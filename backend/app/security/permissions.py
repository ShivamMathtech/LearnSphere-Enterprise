from sqlalchemy import select
from app.models import Permission, Role, RolePermission

LEARNER = {
    "courses.read",
    "enrollments.create",
    "progress.update",
    "assessments.attempt",
    "submissions.create",
    "discussions.write",
    "certificates.read",
    "profile.update",
}
INSTRUCTOR = {
    "courses.read",
    "courses.create",
    "courses.update",
    "courses.publish",
    "courses.assign_assistant",
    "assessments.create",
    "assessments.grade",
    "enrollments.read",
    "reports.read",
    "reports.export",
    "attendance.manage",
    "discussions.write",
    "announcements.create",
    "messages.create",
    "profile.update",
    "files.create",
    "certificates.read",
}
ADMIN = INSTRUCTOR | {
    "users.read",
    "users.create",
    "users.update",
    "users.disable",
    "roles.read",
    "roles.assign",
    "academic.read",
    "academic.manage",
    "courses.manage",
    "enrollments.manage",
    "enrollments.create",
    "audit.read",
    "settings.manage",
    "certificates.manage",
    "imports.manage",
}
ROLE_PERMISSIONS = {
    "super_admin": ADMIN | {"institutions.manage", "system.manage"},
    "institution_admin": ADMIN,
    "coordinator": {
        "users.read",
        "academic.read",
        "academic.manage",
        "courses.read",
        "courses.manage",
        "enrollments.create",
        "enrollments.manage",
        "enrollments.read",
        "reports.read",
        "reports.export",
        "attendance.manage",
        "profile.update",
    },
    "instructor": INSTRUCTOR,
    "teaching_assistant": {"courses.read", "assessments.grade", "enrollments.read", "discussions.write", "profile.update"},
    "student": LEARNER,
    "auditor": {"reports.read", "reports.export", "audit.read", "profile.update"},
}
ALL_PERMISSIONS = set.union(*ROLE_PERMISSIONS.values())


def seed_permissions(db):
    for code in sorted(ALL_PERMISSIONS):
        if not db.get(Permission, code):
            db.add(Permission(code=code, description=code.replace(".", ": ").replace("_", " ")))
    db.flush()
    for name, permissions in ROLE_PERMISSIONS.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if not role:
            role = Role(name=name, description=name.replace("_", " ").title())
            db.add(role)
            db.flush()
        for code in sorted(permissions):
            if not db.get(RolePermission, (role.id, code)):
                db.add(RolePermission(role_id=role.id, permission_code=code))
    db.flush()
