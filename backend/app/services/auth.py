from datetime import timedelta
import time
import jwt
import pyotp
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db.base import now
from app.models import (
    User,
    Membership,
    Role,
    UserRole,
    RolePermission,
    RefreshSession,
    UsedRefreshToken,
    PasswordResetToken,
    RateLimit,
    AuditEvent,
    EmailOutbox,
)
from app.security.crypto import token, digest, verify_password, hash_password, DUMMY_HASH, cipher


def throttle(db, key, limit=15, seconds=900):
    key = digest(key)
    item = db.scalar(select(RateLimit).where(RateLimit.key == key).with_for_update())
    if not item:
        try:
            with db.begin_nested():
                db.add(RateLimit(key=key, count=1, resets_at=now() + timedelta(seconds=seconds)))
                db.flush()
        except IntegrityError:
            db.execute(update(RateLimit).where(RateLimit.key == key).values(count=RateLimit.count + 1))
    elif item.resets_at <= now():
        item.count, item.resets_at = 1, now() + timedelta(seconds=seconds)
    elif item.count >= limit:
        raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(seconds)})
    else:
        db.execute(update(RateLimit).where(RateLimit.key == key).values(count=RateLimit.count + 1))
    db.commit()  # Failed authentication must still consume the shared throttle budget.


def identity(db, user, membership):
    roles = list(db.scalars(select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.membership_id == membership.id)))
    permissions = sorted(
        set(
            db.scalars(
                select(RolePermission.permission_code)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .where(UserRole.membership_id == membership.id)
            )
        )
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "institution_id": membership.institution_id,
        "roles": roles,
        "permissions": permissions,
        "mfa_enabled": bool(user.totp_secret),
        "verified": user.verified,
    }


def access_token(session):
    s = settings()
    return jwt.encode(
        {
            "sub": session.user_id,
            "sid": session.id,
            "iat": now(),
            "exp": now() + timedelta(minutes=s.access_minutes),
            "aud": "learnsphere",
            "iss": "learnsphere",
        },
        s.secret_key,
        algorithm="HS256",
    )


def totp_valid(user, code, pending=False):
    encrypted = user.totp_pending if pending else user.totp_secret
    if not encrypted or not code:
        return False
    generator = pyotp.TOTP(cipher().decrypt(encrypted.encode()).decode())
    step = int(time.time()) // 30
    # Prevent reusing a valid OTP within its time step.
    if step <= user.totp_last_step or not generator.verify(code, valid_window=0):
        return False
    user.totp_last_step = step
    return True


def login(db, data, request):
    throttle(db, "login-ip:" + (request.client.host if request.client else "unknown"), 40)
    email = str(data.email).lower()
    throttle(db, "login-account:" + email, 10)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active or (user.locked_until and user.locked_until > now()):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now() + timedelta(minutes=15)
        db.add(AuditEvent(actor_id=user.id if user else None, action="auth.login_failed", resource_type="auth", detail={}))
        db.commit()
        raise HTTPException(401, "Invalid credentials or account temporarily locked")
    if user.totp_secret and not totp_valid(user, data.totp):
        db.commit()
        raise HTTPException(401, "A valid authenticator code is required")
    if settings().email_verification_required and not user.verified:
        raise HTTPException(403, "Verify your email before signing in")
    query = select(Membership).where(Membership.user_id == user.id)
    if data.institution_id:
        query = query.where(Membership.institution_id == data.institution_id)
    memberships = db.scalars(query).all()
    if len(memberships) != 1:
        raise HTTPException(400, "Select your institution to continue")
    membership = memberships[0]
    user.failed_logins, user.locked_until = 0, None
    raw, csrf = token(), token()
    session = RefreshSession(
        user_id=user.id,
        membership_id=membership.id,
        token_hash=digest(raw),
        csrf_hash=digest(csrf),
        expires_at=now() + timedelta(days=settings().refresh_days),
        user_agent=request.headers.get("user-agent", "")[:250],
        ip_hash=digest((request.client.host if request.client else "unknown")),
    )
    db.add(session)
    db.add(AuditEvent(institution_id=membership.institution_id, actor_id=user.id, action="auth.login", resource_type="auth", detail={}))
    db.flush()
    return session, raw, csrf, identity(db, user, membership)


def rotate(db, raw, csrf):
    hashed = digest(raw)
    used = db.get(UsedRefreshToken, hashed)
    if used:
        db.execute(update(RefreshSession).where(RefreshSession.id == used.session_id).values(revoked=True))
        db.commit()
        raise HTTPException(401, "Refresh token replay detected; sign in again")
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hashed).with_for_update())
    if not session or session.revoked or session.expires_at <= now():
        raise HTTPException(401, "Session expired")
    if digest(csrf) != session.csrf_hash:
        raise HTTPException(403, "Invalid CSRF token")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable")
    new_raw = token()
    changed = db.execute(
        update(RefreshSession)
        .where(RefreshSession.id == session.id, RefreshSession.token_hash == hashed, RefreshSession.revoked.is_(False))
        .values(token_hash=digest(new_raw))
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Concurrent refresh; sign in again")
    db.add(UsedRefreshToken(token_hash=hashed, session_id=session.id))
    db.flush()
    return session, new_raw, identity(db, user, db.get(Membership, session.membership_id))


def queue_token(db, user, kind):
    raw = token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=digest(raw), kind=kind, expires_at=now() + timedelta(minutes=30)))
    path = "verify-email" if kind == "verify" else "reset-password"
    link = f"{settings().frontend_url}/{path}#token={raw}"
    body = f"LearnSphere Enterprise: {kind}\nThis link expires in 30 minutes and can be used once.\n{link}"
    db.add(
        EmailOutbox(
            recipient=user.email,
            subject=f"LearnSphere {kind}",
            encrypted_body=cipher().encrypt(body.encode()).decode(),
            next_attempt_at=now(),
            status="pending" if settings().smtp_host else "unconfigured",
        )
    )
    return raw


def use_token(db, raw, password=None):
    t = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest(raw)).with_for_update())
    if (
        not t
        or t.used_at
        or t.expires_at <= now()
        or (password is None and t.kind != "verify")
        or (password is not None and t.kind not in {"reset", "invite"})
    ):
        raise HTTPException(400, "Token expired, invalid, or already used")
    new_hash = hash_password(password) if password is not None else None
    result = db.execute(
        update(PasswordResetToken).where(PasswordResetToken.id == t.id, PasswordResetToken.used_at.is_(None)).values(used_at=now())
    )
    if result.rowcount != 1:
        raise HTTPException(400, "Token already used")
    user = db.get(User, t.user_id)
    if new_hash:
        user.password_hash = new_hash
        user.failed_logins, user.locked_until = 0, None
        db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id).values(revoked=True))
    user.verified = True
    db.add(AuditEvent(actor_id=user.id, action=f"auth.{t.kind}_completed", resource_type="users", resource_id=user.id, detail={}))
