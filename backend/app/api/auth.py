import hmac
import pyotp
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models import User, UserProfile, RefreshSession
from app.schemas import contracts as s
from app.security.access import current, Principal
from app.security.crypto import cipher, verify_password, hash_password
from app.services import auth as service
from app.services.common import audit, public

router = APIRouter(prefix="/auth", tags=["Authentication"])


def origin_check(request):
    origin = request.headers.get("origin")
    if origin and origin not in settings().origins:
        raise HTTPException(403, "Origin is not allowed")


def csrf_check(request):
    origin_check(request)
    cookie, header = request.cookies.get("ls_csrf", ""), request.headers.get("x-csrf-token", "")
    if not cookie or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "CSRF token is missing or invalid")
    return cookie


def set_cookies(response, raw, csrf=None):
    secure = settings().production
    response.set_cookie(
        "ls_refresh", raw, max_age=settings().refresh_days * 86400, httponly=True, secure=secure, samesite="lax", path="/api/v1/auth"
    )
    if csrf:
        response.set_cookie(
            "ls_csrf", csrf, max_age=settings().refresh_days * 86400, httponly=False, secure=secure, samesite="lax", path="/"
        )


@router.post("/login", response_model=s.AuthResult)
def login(data: s.Login, request: Request, response: Response, db: Session = Depends(get_db)):
    origin_check(request)
    session, raw, csrf, user = service.login(db, data, request)
    set_cookies(response, raw, csrf)
    return {"access_token": service.access_token(session), "expires_in": settings().access_minutes * 60, "user": user}


@router.post("/refresh", response_model=s.AuthResult)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    csrf = csrf_check(request)
    session, raw, user = service.rotate(db, request.cookies.get("ls_refresh", ""), csrf)
    set_cookies(response, raw)
    return {"access_token": service.access_token(session), "expires_in": settings().access_minutes * 60, "user": user}


@router.post("/logout", response_model=s.Result)
def logout(request: Request, response: Response, p: Principal = Depends(current), db: Session = Depends(get_db)):
    csrf_check(request)
    p.session.revoked = True
    response.delete_cookie("ls_refresh", path="/api/v1/auth")
    response.delete_cookie("ls_csrf", path="/")
    audit(db, p, "auth.logout")
    return {"message": "Signed out"}


@router.get("/me")
def me(p: Principal = Depends(current), db: Session = Depends(get_db)):
    return service.identity(db, p.user, p.membership)


@router.post("/forgot-password", response_model=s.Result)
def forgot(data: s.EmailInput, request: Request, db: Session = Depends(get_db)):
    origin_check(request)
    service.throttle(db, "reset-ip:" + (request.client.host if request.client else "unknown"), 10)
    service.throttle(db, "reset-email:" + str(data.email).lower(), 4)
    user = db.scalar(select(User).where(User.email == str(data.email).lower(), User.active.is_(True)))
    if user:
        service.queue_token(db, user, "reset")
    return {"message": "If the account exists, reset instructions have been queued. Delivery requires configured SMTP."}


@router.post("/reset-password", response_model=s.Result)
def reset(data: s.ResetInput, request: Request, db: Session = Depends(get_db)):
    origin_check(request)
    service.throttle(db, "reset-use:" + (request.client.host if request.client else "unknown"), 15)
    service.use_token(db, data.token, data.password)
    return {"message": "Password updated. Sign in again."}


@router.post("/request-verification", response_model=s.Result)
def request_verification(p: Principal = Depends(current), db: Session = Depends(get_db)):
    service.throttle(db, "verify:" + p.user.id, 3)
    service.queue_token(db, p.user, "verify")
    return {"message": "Verification queued; delivery requires configured SMTP."}


@router.post("/verify-email", response_model=s.Result)
def verify(data: s.TokenInput, request: Request, db: Session = Depends(get_db)):
    service.throttle(db, "verify-use:" + (request.client.host if request.client else "unknown"), 15)
    service.use_token(db, data.token)
    return {"message": "Email verified"}


@router.post("/change-password", response_model=s.Result)
def change_password(data: s.PasswordChange, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, p.user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    p.user.password_hash = hash_password(data.password)
    db.execute(update(RefreshSession).where(RefreshSession.user_id == p.user.id).values(revoked=True))
    audit(db, p, "auth.password_changed")
    return {"message": "Password changed; all sessions revoked. Sign in again."}


@router.get("/sessions")
def sessions(p: Principal = Depends(current), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(RefreshSession).where(RefreshSession.user_id == p.user.id).order_by(RefreshSession.created_at.desc()).limit(100)
    )
    return [{**public(row, ["ip_hash", "membership_id"]), "current": row.id == p.session.id} for row in rows]


@router.delete("/sessions/{session_id}", response_model=s.Result)
def revoke_session(session_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    row = db.scalar(select(RefreshSession).where(RefreshSession.id == session_id, RefreshSession.user_id == p.user.id))
    if not row:
        raise HTTPException(404, "Session not found")
    row.revoked = True
    audit(db, p, "auth.session_revoked", row)
    return {"message": "Session revoked"}


@router.post("/mfa/setup")
def mfa_setup(data: s.MFASetup, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, p.user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if p.user.totp_secret:
        raise HTTPException(409, "MFA is already enabled")
    secret = pyotp.random_base32()
    p.user.totp_pending = cipher().encrypt(secret.encode()).decode()
    return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri(p.user.email, issuer_name="LearnSphere Enterprise")}


@router.post("/mfa/enable", response_model=s.Result)
def mfa_enable(data: s.MFAInput, p: Principal = Depends(current), db: Session = Depends(get_db)):
    service.throttle(db, "mfa:" + p.user.id, 8)
    if not verify_password(data.password, p.user.password_hash) or not service.totp_valid(p.user, data.code, pending=True):
        raise HTTPException(400, "Password or authenticator code is incorrect")
    p.user.totp_secret, p.user.totp_pending = p.user.totp_pending, None
    audit(db, p, "auth.mfa_enabled")
    return {"message": "MFA enabled"}


@router.post("/mfa/disable", response_model=s.Result)
def mfa_disable(data: s.MFAInput, p: Principal = Depends(current), db: Session = Depends(get_db)):
    service.throttle(db, "mfa:" + p.user.id, 8)
    if not verify_password(data.password, p.user.password_hash) or not service.totp_valid(p.user, data.code):
        raise HTTPException(400, "Password or authenticator code is incorrect")
    p.user.totp_secret = None
    db.execute(update(RefreshSession).where(RefreshSession.user_id == p.user.id).values(revoked=True))
    audit(db, p, "auth.mfa_disabled")
    return {"message": "MFA disabled and sessions revoked"}


@router.get("/profile")
def profile(p: Principal = Depends(current), db: Session = Depends(get_db)):
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == p.user.id))
    return {
        **service.identity(db, p.user, p.membership),
        "bio": profile.bio if profile else "",
        "timezone": profile.timezone if profile else "UTC",
    }


@router.put("/profile", response_model=s.Result)
def update_profile(data: s.ProfileInput, p: Principal = Depends(current), db: Session = Depends(get_db)):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Unknown timezone") from None
    p.user.name = data.name
    row = db.scalar(select(UserProfile).where(UserProfile.user_id == p.user.id))
    if row is None:
        row = UserProfile(user_id=p.user.id)
        db.add(row)
    row.bio, row.timezone = data.bio, data.timezone
    audit(db, p, "users.profile_updated")
    return {"message": "Profile updated"}
