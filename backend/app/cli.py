import argparse
import getpass
import json
import secrets
from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    User,
    Institution,
    Membership,
    Role,
    UserRole,
    Course,
    CourseSection,
    Lesson,
    CourseInstructor,
    CourseVersion,
    Department,
)
from app.security.crypto import hash_password
from app.security.permissions import seed_permissions


def add_user(db, email, name, password, role_name, institution_id):
    user = User(email=email.lower(), name=name, password_hash=hash_password(password), verified=True)
    db.add(user)
    db.flush()
    membership = Membership(user_id=user.id, institution_id=institution_id)
    db.add(membership)
    db.flush()
    role = db.scalar(select(Role).where(Role.name == role_name))
    db.add(UserRole(membership_id=membership.id, role_id=role.id))
    return user


def bootstrap(email, name):
    password = getpass.getpass("New super administrator password (12+ characters): ")
    if getpass.getpass("Confirm password: ") != password:
        raise SystemExit("Passwords differ")
    with SessionLocal.begin() as db:
        seed_permissions(db)
        if db.scalar(select(User.id).where(User.email == email.lower())):
            raise SystemExit("That account already exists; no changes made")
        add_user(db, email, name, password, "super_admin", None)
    print("Super administrator created. Sign in and create an institution.")


def seed_demo():
    if settings().app_env != "development" or not settings().demo_enabled:
        raise SystemExit("Demo seed requires APP_ENV=development and DEMO_ENABLED=true")
    with SessionLocal.begin() as db:
        seed_permissions(db)
        if db.scalar(select(Institution.id).where(Institution.slug == "northbridge-demo")):
            print("Demo data already exists; nothing reset.")
            return
        inst = Institution(name="Northbridge Institute · Demo", slug="northbridge-demo")
        db.add(inst)
        db.flush()
        db.add(Department(institution_id=inst.id, name="Computer Science", code="CSE"))
        password = "LearnSphere2026!"
        accounts = [
            ("admin", "Alex Morgan", "institution_admin"),
            ("faculty", "Dr. Maya Chen", "instructor"),
            ("student", "Jordan Lee", "student"),
            ("coordinator", "Sam Rivera", "coordinator"),
            ("assistant", "Taylor Kim", "teaching_assistant"),
            ("auditor", "Casey Patel", "auditor"),
        ]
        users = {}
        for login, name, role in accounts:
            users[login] = add_user(db, login + "@example.com", name, password, role, inst.id)
        add_user(db, "super@example.com", "Platform Administrator", password, "super_admin", None)
        topics = [
            (
                "Foundations of Computer Science",
                "foundations-computer-science",
                "Understand algorithms, representations, and the building blocks of software.",
                "Explain computational thinking and implement a small algorithm.",
                "beginner",
            ),
            (
                "Designing Reliable APIs",
                "designing-reliable-apis",
                "Build service boundaries, validate input and reason about failure.",
                "Design a versioned API and evaluate authorization boundaries.",
                "intermediate",
            ),
            (
                "Applied Data Literacy",
                "applied-data-literacy",
                "Read data critically and communicate evidence responsibly.",
                "Interpret distributions and identify misleading summaries.",
                "beginner",
            ),
        ]
        for index, (title, slug, description, objectives, difficulty) in enumerate(topics):
            c = Course(
                institution_id=inst.id,
                title=title,
                slug=slug,
                description=description,
                objectives=objectives,
                difficulty=difficulty,
                status="published",
                created_by=users["faculty"].id,
                estimated_minutes=45 + index * 30,
            )
            db.add(c)
            db.flush()
            db.add(CourseInstructor(course_id=c.id, user_id=users["faculty"].id, can_grade=True))
            section = CourseSection(institution_id=inst.id, course_id=c.id, title="Getting started", position=0)
            db.add(section)
            db.flush()
            for position, heading in enumerate(["Core ideas", "Guided practice", "Reflect and apply"]):
                db.add(
                    Lesson(
                        institution_id=inst.id,
                        course_id=c.id,
                        section_id=section.id,
                        title=heading,
                        position=position,
                        content=f"{heading}\n\n{description}\n\nLearning objective: {objectives}\n\nPractice: Write a concrete example, explain your reasoning, then identify one limitation.\n\nThis is an explicitly labeled development course. Replace the lesson with your institutional content before real teaching.",
                    )
                )
            db.flush()
            from app.services.learning import course_outline

            db.add(
                CourseVersion(
                    institution_id=inst.id, course_id=c.id, version=1, snapshot={"title": c.title, "sections": course_outline(db, c)}
                )
            )
        print("Development seed created. Accounts: admin, faculty, student, coordinator, assistant, auditor, super @example.com")
        print("Development-only password: LearnSphere2026!")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--email", required=True)
    boot.add_argument("--name", required=True)
    sub.add_parser("seed-demo")
    sub.add_parser("seed-permissions")
    sub.add_parser("generate-secrets")
    sub.add_parser("worker")
    sub.add_parser("retention")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap(args.email, args.name)
    elif args.command == "seed-demo":
        seed_demo()
    elif args.command == "seed-permissions":
        with SessionLocal.begin() as db:
            seed_permissions(db)
    elif args.command == "generate-secrets":
        from cryptography.fernet import Fernet

        print("SECRET_KEY=" + secrets.token_urlsafe(64))
        print("ENCRYPTION_KEY=" + Fernet.generate_key().decode())
    elif args.command == "worker":
        from app.tasks.worker import run_once

        print(json.dumps(run_once()))
    elif args.command == "retention":
        from app.tasks.worker import retention

        retention()
        print("Expired records removed according to configured retention.")


if __name__ == "__main__":
    main()
