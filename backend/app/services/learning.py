from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from app.db.base import now
from app.models import (
    Course,
    CourseInstructor,
    CourseSection,
    Lesson,
    LessonResource,
    CourseVersion,
    Enrollment,
    LessonProgress,
    LearningActivity,
    Quiz,
    QuizAttempt,
    Assignment,
    Submission,
    Grade,
    UserRole,
    Role,
)
from app.security.access import tenant, scoped, course_access, active_enrollment, member
from app.services.common import public, audit, notify, check_dates


def course_outline(db, course, include_content=True):
    sections = []
    for section in db.scalars(select(CourseSection).where(CourseSection.course_id == course.id).order_by(CourseSection.position)):
        lessons = []
        for lesson in db.scalars(select(Lesson).where(Lesson.section_id == section.id).order_by(Lesson.position)):
            item = public(lesson, [] if include_content else ["content", "url"])
            if include_content:
                item["file_ids"] = list(db.scalars(select(LessonResource.file_id).where(LessonResource.lesson_id == lesson.id)))
            lessons.append(item)
        sections.append({**public(section), "lessons": lessons})
    return sections


def publish(db, p, course):
    if course.status != "in_review":
        raise HTTPException(409, "Submit the draft for review before publishing")
    lessons = db.scalars(select(Lesson).where(Lesson.course_id == course.id)).all()
    if not course.description.strip() or not course.objectives.strip() or not lessons:
        raise HTTPException(422, "Add a description, objectives and at least one lesson before publishing")
    for lesson in lessons:
        if lesson.kind == "text" and not lesson.content.strip():
            raise HTTPException(422, f"Lesson is empty: {lesson.title}")
        if lesson.kind in {"video", "link"} and not lesson.url:
            raise HTTPException(422, f"Lesson needs a URL: {lesson.title}")
        if lesson.kind in {"pdf", "document", "resource"} and not db.scalar(
            select(LessonResource.file_id).where(LessonResource.lesson_id == lesson.id)
        ):
            raise HTTPException(422, f"Lesson needs an uploaded resource: {lesson.title}")
    if not db.scalar(select(CourseInstructor.user_id).where(CourseInstructor.course_id == course.id)):
        raise HTTPException(422, "Assign an instructor before publishing")
    course.status = "published"
    db.add(
        CourseVersion(
            institution_id=tenant(p),
            course_id=course.id,
            version=course.version,
            snapshot={**public(course), "sections": course_outline(db, course)},
        )
    )
    audit(db, p, "courses.published", course)
    notify(db, p.tenant_id, p.user.id, "Course published", course.title)


def enroll(db, p, data, bulk=False):
    course = scoped(db, Course, data.course_id, p)
    # A write locks this capacity decision on both SQLite and PostgreSQL.
    db.execute(update(Course).where(Course.id == course.id).values(updated_at=now()))
    who = data.user_id or p.user.id
    if who != p.user.id or bulk:
        p.require("enrollments.manage")
        course_access(db, p, course.id, "write")
    m = member(db, who, p)
    learner_role = db.scalar(
        select(Role.name).join(UserRole, Role.id == UserRole.role_id).where(UserRole.membership_id == m.id, Role.name == "student")
    )
    if not learner_role:
        raise HTTPException(422, "Only student memberships can be enrolled")
    if course.status != "published":
        raise HTTPException(409, "Only published courses accept new enrollments")
    if not p.manager and (course.enrollment_policy == "closed" or course.visibility == "assigned"):
        raise HTTPException(403, "This course requires administrator enrollment")
    if not p.manager and (data.starts_at or data.ends_at):
        raise HTTPException(403, "Only administrators may set access dates")
    check_dates(data.starts_at, data.ends_at)
    existing = db.scalar(select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.user_id == who))
    if existing:
        return existing
    count = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.course_id == course.id, Enrollment.status.in_(["active", "completed"]))
    )
    status = (
        "pending"
        if course.enrollment_policy == "approval" and not p.manager
        else ("waitlisted" if count >= course.max_learners else "active")
    )
    e = Enrollment(
        institution_id=tenant(p), course_id=course.id, user_id=who, status=status, starts_at=data.starts_at, ends_at=data.ends_at
    )
    db.add(e)
    db.flush()
    audit(db, p, "enrollments.created", e, {"status": status})
    notify(db, tenant(p), who, "Enrollment " + status, course.title)
    return e


def progress(db, enrollment):
    total = db.scalar(select(func.count()).select_from(Lesson).where(Lesson.course_id == enrollment.course_id))
    complete_ids = list(db.scalars(select(LessonProgress.lesson_id).where(LessonProgress.enrollment_id == enrollment.id)))
    return {
        "completed": len(complete_ids),
        "total": total,
        "percent": round(100 * len(complete_ids) / total, 1) if total else 0,
        "completed_lesson_ids": complete_ids,
        "last_lesson_id": enrollment.last_lesson_id,
    }


def eligibility(db, enrollment):
    course = db.get(Course, enrollment.course_id)
    state = progress(db, enrollment)
    reasons = []
    if not state["total"] or state["completed"] < state["total"]:
        reasons.append("Complete every lesson")
    if course.require_assessments:
        for quiz in db.scalars(select(Quiz).where(Quiz.course_id == course.id, Quiz.required.is_(True))):
            attempts = db.scalars(
                select(QuizAttempt).where(
                    QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == enrollment.user_id, QuizAttempt.status == "graded"
                )
            ).all()
            released = (
                quiz.release_policy == "immediate"
                or quiz.released
                or (quiz.release_policy == "after_close" and quiz.closes_at and now() >= quiz.closes_at)
            )
            if not released or not any(a.max_score and (a.score or 0) * 100 / a.max_score >= quiz.pass_percent for a in attempts):
                reasons.append("Pass quiz: " + quiz.title)
        for assignment in db.scalars(select(Assignment).where(Assignment.course_id == course.id, Assignment.required.is_(True))):
            latest = db.scalar(
                select(Submission)
                .where(Submission.assignment_id == assignment.id, Submission.user_id == enrollment.user_id)
                .order_by(Submission.version.desc())
            )
            grade = db.scalar(select(Grade).where(Grade.submission_id == latest.id)) if latest else None
            if not grade or not grade.released or grade.marks * 100 / assignment.max_marks < assignment.pass_percent:
                reasons.append("Pass assignment: " + assignment.title)
    return {**state, "eligible": not reasons, "remaining": reasons}


def lesson_open(db, p, lesson):
    course_access(db, p, lesson.course_id)
    if p.manager or db.get(CourseInstructor, (lesson.course_id, p.user.id)):
        return None
    e = active_enrollment(db, p, lesson.course_id)
    start = e.starts_at or e.created_at
    if now() < start + timedelta(days=lesson.drip_days):
        raise HTTPException(403, "This lesson has not been released yet")
    if lesson.prerequisite_id and not db.scalar(
        select(LessonProgress.id).where(LessonProgress.enrollment_id == e.id, LessonProgress.lesson_id == lesson.prerequisite_id)
    ):
        raise HTTPException(403, "Complete the prerequisite lesson first")
    return e


def complete_lesson(db, p, lesson):
    e = lesson_open(db, p, lesson)
    if e is None:
        raise HTTPException(403, "Learning progress is recorded for enrolled learners")
    exists = db.scalar(select(LessonProgress.id).where(LessonProgress.enrollment_id == e.id, LessonProgress.lesson_id == lesson.id))
    if not exists:
        try:
            with db.begin_nested():
                db.add(LessonProgress(institution_id=tenant(p), enrollment_id=e.id, lesson_id=lesson.id))
                db.flush()
                db.add(
                    LearningActivity(
                        institution_id=tenant(p),
                        user_id=p.user.id,
                        course_id=lesson.course_id,
                        lesson_id=lesson.id,
                        action="lesson_completed",
                    )
                )
        except IntegrityError:
            pass  # The uniqueness constraint makes a concurrent retry idempotent.
    e.last_lesson_id = lesson.id
    db.flush()
    return eligibility(db, e)
