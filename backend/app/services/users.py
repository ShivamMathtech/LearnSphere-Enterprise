import csv
import io
import json
import hmac
import hashlib
import secrets
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from app.core.config import settings
from app.models import User, Membership, Role, UserRole, Department
from app.schemas.contracts import UserCreate
from app.security.access import scoped, tenant
from app.security.crypto import hash_password
from app.services.auth import queue_token
from app.services.common import audit


def authorize_role(p, role):
    p.require("roles.assign")
    if role == "institution_admin" and not p.super:
        raise HTTPException(403, "Only a super administrator may appoint institution administrators")


def create_user(db, p, data):
    p.require("users.create")
    authorize_role(p, data.role)
    if data.department_id:
        scoped(db, Department, data.department_id, p)
    if not data.invite and not data.password:
        raise HTTPException(422, "Supply an initial password or select invitation")
    user = User(
        name=data.name,
        email=str(data.email).lower(),
        password_hash=hash_password(data.password or ("Invite9" + secrets.token_urlsafe(32))),
        verified=False,
    )
    db.add(user)
    db.flush()
    membership = Membership(user_id=user.id, institution_id=tenant(p), identifier=data.identifier, department_id=data.department_id)
    db.add(membership)
    db.flush()
    role = db.scalar(select(Role).where(Role.name == data.role))
    db.add(UserRole(membership_id=membership.id, role_id=role.id))
    delivery = None
    if data.invite:
        queue_token(db, user, "invite")
        delivery = "queued" if settings().smtp_host else "unconfigured"
    elif settings().email_verification_required:
        queue_token(db, user, "verify")
    audit(db, p, "users.created", user, {"role": data.role, "invitation": bool(data.invite)})
    return user, delivery


def preview_import(db, p, data):
    p.require("imports.manage")
    if not {"name", "email"} <= set(data.mapping):
        raise HTTPException(422, "Map the name and email columns")
    if set(data.mapping) - {"name", "email", "identifier", "department_id"}:
        raise HTTPException(422, "Unsupported mapped field")
    reader = csv.DictReader(io.StringIO(data.csv_text.lstrip("\ufeff")))
    if not reader.fieldnames or not set(data.mapping.values()) <= set(reader.fieldnames):
        raise HTTPException(422, "Mapped columns must exist in the CSV header")
    rows, errors, seen_emails, seen_ids = [], [], set(), set()
    for line, row in enumerate(reader, 2):
        if line > 501:
            raise HTTPException(422, "At most 500 rows per import")
        try:
            values = {key: row.get(source) or None for key, source in data.mapping.items()}
            user = UserCreate.model_validate(values | {"role": data.role, "invite": True})
            email = str(user.email).lower()
            if email in seen_emails or db.scalar(select(User.id).where(User.email == email)):
                raise ValueError("Duplicate email")
            if user.identifier and (
                user.identifier in seen_ids
                or db.scalar(select(Membership.id).where(Membership.institution_id == tenant(p), Membership.identifier == user.identifier))
            ):
                raise ValueError("Duplicate institutional identifier")
            if user.department_id:
                scoped(db, Department, user.department_id, p)
            seen_emails.add(email)
            if user.identifier:
                seen_ids.add(user.identifier)
            rows.append({"line": line, **user.model_dump(mode="json", exclude={"password"})})
        except (ValueError, ValidationError, HTTPException) as exc:
            errors.append({"line": line, "error": str(exc.detail) if isinstance(exc, HTTPException) else str(exc)[:500]})
    raw = json.dumps({"tenant": tenant(p), "csv": data.csv_text, "mapping": data.mapping, "role": data.role}, sort_keys=True)
    signed = hmac.new(settings().secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return {"rows": rows, "errors": errors, "valid_count": len(rows), "error_count": len(errors), "preview_hash": signed}
