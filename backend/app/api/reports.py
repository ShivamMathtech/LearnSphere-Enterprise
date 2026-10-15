from app.services.common import required
import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import now
from app.db.session import get_db
from app.models import (
    Institution,
    User,
    Membership,
    Role,
    UserRole,
    Course,
    Enrollment,
    Quiz,
    QuizAttempt,
    Assignment,
    Submission,
    Grade,
    AuditEvent,
    LearningActivity,
    AttendanceRecord,
    AttendanceSession,
    EmailOutbox,
    Department,
)
from app.security.access import Principal, current, permit, tenant, visible_course_ids
from app.services.common import public, page, audit, check_dates
from app.services.learning import progress
from app.api.deps import Pagination
from app.schemas import contracts as s

router = APIRouter(tags=["Reports and system"])


def count(db, model, *criteria):
    return db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0


def range_filter(query, model, start, end):
    check_dates(start, end)
    if start:
        query = query.where(model.created_at >= start)
    if end:
        query = query.where(model.created_at <= end)
    return query


@router.get("/reports/dashboard")
def dashboard(start: datetime | None = None, end: datetime | None = None, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.super and not p.tenant_id:
        return {
            "scope": "platform",
            "metrics": {
                "Institutions": count(db, Institution),
                "Active users": count(db, User, User.active.is_(True)),
                "Courses": count(db, Course),
                "Security events": count(db, AuditEvent, AuditEvent.action.like("auth.%")),
            },
            "trend": [],
            "courses": [],
            "deadlines": [],
            "activity": [],
        }
    tenant_id = tenant(p)
    allowed = visible_course_ids(db, p)
    course_query = select(Course).where(Course.institution_id == tenant_id, Course.id.in_(allowed))
    e_query = select(Enrollment).where(Enrollment.institution_id == tenant_id, Enrollment.course_id.in_(allowed))
    is_learner = "student" in p.roles
    if is_learner:
        e_query = e_query.where(Enrollment.user_id == p.user.id)
    e_query = range_filter(e_query, Enrollment, start, end)
    # Aggregate metrics in SQL; detailed progress is computed from persisted completion records.
    e_sub = e_query.subquery()
    total = db.scalar(select(func.count()).select_from(e_sub)) or 0
    completed = db.scalar(select(func.count()).select_from(e_sub).where(e_sub.c.status == "completed")) or 0
    pending_query = (
        select(func.count())
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Submission.institution_id == tenant_id, Assignment.course_id.in_(allowed), Submission.status == "submitted")
    )
    if is_learner:
        pending_query = pending_query.where(Submission.user_id == p.user.id)
    metrics = {
        "My courses" if is_learner else "Courses": db.scalar(select(func.count()).select_from(course_query.subquery())) or 0,
        "Enrollments": total,
        "Completion rate": round(100 * completed / total, 1) if total else 0,
        "Pending review": db.scalar(pending_query) or 0,
    }
    if p.manager:
        for role_name, label in [("student", "Students"), ("instructor", "Faculty")]:
            metrics[label] = (
                db.scalar(
                    select(func.count())
                    .select_from(Membership)
                    .join(UserRole, UserRole.membership_id == Membership.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(Membership.institution_id == tenant_id, Role.name == role_name)
                )
                or 0
            )
    trend = []
    day = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    for index in range(7):
        begin = day + timedelta(days=index)
        finish = begin + timedelta(days=1)
        trend.append(
            {
                "date": begin.date().isoformat(),
                "enrollments": db.scalar(
                    select(func.count()).select_from(e_sub).where(e_sub.c.created_at >= begin, e_sub.c.created_at < finish)
                )
                or 0,
                "completions": db.scalar(
                    select(func.count()).select_from(e_sub).where(e_sub.c.completed_at >= begin, e_sub.c.completed_at < finish)
                )
                or 0,
            }
        )
    courses = []
    for c in db.scalars(course_query.order_by(Course.updated_at.desc()).limit(6)):
        enrollments = db.scalars(e_query.where(Enrollment.course_id == c.id)).all()
        percentages = [progress(db, e)["percent"] for e in enrollments]
        courses.append(
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "difficulty": c.difficulty,
                "learners": len(enrollments),
                "progress": round(sum(percentages) / len(percentages), 1) if percentages else 0,
            }
        )
    deadlines = [
        {"id": a.id, "course_id": a.course_id, "title": a.title, "due_at": a.due_at, "kind": "assignment"}
        for a in db.scalars(
            select(Assignment)
            .where(Assignment.institution_id == tenant_id, Assignment.course_id.in_(allowed), Assignment.due_at >= now())
            .order_by(Assignment.due_at)
            .limit(6)
        )
    ]
    deadlines += [
        {"id": q.id, "course_id": q.course_id, "title": q.title, "due_at": q.closes_at, "kind": "quiz"}
        for q in db.scalars(
            select(Quiz)
            .where(Quiz.institution_id == tenant_id, Quiz.course_id.in_(allowed), Quiz.closes_at >= now())
            .order_by(Quiz.closes_at)
            .limit(6)
        )
    ]
    activity_query = select(LearningActivity).where(LearningActivity.institution_id == tenant_id, LearningActivity.course_id.in_(allowed))
    if is_learner:
        activity_query = activity_query.where(LearningActivity.user_id == p.user.id)
    return {
        "scope": "learner" if is_learner else "institution",
        "metrics": metrics,
        "trend": trend,
        "courses": courses,
        "deadlines": sorted(deadlines, key=lambda d: str(d["due_at"]))[:6],
        "activity": [public(a) for a in db.scalars(activity_query.order_by(LearningActivity.created_at.desc()).limit(8))],
    }


@router.get("/reports/enrollments", response_model=s.Page)
def enrollment_report(
    start: datetime | None = None,
    end: datetime | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("reports.read")),
    db: Session = Depends(get_db),
):
    query = range_filter(
        select(Enrollment).where(Enrollment.institution_id == tenant(p), Enrollment.course_id.in_(visible_course_ids(db, p))),
        Enrollment,
        start,
        end,
    )
    return page(
        db,
        q.apply(query, Enrollment),
        q.page,
        q.page_size,
        lambda e: {
            **public(e),
            "student_name": required(db, User, e.user_id).name,
            "course_title": required(db, Course, e.course_id).title,
            "progress": progress(db, e)["percent"],
        },
    )


def csv_safe(value):
    text = str(value or "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/reports/export.csv")
def export(
    kind: str = "enrollments",
    start: datetime | None = None,
    end: datetime | None = None,
    p: Principal = Depends(permit("reports.export")),
    db: Session = Depends(get_db),
):
    allowed = visible_course_ids(db, p)
    rows = []
    if kind == "enrollments":
        columns = ["course", "learner", "status", "progress_percent", "enrolled_at"]
        query = range_filter(
            select(Enrollment).where(Enrollment.institution_id == tenant(p), Enrollment.course_id.in_(allowed)), Enrollment, start, end
        )
        for e in db.scalars(query.limit(10001)):
            rows.append(
                [
                    required(db, Course, e.course_id).title,
                    required(db, User, e.user_id).name,
                    e.status,
                    progress(db, e)["percent"],
                    e.created_at.isoformat(),
                ]
            )
    elif kind == "grades":
        columns = ["assignment", "learner", "version", "marks", "released", "graded_at"]
        query = range_filter(
            select(Grade)
            .join(Submission, Grade.submission_id == Submission.id)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Grade.institution_id == tenant(p), Assignment.course_id.in_(allowed)),
            Grade,
            start,
            end,
        )
        for grade in db.scalars(query.limit(10001)):
            sub = required(db, Submission, grade.submission_id)
            rows.append(
                [
                    required(db, Assignment, sub.assignment_id).title,
                    required(db, User, sub.user_id).name,
                    sub.version,
                    grade.marks,
                    grade.released,
                    grade.updated_at.isoformat(),
                ]
            )
    elif kind == "attendance":
        columns = ["session", "learner", "status", "recorded_at"]
        query = range_filter(
            select(AttendanceRecord)
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .where(AttendanceRecord.institution_id == tenant(p), AttendanceSession.course_id.in_(allowed)),
            AttendanceRecord,
            start,
            end,
        )
        for record in db.scalars(query.limit(10001)):
            rows.append(
                [
                    required(db, AttendanceSession, record.session_id).title,
                    required(db, User, record.user_id).name,
                    record.status,
                    record.updated_at.isoformat(),
                ]
            )
    else:
        raise HTTPException(422, "Unsupported report type")
    if len(rows) > 10000:
        raise HTTPException(422, "Narrow the date range to export at most 10000 records")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows([[csv_safe(c) for c in row] for row in rows])
    audit(db, p, "reports.exported", detail={"kind": kind, "rows": len(rows)})
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.get("/reports/academic")
def academic_report(p: Principal = Depends(permit("reports.read")), db: Session = Depends(get_db)):
    allowed = visible_course_ids(db, p)
    departments = []
    for d in db.scalars(select(Department).where(Department.institution_id == tenant(p))):
        course_ids = select(Course.id).where(Course.department_id == d.id, Course.id.in_(allowed))
        total = count(db, Enrollment, Enrollment.course_id.in_(course_ids))
        completed = count(db, Enrollment, Enrollment.course_id.in_(course_ids), Enrollment.status == "completed")
        departments.append({"department": d.name, "enrollments": total, "completed": completed})
    outcomes = db.execute(
        select(Quiz.title, func.avg(QuizAttempt.score * 100 / QuizAttempt.max_score), func.count(QuizAttempt.id))
        .join(QuizAttempt, Quiz.id == QuizAttempt.quiz_id)
        .where(Quiz.institution_id == tenant(p), Quiz.course_id.in_(allowed), QuizAttempt.status == "graded")
        .group_by(Quiz.id, Quiz.title)
    ).all()
    return {
        "departments": departments,
        "quiz_outcomes": [{"title": title, "average_percent": round(avg or 0, 1), "attempts": count_} for title, avg, count_ in outcomes],
    }


@router.get("/audit-logs", response_model=s.Page)
def audit_logs(
    start: datetime | None = None,
    end: datetime | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("audit.read")),
    db: Session = Depends(get_db),
):
    query = select(AuditEvent)
    if not p.super or p.tenant_id:
        query = query.where(AuditEvent.institution_id == tenant(p))
    query = range_filter(query, AuditEvent, start, end)
    return page(db, q.apply(query, AuditEvent, AuditEvent.action), q.page, q.page_size)


@router.get("/system/status")
def system_status(p: Principal = Depends(permit("settings.manage")), db: Session = Depends(get_db)):
    result = {
        "environment": settings().app_env,
        "database": db.get_bind().dialect.name,
        "smtp": "configured" if settings().smtp_host else "unconfigured",
        "meeting_provider": "manual links only; no API provider configured",
        "plagiarism_provider": "not configured",
        "upload_max_mb": settings().upload_max_mb,
        "audit_retention_days": settings().audit_retention_days,
        "require_privileged_mfa": settings().require_privileged_mfa,
    }
    if p.super:
        result["mail_queue"] = {
            str(status): int(count_) for status, count_ in db.execute(select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status))
        }
    return result
