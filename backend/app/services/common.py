from typing import Any, TypeVar
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import func, select
from app.db.base import now
from app.models import AuditEvent, Notification

HIDDEN = {
    "password_hash",
    "totp_secret",
    "totp_pending",
    "totp_last_step",
    "failed_logins",
    "locked_until",
    "token_hash",
    "csrf_hash",
    "storage_key",
    "encrypted_body",
}


def public(row, exclude=()):
    return {
        c.name: (v.isoformat() if isinstance(v, datetime) else v)
        for c in row.__table__.columns
        if c.name not in HIDDEN and c.name not in exclude
        for v in [getattr(row, c.name)]
    }


def page(db, query, page_number=1, page_size=20, serializer=public):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.scalars(query.offset((page_number - 1) * page_size).limit(page_size)).all()
    return {"items": [serializer(r) for r in rows], "total": total, "page": page_number, "page_size": page_size}


def audit(db, p, action, obj=None, detail=None):
    db.add(
        AuditEvent(
            institution_id=p.tenant_id,
            actor_id=p.user.id,
            action=action,
            resource_type=obj.__tablename__ if obj is not None else "system",
            resource_id=getattr(obj, "id", None),
            detail=detail or {},
        )
    )


def notify(db, institution_id, user_id, title, body, dedupe_key=None):
    if dedupe_key and db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key)):
        return
    db.add(Notification(institution_id=institution_id, user_id=user_id, title=title, body=body, dedupe_key=dedupe_key))


def check_dates(start, end):
    if start and end and start >= end:
        raise HTTPException(422, "The end must be later than the start")


def require_window(start, end):
    if start and now() < start:
        raise HTTPException(409, "This activity has not opened yet")
    if end and now() > end:
        raise HTTPException(409, "This activity has closed")


T = TypeVar("T")


def required(db: Session, model: type[T], key: Any) -> T:
    """Fetch a row whose ID was obtained through an authorized relation."""
    row = db.get(model, key)
    if row is None:
        raise HTTPException(404, "Related record is unavailable")
    return row
