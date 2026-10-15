from dataclasses import dataclass
import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import now
from app.db.session import get_db
from app.models import User, Membership, Role, UserRole, RolePermission, RefreshSession, Institution, Course, CourseInstructor, Enrollment

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    membership: Membership
    roles: set[str]
    permissions: set[str]
    tenant_id: str | None
    session: RefreshSession

    @property
    def super(self):
        return "super_admin" in self.roles

    @property
    def manager(self):
        return bool(self.roles & {"super_admin", "institution_admin", "coordinator"})

    def require(self, code):
        if code not in self.permissions:
            raise HTTPException(403, f"Permission required: {code}")


def current(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_institution_id: str | None = Header(default=None),
):
    if not credentials:
        raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings().secret_key,
            algorithms=["HS256"],
            audience="learnsphere",
            issuer="learnsphere",
            options={"require": ["exp", "iat", "sub", "sid"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired or invalid") from None
    session = db.get(RefreshSession, claims["sid"])
    if not session or session.revoked or session.expires_at <= now() or session.user_id != claims["sub"]:
        raise HTTPException(401, "Session revoked or expired")
    user = db.get(User, session.user_id)
    membership = db.get(Membership, session.membership_id)
    if not user or not user.active or not membership:
        raise HTTPException(401, "Account unavailable")
    roles = set(db.scalars(select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.membership_id == membership.id)))
    permissions = set(
        db.scalars(
            select(RolePermission.permission_code)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.membership_id == membership.id)
        )
    )
    tenant_id = membership.institution_id
    if x_institution_id:
        if "super_admin" not in roles and x_institution_id != tenant_id:
            raise HTTPException(403, "Institution access denied")
        tenant_id = x_institution_id
    if tenant_id:
        institution = db.get(Institution, tenant_id)
        if not institution or not institution.active:
            raise HTTPException(403, "Institution unavailable")
    if (
        settings().require_privileged_mfa
        and roles & {"super_admin", "institution_admin", "coordinator", "instructor"}
        and not user.totp_secret
        and not request.url.path.startswith("/api/v1/auth/")
    ):
        raise HTTPException(403, "Institution policy requires authenticator setup in Profile & security")
    return Principal(user, membership, roles, permissions, tenant_id, session)


def permit(code):
    def dependency(p: Principal = Depends(current)):
        p.require(code)
        return p

    return dependency


def tenant(p):
    if not p.tenant_id:
        raise HTTPException(400, "Select an institution first")
    return p.tenant_id


def scoped(db, model, entity_id, p):
    obj = db.scalar(select(model).where(model.id == entity_id, model.institution_id == tenant(p)))
    if obj is None:
        raise HTTPException(404, "Record not found")
    return obj


def member(db, user_id, p):
    m = db.scalar(select(Membership).where(Membership.user_id == user_id, Membership.institution_id == tenant(p)))
    u = db.get(User, user_id)
    if not m or not u or not u.active:
        raise HTTPException(404, "Institution member not found")
    return m


def roles_for(db, membership_id):
    return set(db.scalars(select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.membership_id == membership_id)))


def active_enrollment(db, p, course_id, user_id=None):
    e = db.scalar(
        select(Enrollment).where(
            Enrollment.institution_id == tenant(p), Enrollment.course_id == course_id, Enrollment.user_id == (user_id or p.user.id)
        )
    )
    if not e or e.status not in {"active", "completed"} or (e.starts_at and now() < e.starts_at) or (e.ends_at and now() > e.ends_at):
        raise HTTPException(403, "An active enrollment is required")
    return e


def course_access(db, p, course_id, mode="read"):
    course = scoped(db, Course, course_id, p)
    if p.manager:
        return course
    assignment = db.get(CourseInstructor, (course.id, p.user.id))
    if assignment:
        if mode == "grade" and not assignment.can_grade:
            raise HTTPException(403, "Grading has not been delegated for this course")
        if mode == "write" and "instructor" not in p.roles:
            raise HTTPException(403, "Only an assigned instructor may author content")
        if mode == "discuss" and not assignment.can_discuss:
            raise HTTPException(403, "Discussion permission is not delegated")
        return course
    if mode != "read":
        raise HTTPException(403, "Course assignment required")
    active_enrollment(db, p, course.id)
    return course


def editable(course):
    if course.status not in {"draft", "in_review"}:
        raise HTTPException(409, "Published revisions are immutable. Create a new revision to change content.")


def visible_course_ids(db, p):
    if p.manager or "auditor" in p.roles:
        return select(Course.id).where(Course.institution_id == tenant(p))
    if p.roles & {"instructor", "teaching_assistant"}:
        return select(CourseInstructor.course_id).where(CourseInstructor.user_id == p.user.id)
    return select(Enrollment.course_id).where(Enrollment.institution_id == tenant(p), Enrollment.user_id == p.user.id)
