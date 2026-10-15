from app.services.common import required
import csv
import io
import hmac
from dataclasses import replace
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import (
    Institution,
    User,
    Membership,
    Role,
    UserRole,
    Permission,
    RolePermission,
    Department,
    Program,
    AcademicYear,
    Semester,
    Cohort,
    CourseCategory,
    CourseOffering,
    Course,
    CohortMember,
    RefreshSession,
    SystemSetting,
)
from app.schemas import contracts as s
from app.security.access import Principal, permit, scoped, member, roles_for, tenant
from app.services.common import public, page, audit, check_dates
from app.services.users import create_user, authorize_role, preview_import
from app.api.deps import Pagination

router = APIRouter(tags=["Administration"])


def user_view(db, u, institution_id):
    m = db.scalar(select(Membership).where(Membership.user_id == u.id, Membership.institution_id == institution_id))
    return {**public(u), "roles": sorted(roles_for(db, m.id)), "identifier": m.identifier, "department_id": m.department_id}


@router.get("/users", response_model=s.Page)
def users(
    role: str | None = None,
    active: bool | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("users.read")),
    db: Session = Depends(get_db),
):
    query = select(User).join(Membership).where(Membership.institution_id == tenant(p))
    if role:
        query = query.where(Membership.id.in_(select(UserRole.membership_id).join(Role).where(Role.name == role)))
    if active is not None:
        query = query.where(User.active.is_(active))
    return page(db, q.apply(query, User, User.name), q.page, q.page_size, lambda u: user_view(db, u, p.tenant_id))


@router.post("/users", response_model=s.Record, status_code=201)
def add_user(data: s.UserCreate, p: Principal = Depends(permit("users.create")), db: Session = Depends(get_db)):
    user, delivery = create_user(db, p, data)
    db.flush()
    return {**user_view(db, user, p.tenant_id), "email_delivery": delivery}


@router.patch("/users/{user_id}", response_model=s.Record)
def edit_user(user_id: str, data: s.UserUpdate, p: Principal = Depends(permit("users.update")), db: Session = Depends(get_db)):
    m = member(db, user_id, p)
    u = required(db, User, user_id)
    target_roles = roles_for(db, m.id)
    if target_roles & {"institution_admin", "super_admin"} and not p.super:
        raise HTTPException(403, "Only super administrators can change administrator accounts")
    if data.active is False:
        p.require("users.disable")
        if u.id == p.user.id:
            raise HTTPException(409, "You cannot disable yourself")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "department_id" and value:
            scoped(db, Department, value, p)
        if key in {"name", "active"}:
            if value is None:
                raise HTTPException(422, f"{key} cannot be null")
            setattr(u, key, value)
        else:
            setattr(m, key, value)
    if not u.active:
        db.execute(update(RefreshSession).where(RefreshSession.user_id == u.id).values(revoked=True))
    audit(db, p, "users.updated", u, {"fields": list(data.model_fields_set)})
    db.flush()
    return user_view(db, u, p.tenant_id)


@router.put("/users/{user_id}/role", response_model=s.Result)
def assign_role(user_id: str, data: s.RoleAssign, p: Principal = Depends(permit("roles.assign")), db: Session = Depends(get_db)):
    authorize_role(p, data.role)
    m = member(db, user_id, p)
    if user_id == p.user.id or ("institution_admin" in roles_for(db, m.id) and not p.super):
        raise HTTPException(403, "This role change requires a super administrator")
    role = db.scalar(select(Role).where(Role.name == data.role))
    if role is None:
        raise HTTPException(409, "Roles are not initialized; run the permissions seed")
    db.execute(delete(UserRole).where(UserRole.membership_id == m.id))
    db.add(UserRole(membership_id=m.id, role_id=role.id))
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user_id).values(revoked=True))
    audit(db, p, "roles.assigned", m, {"role": data.role})
    return {"message": "Role updated; existing sessions revoked"}


@router.get("/roles")
def roles(p: Principal = Depends(permit("roles.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Role).order_by(Role.name))
    return [
        {**public(r), "permissions": list(db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == r.id)))}
        for r in rows
    ]


@router.get("/permissions")
def permissions(p: Principal = Depends(permit("roles.read")), db: Session = Depends(get_db)):
    return [public(r) for r in db.scalars(select(Permission).order_by(Permission.code))]


@router.get("/institutions", response_model=s.Page)
def institutions(q: Pagination = Depends(), p: Principal = Depends(permit("institutions.manage")), db: Session = Depends(get_db)):
    return page(db, q.apply(select(Institution), Institution, Institution.name), q.page, q.page_size)


@router.post("/institutions", response_model=s.Record, status_code=201)
def add_institution(data: s.InstitutionInput, p: Principal = Depends(permit("institutions.manage")), db: Session = Depends(get_db)):
    row = Institution(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, replace(p, tenant_id=row.id), "institutions.created", row)
    return public(row)


@router.put("/institutions/{institution_id}", response_model=s.Record)
def edit_institution(
    institution_id: str, data: s.InstitutionInput, p: Principal = Depends(permit("institutions.manage")), db: Session = Depends(get_db)
):
    row = required(db, Institution, institution_id)
    if not row:
        raise HTTPException(404, "Institution not found")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    audit(db, replace(p, tenant_id=row.id), "institutions.updated", row)
    db.flush()
    return public(row)


@router.post("/institutions/{institution_id}/administrator", response_model=s.Record, status_code=201)
def add_admin(
    institution_id: str, data: s.UserCreate, p: Principal = Depends(permit("institutions.manage")), db: Session = Depends(get_db)
):
    if not required(db, Institution, institution_id):
        raise HTTPException(404, "Institution not found")
    data.role = "institution_admin"
    user, delivery = create_user(db, replace(p, tenant_id=institution_id), data)
    return {**public(user), "email_delivery": delivery}


ACADEMIC = {
    "departments": (Department, {"name", "code"}, {"code"}),
    "programs": (Program, {"name", "code", "department_id", "level"}, {"code"}),
    "academic-years": (AcademicYear, {"name", "starts_at", "ends_at"}, {"starts_at", "ends_at"}),
    "semesters": (Semester, {"name", "academic_year_id"}, {"academic_year_id"}),
    "cohorts": (Cohort, {"name", "code", "program_id"}, {"code"}),
    "course-categories": (CourseCategory, {"name"}, set()),
    "course-offerings": (CourseOffering, {"name", "course_id", "cohort_id", "semester_id"}, {"course_id", "cohort_id"}),
}
REFERENCES = {
    "department_id": Department,
    "program_id": Program,
    "academic_year_id": AcademicYear,
    "semester_id": Semester,
    "cohort_id": Cohort,
    "course_id": Course,
}


def register_academic(path, model, fields, required):
    def validate(data, db, p):
        values = data.model_dump(include=data.model_fields_set)
        if values.keys() - fields:
            raise HTTPException(422, "Unsupported fields for this academic entity")
        if any(values.get(key) in (None, "") for key in required):
            raise HTTPException(422, "Required fields: " + ", ".join(sorted(required)))
        for key, cls in REFERENCES.items():
            if values.get(key):
                scoped(db, cls, values[key], p)
        check_dates(data.starts_at, data.ends_at)
        return values

    def list_rows(q: Pagination = Depends(), p: Principal = Depends(permit("academic.read")), db: Session = Depends(get_db)):
        return page(db, q.apply(select(model).where(model.institution_id == tenant(p)), model, model.name), q.page, q.page_size)

    def create(data: s.AcademicInput, p: Principal = Depends(permit("academic.manage")), db: Session = Depends(get_db)):
        row = model(institution_id=tenant(p), **validate(data, db, p))
        db.add(row)
        db.flush()
        audit(db, p, path + ".created", row)
        return public(row)

    def edit(entity_id: str, data: s.AcademicInput, p: Principal = Depends(permit("academic.manage")), db: Session = Depends(get_db)):
        row = scoped(db, model, entity_id, p)
        for key, value in validate(data, db, p).items():
            setattr(row, key, value)
        audit(db, p, path + ".updated", row)
        db.flush()
        return public(row)

    def remove(entity_id: str, p: Principal = Depends(permit("academic.manage")), db: Session = Depends(get_db)):
        row = scoped(db, model, entity_id, p)
        audit(db, p, path + ".deleted", row)
        db.delete(row)
        db.flush()
        return {"message": "Deleted"}

    router.add_api_route("/" + path, list_rows, methods=["GET"], response_model=s.Page, name="list_" + path)
    router.add_api_route("/" + path, create, methods=["POST"], response_model=s.Record, status_code=201, name="create_" + path)
    router.add_api_route("/" + path + "/{entity_id}", edit, methods=["PUT"], response_model=s.Record, name="edit_" + path)
    router.add_api_route("/" + path + "/{entity_id}", remove, methods=["DELETE"], response_model=s.Result, name="delete_" + path)


for _path, (_model, _fields, _required) in ACADEMIC.items():
    register_academic(_path, _model, _fields, _required)


@router.post("/cohorts/{cohort_id}/members/{user_id}", response_model=s.Result)
def add_cohort_member(cohort_id: str, user_id: str, p: Principal = Depends(permit("academic.manage")), db: Session = Depends(get_db)):
    scoped(db, Cohort, cohort_id, p)
    membership = member(db, user_id, p)
    if "student" not in roles_for(db, membership.id):
        raise HTTPException(422, "Only learner memberships can join a cohort")
    if not db.get(CohortMember, (cohort_id, user_id)):
        db.add(CohortMember(cohort_id=cohort_id, user_id=user_id))
        audit(db, p, "cohorts.member_added", detail={"cohort_id": cohort_id, "user_id": user_id})
    return {"message": "Cohort membership saved"}


@router.post("/users/import/preview")
def import_preview(data: s.ImportInput, p: Principal = Depends(permit("imports.manage")), db: Session = Depends(get_db)):
    return preview_import(db, p, data)


@router.post("/users/import/commit")
def import_commit(data: s.ImportInput, p: Principal = Depends(permit("imports.manage")), db: Session = Depends(get_db)):
    result = preview_import(db, p, data)
    if not data.preview_hash or not hmac.compare_digest(data.preview_hash, result["preview_hash"]):
        raise HTTPException(409, "Preview this exact import before committing")
    if result["errors"]:
        raise HTTPException(422, "Resolve all row errors before import; no rows have been imported")
    for row in result["rows"]:
        create_user(db, p, s.UserCreate(**{k: v for k, v in row.items() if k != "line"}))
    db.flush()
    audit(db, p, "users.imported", detail={"count": len(result["rows"])})
    return {"imported": len(result["rows"]), "email_delivery": "queued or unconfigured; check system status"}


@router.post("/users/import/errors.csv")
def import_errors(data: s.ImportInput, p: Principal = Depends(permit("imports.manage")), db: Session = Depends(get_db)):
    result = preview_import(db, p, data)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["line", "error"])
    writer.writeheader()
    writer.writerows(result["errors"])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="import-errors.csv"'})


@router.get("/settings")
def settings_list(p: Principal = Depends(permit("settings.manage")), db: Session = Depends(get_db)):
    return [public(row) for row in db.scalars(select(SystemSetting).where(SystemSetting.institution_id == tenant(p)))]


@router.put("/settings/{key}", response_model=s.Record)
def update_setting(key: str, data: s.SettingInput, p: Principal = Depends(permit("settings.manage")), db: Session = Depends(get_db)):
    allowed = {"certificate": {"heading", "issuer", "footer"}, "branding": {"display_name", "accent", "support_email"}}
    if key not in allowed or set(data.value) - allowed[key] or any(not isinstance(v, str) or len(v) > 300 for v in data.value.values()):
        raise HTTPException(422, "Unsupported setting key or value")
    row = db.scalar(select(SystemSetting).where(SystemSetting.institution_id == tenant(p), SystemSetting.key == key))
    if not row:
        row = SystemSetting(institution_id=tenant(p), key=key, value={})
        db.add(row)
    row.value = data.value
    db.flush()
    audit(db, p, "settings.updated", row)
    return public(row)


@router.get("/institution-branding")
def branding(p: Principal = Depends(permit("profile.update")), db: Session = Depends(get_db)):
    if not p.tenant_id:
        return {"display_name": "Platform workspace"}
    institution = required(db, Institution, tenant(p))
    setting = db.scalar(select(SystemSetting).where(SystemSetting.institution_id == tenant(p), SystemSetting.key == "branding"))
    return {"display_name": institution.name, **(setting.value if setting else {})}


@router.get("/cohorts/{cohort_id}/members", response_model=s.Page)
def cohort_members(
    cohort_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("academic.read")), db: Session = Depends(get_db)
):
    scoped(db, Cohort, cohort_id, p)
    query = select(User).join(CohortMember, CohortMember.user_id == User.id).where(CohortMember.cohort_id == cohort_id)
    return page(db, q.apply(query, User, User.name), q.page, q.page_size, lambda u: {"id": u.id, "name": u.name, "email": u.email})


@router.delete("/cohorts/{cohort_id}/members/{user_id}", response_model=s.Result)
def remove_cohort_member(cohort_id: str, user_id: str, p: Principal = Depends(permit("academic.manage")), db: Session = Depends(get_db)):
    scoped(db, Cohort, cohort_id, p)
    row = db.get(CohortMember, (cohort_id, user_id))
    if row:
        db.delete(row)
    audit(db, p, "cohorts.member_removed", detail={"cohort_id": cohort_id, "user_id": user_id})
    return {"message": "Cohort membership removed"}
