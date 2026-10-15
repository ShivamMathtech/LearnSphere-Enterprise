from app.services.common import required
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.base import now
from app.db.session import get_db
from app.models import (
    Certificate,
    Enrollment,
    Institution,
    AttendanceSession,
    AttendanceRecord,
    CourseInstructor,
    Announcement,
    Discussion,
    DiscussionReply,
    Message,
    Notification,
    User,
)
from app.schemas import contracts as s
from app.security.access import Principal, current, permit, scoped, tenant, course_access, active_enrollment, member, visible_course_ids
from app.services.common import public, page, audit, notify, check_dates
from app.services import certificates
from app.services.auth import throttle
from app.api.deps import Pagination

router = APIRouter(tags=["Community, attendance and certificates"])


@router.get("/certificates", response_model=s.Page)
def certificate_list(q: Pagination = Depends(), p: Principal = Depends(permit("certificates.read")), db: Session = Depends(get_db)):
    query = select(Certificate).join(Enrollment).where(Certificate.institution_id == tenant(p))
    if "certificates.manage" not in p.permissions:
        query = query.where(Enrollment.user_id == p.user.id)
    return page(db, q.apply(query, Certificate), q.page, q.page_size)


@router.post("/certificates/issue/{enrollment_id}", response_model=s.Record, status_code=201)
def issue(enrollment_id: str, p: Principal = Depends(permit("certificates.read")), db: Session = Depends(get_db)):
    e = scoped(db, Enrollment, enrollment_id, p)
    if e.user_id != p.user.id:
        p.require("certificates.manage")
    active_enrollment(db, p, e.course_id, e.user_id)
    return public(certificates.issue(db, p, e))


@router.get("/certificates/verify/{code}")
def verify(code: str, request: Request, db: Session = Depends(get_db)):
    throttle(db, "certificate-verify:" + (request.client.host if request.client else "unknown"), 60, 60)
    row = db.scalar(select(Certificate).where(Certificate.code == code[:80]))
    if not row:
        raise HTTPException(404, "No matching certificate")
    parts = row.student_name.split()
    return {
        "valid": row.revoked_at is None,
        "code": row.code,
        "learner": parts[0] + (" " + parts[-1][0] + "." if len(parts) > 1 else ""),
        "course": row.course_title,
        "institution": required(db, Institution, row.institution_id).name,
        "issued_at": row.created_at,
        "revoked_at": row.revoked_at,
    }


@router.get("/certificates/{certificate_id}/pdf")
def download_certificate(certificate_id: str, p: Principal = Depends(permit("certificates.read")), db: Session = Depends(get_db)):
    row = scoped(db, Certificate, certificate_id, p)
    e = scoped(db, Enrollment, row.enrollment_id, p)
    if e.user_id != p.user.id:
        p.require("certificates.manage")
    return Response(
        certificates.pdf(db, row),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="certificate-' + row.code + '.pdf"'},
    )


@router.post("/certificates/{certificate_id}/revoke", response_model=s.Record)
def revoke(certificate_id: str, data: s.RevokeInput, p: Principal = Depends(permit("certificates.manage")), db: Session = Depends(get_db)):
    row = scoped(db, Certificate, certificate_id, p)
    row.revoked_at, row.revocation_reason = now(), data.reason
    audit(db, p, "certificates.revoked", row, {"reason": data.reason})
    return public(row)


@router.get("/attendance", response_model=s.Page)
def sessions(
    course_id: str | None = None, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)
):
    query = select(AttendanceSession).where(
        AttendanceSession.institution_id == tenant(p), AttendanceSession.course_id.in_(visible_course_ids(db, p))
    )
    if course_id:
        query = query.where(AttendanceSession.course_id == course_id)
    return page(db, q.apply(query, AttendanceSession, AttendanceSession.title), q.page, q.page_size)


@router.post("/attendance", response_model=s.Record, status_code=201)
def add_session(data: s.AttendanceInput, p: Principal = Depends(permit("attendance.manage")), db: Session = Depends(get_db)):
    course_access(db, p, data.course_id, "write")
    check_dates(data.starts_at, data.ends_at)
    instructor = data.instructor_id or p.user.id
    member(db, instructor, p)
    if not db.get(CourseInstructor, (data.course_id, instructor)):
        raise HTTPException(422, "Session instructor must be assigned to the course")
    row = AttendanceSession(institution_id=tenant(p), **(data.model_dump() | {"instructor_id": instructor}))
    db.add(row)
    db.flush()
    audit(db, p, "attendance.session_created", row)
    return public(row)


def mark_attendance(db, p, session, data):
    active_enrollment(db, p, session.course_id, data.user_id)
    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.session_id == session.id, AttendanceRecord.user_id == data.user_id))
    previous = row.status if row else None
    if not row:
        row = AttendanceRecord(
            institution_id=tenant(p), session_id=session.id, user_id=data.user_id, recorded_by=p.user.id, status=data.status
        )
        db.add(row)
    row.status, row.note, row.recorded_by = data.status, data.note, p.user.id
    db.flush()
    audit(db, p, "attendance.corrected" if previous else "attendance.recorded", row, {"previous": previous, "status": data.status})
    return row


@router.put("/attendance/{session_id}/records", response_model=s.Record)
def mark(session_id: str, data: s.AttendanceMark, p: Principal = Depends(permit("attendance.manage")), db: Session = Depends(get_db)):
    session = scoped(db, AttendanceSession, session_id, p)
    course_access(db, p, session.course_id, "write")
    return public(mark_attendance(db, p, session, data))


@router.get("/attendance/{session_id}/records", response_model=s.Page)
def records(session_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    session = scoped(db, AttendanceSession, session_id, p)
    course_access(db, p, session.course_id)
    query = select(AttendanceRecord).where(AttendanceRecord.session_id == session.id, AttendanceRecord.institution_id == tenant(p))
    if "attendance.manage" not in p.permissions:
        query = query.where(AttendanceRecord.user_id == p.user.id)
    return page(
        db,
        q.apply(query, AttendanceRecord),
        q.page,
        q.page_size,
        lambda r: {**public(r), "student_name": required(db, User, r.user_id).name},
    )


@router.post("/attendance/{session_id}/import", response_model=s.Result)
def import_attendance(
    session_id: str, data: s.ImportInput, p: Principal = Depends(permit("attendance.manage")), db: Session = Depends(get_db)
):
    session = scoped(db, AttendanceSession, session_id, p)
    course_access(db, p, session.course_id, "write")
    rows = list(csv.DictReader(io.StringIO(data.csv_text)))
    if len(rows) > 500:
        raise HTTPException(422, "At most 500 attendance rows per import")
    from pydantic import ValidationError

    for index, row in enumerate(rows, start=2):
        try:
            entry = s.AttendanceMark.model_validate(row)
        except ValidationError as exc:
            raise HTTPException(422, {"row": index, "errors": exc.errors(include_input=False, include_context=False)}) from None
        mark_attendance(db, p, session, entry)
    return {"message": f"{len(rows)} attendance rows saved"}


def register_posts(path, model, permission):
    def listing(course_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
        course_access(db, p, course_id)
        query = select(model).where(model.institution_id == tenant(p), model.course_id == course_id)
        return page(
            db,
            q.apply(query, model, model.title),
            q.page,
            q.page_size,
            lambda r: {**public(r), "author_name": required(db, User, r.author_id).name},
        )

    def create(data: s.PostInput, p: Principal = Depends(permit(permission)), db: Session = Depends(get_db)):
        course_access(db, p, data.course_id, "write" if model == Announcement else "read")
        if "teaching_assistant" in p.roles:
            course_access(db, p, data.course_id, "discuss")
        row = model(institution_id=tenant(p), author_id=p.user.id, **data.model_dump())
        db.add(row)
        db.flush()
        audit(db, p, path + ".created", row)
        if model == Announcement:
            for e in db.scalars(
                select(Enrollment).where(Enrollment.course_id == data.course_id, Enrollment.status.in_(["active", "completed"]))
            ):
                notify(db, tenant(p), e.user_id, data.title, "New course announcement")
        return public(row)

    router.add_api_route("/" + path, listing, methods=["GET"], response_model=s.Page, name=path + "_list")
    router.add_api_route("/" + path, create, methods=["POST"], response_model=s.Record, status_code=201, name=path + "_create")


register_posts("announcements", Announcement, "announcements.create")
register_posts("discussions", Discussion, "discussions.write")


@router.get("/discussions/{discussion_id}/replies", response_model=s.Page)
def replies(discussion_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    d = scoped(db, Discussion, discussion_id, p)
    course_access(db, p, d.course_id)
    return page(
        db,
        q.apply(
            select(DiscussionReply).where(DiscussionReply.discussion_id == d.id, DiscussionReply.institution_id == tenant(p)),
            DiscussionReply,
        ),
        q.page,
        q.page_size,
        lambda r: {**public(r), "author_name": required(db, User, r.author_id).name},
    )


@router.post("/discussions/{discussion_id}/replies", response_model=s.Record, status_code=201)
def reply(discussion_id: str, data: s.ReplyInput, p: Principal = Depends(permit("discussions.write")), db: Session = Depends(get_db)):
    d = scoped(db, Discussion, discussion_id, p)
    course_access(db, p, d.course_id, "discuss" if "teaching_assistant" in p.roles else "read")
    row = DiscussionReply(institution_id=tenant(p), discussion_id=d.id, author_id=p.user.id, body=data.body)
    db.add(row)
    db.flush()
    return public(row)


@router.post("/messages", response_model=s.Record, status_code=201)
def message(data: s.MessageInput, p: Principal = Depends(permit("messages.create")), db: Session = Depends(get_db)):
    course_access(db, p, data.course_id, "write")
    active_enrollment(db, p, data.course_id, data.recipient_id)
    row = Message(institution_id=tenant(p), sender_id=p.user.id, **data.model_dump())
    db.add(row)
    db.flush()
    notify(db, tenant(p), data.recipient_id, "Message from " + p.user.name, data.body)
    return public(row)


@router.get("/messages", response_model=s.Page)
def messages(q: Pagination = Depends(), p: Principal = Depends(current), db: Session = Depends(get_db)):
    query = select(Message).where(
        Message.institution_id == tenant(p), (Message.sender_id == p.user.id) | (Message.recipient_id == p.user.id)
    )
    return page(db, q.apply(query, Message), q.page, q.page_size)


@router.get("/notifications", response_model=s.Page)
def notifications(unread: bool = False, q: Pagination = Depends(), p: Principal = Depends(current), db: Session = Depends(get_db)):
    query = select(Notification).where(Notification.institution_id == tenant(p), Notification.user_id == p.user.id)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    return page(db, q.apply(query, Notification, Notification.title), q.page, q.page_size)


@router.post("/notifications/{notification_id}/read", response_model=s.Record)
def read_notification(notification_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    row = scoped(db, Notification, notification_id, p)
    if row.user_id != p.user.id:
        raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or now()
    return public(row)
