from datetime import timedelta
import pyotp
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable
from alembic import command
from alembic.config import Config
from app import cli
from app.db.base import Base, now
from app.db.session import SessionLocal, engine
from app.models import AuditEvent, Course, Institution, User, Membership, UserRole, Role
from app.services.auth import totp_valid
from app.security.crypto import cipher
from conftest import publish


def test_migration_model_parity_and_portable_ddl():
    command.check(Config("alembic.ini"))
    for dialect in [sqlite.dialect(), postgresql.dialect()]:
        for table in Base.metadata.sorted_tables:
            assert str(CreateTable(table).compile(dialect=dialect))
            for index in table.indexes:
                assert str(CreateIndex(index).compile(dialect=dialect))
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert not connection.execute(text("PRAGMA foreign_key_check")).all()


def test_secure_bootstrap_and_account_lockout(env, monkeypatch):
    clients, ids = env
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "SecureBootstrap2026!")
    cli.bootstrap("root@example.com", "New Platform Owner")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "root@example.com"))
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
        role = db.scalar(select(Role.name).join(UserRole).where(UserRole.membership_id == membership.id))
        assert membership.institution_id is None and role == "super_admin"
        assert user.password_hash.startswith("$argon2id$") and user.verified
    student = clients["student"]
    for _ in range(5):
        assert (
            student.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "IncorrectPassword2026!"}).status_code
            == 401
        )
    assert student.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "StrongPassword2026!"}).status_code == 401
    with SessionLocal() as db:
        assert db.get(User, ids["student"]).locked_until > now()
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "auth.login_failed"))


def test_totp_confirmation_replay_and_session_security(env):
    clients, ids = env
    c = clients["admin"]
    assert c.post("/api/v1/auth/mfa/setup", json={"current_password": "WrongPassword2026!"}).status_code == 400
    result = c.post("/api/v1/auth/mfa/setup", json={"current_password": "StrongPassword2026!"})
    assert result.status_code == 200, result.text
    secret = result.json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert c.post("/api/v1/auth/mfa/enable", json={"password": "StrongPassword2026!", "code": code}).status_code == 200
    assert c.get("/api/v1/auth/me").json()["mfa_enabled"]
    assert c.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "StrongPassword2026!"}).status_code == 401
    with SessionLocal() as db:
        user = db.get(User, ids["admin"])
        assert user.totp_secret != secret
        assert cipher().decrypt(user.totp_secret.encode()).decode() == secret
        assert not totp_valid(user, code)  # Already consumed during enrollment.
    session = clients["student"].get("/api/v1/auth/sessions").json()[0]
    assert c.delete("/api/v1/auth/sessions/" + session["id"]).status_code == 404
    assert (
        clients["student"]
        .post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": clients["student"].cookies.get("ls_csrf"), "Origin": "https://attacker.example"},
        )
        .status_code
        == 403
    )


def test_manual_objective_grading_and_delegated_ta(env, course):
    clients, ids = env
    t, student, ta = clients["teacher"], clients["student"], clients["ta"]
    c, _, _ = course
    items = [
        {
            "kind": "multiple",
            "prompt": "Choose both safe practices",
            "points": 2,
            "negative_points": 1,
            "options": [{"text": "Authorize", "correct": True}, {"text": "Validate", "correct": True}, {"text": "Trust input"}],
        },
        {
            "kind": "boolean",
            "prompt": "Client controls are sufficient",
            "points": 1,
            "negative_points": 1,
            "options": [{"text": "True"}, {"text": "False", "correct": True}],
        },
        {"kind": "short", "prompt": "Explain isolation", "points": 3},
    ]
    questions = []
    for item in items:
        r = t.post("/api/v1/questions", json={"course_id": c["id"], **item})
        assert r.status_code == 201, r.text
        questions.append(r.json())
    quiz = t.post(
        "/api/v1/quizzes",
        json={"course_id": c["id"], "title": "Mixed assessment", "question_ids": [q["id"] for q in questions], "release_policy": "manual"},
    ).json()
    t.post("/api/v1/courses/" + c["id"] + "/instructors", json={"user_id": ids["ta"], "can_grade": False})
    publish(t, c["id"])
    student.post("/api/v1/enrollments", json={"course_id": c["id"]})
    attempt = student.post("/api/v1/quizzes/" + quiz["id"] + "/start").json()
    answers = [
        {"question_id": questions[0]["id"], "selected": [o["id"] for o in questions[0]["options"] if o["correct"]]},
        {"question_id": questions[1]["id"], "selected": [o["id"] for o in questions[1]["options"] if not o["correct"]]},
        {"question_id": questions[2]["id"], "text": "Every query is scoped to the authenticated membership."},
    ]
    student.put("/api/v1/attempts/" + attempt["id"] + "/answers", json={"answers": answers})
    result = student.post("/api/v1/attempts/" + attempt["id"] + "/submit").json()
    assert result["status"] == "pending_review" and result["score"] is None
    short = next(a for a in result["answers"] if a["question_id"] == questions[2]["id"])
    path = "/api/v1/attempts/" + attempt["id"] + "/answers/" + short["id"] + "/grade"
    assert ta.put(path, json={"marks": 3}).status_code == 403
    assert student.put(path, json={"marks": 3}).status_code == 403
    assert t.put(path, json={"marks": 4}).status_code == 422
    t.post("/api/v1/courses/" + c["id"] + "/instructors", json={"user_id": ids["ta"], "can_grade": True})
    grade = ta.put(path, json={"marks": 3, "feedback": "Accurate boundaries."})
    assert grade.status_code == 200, grade.text
    assert grade.json()["score"] == 4  # 2 correct - 1 negative + 3 manual.
    assert student.get("/api/v1/attempts/" + attempt["id"]).json()["score"] is None
    t.post("/api/v1/quizzes/" + quiz["id"] + "/release")
    assert student.get("/api/v1/attempts/" + attempt["id"]).json()["score"] == 4
    assert clients["peer"].get("/api/v1/attempts/" + attempt["id"]).status_code in (403, 404)


def test_rubric_versions_release_and_late_policy(env, course):
    clients, _ = env
    t, student = clients["teacher"], clients["student"]
    c, _, _ = course
    body = {
        "course_id": c["id"],
        "title": "Design task",
        "instructions": "Explain decisions",
        "max_submissions": 2,
        "rubric": [{"title": "Accuracy", "max_marks": 60}, {"title": "Clarity", "max_marks": 40}],
    }
    assignment = t.post("/api/v1/assignments", json=body).json()
    closed = t.post(
        "/api/v1/assignments",
        json={
            "course_id": c["id"],
            "title": "Closed task",
            "instructions": "Past deadline",
            "due_at": (now() - timedelta(days=1)).isoformat(),
        },
    ).json()
    publish(t, c["id"])
    student.post("/api/v1/enrollments", json={"course_id": c["id"]})
    assert student.post("/api/v1/assignments/" + closed["id"] + "/submit", json={"text": "Late"}).status_code == 409
    path = "/api/v1/assignments/" + assignment["id"] + "/submit"
    a = student.post(path, json={"text": "First answer"}).json()
    b = student.post(path, json={"text": "Improved answer"}).json()
    assert a["id"] != b["id"] and b["version"] == 2
    assert student.post(path, json={"text": "Too many"}).status_code == 409
    grade_path = "/api/v1/submissions/" + b["id"] + "/grade"
    assert t.put(grade_path, json={"marks": 90}).status_code == 422
    scores = {criterion["id"]: criterion["max_marks"] - 5 for criterion in assignment["rubric"]}
    payload = {"marks": 90, "rubric_scores": scores, "feedback": "Strong evidence", "released": False}
    assert t.put(grade_path, json=payload).status_code == 200
    assert student.get("/api/v1/grades").json()["total"] == 0
    assert t.put(grade_path, json=payload | {"released": True}).status_code == 200
    assert student.get("/api/v1/grades").json()["items"][0]["grade"]["marks"] == 90


def test_draft_editing_publication_capacity_and_revision_quota(env, course):
    clients, ids = env
    t, student, peer, admin = clients["teacher"], clients["student"], clients["peer"], clients["admin"]
    c, section, _ = course
    assert t.delete("/api/v1/sections/" + section["id"]).status_code == 409
    assert t.put("/api/v1/sections/" + section["id"], json={"title": "Updated section", "position": 1}).status_code == 200
    question_body = {"course_id": c["id"], "kind": "short", "prompt": "Draft", "points": 1}
    q = t.post("/api/v1/questions", json=question_body).json()
    assert t.put("/api/v1/questions/" + q["id"], json=question_body | {"prompt": "Revised prompt"}).status_code == 200
    quiz_body = {"course_id": c["id"], "title": "Draft quiz", "question_ids": [q["id"]]}
    quiz = t.post("/api/v1/quizzes", json=quiz_body).json()
    assert t.delete("/api/v1/questions/" + q["id"]).status_code == 409
    assert t.put("/api/v1/quizzes/" + quiz["id"], json=quiz_body | {"time_limit_minutes": 5}).status_code == 200
    assert student.get("/api/v1/quizzes/" + quiz["id"] + "/author").status_code == 403
    assert t.delete("/api/v1/quizzes/" + quiz["id"]).status_code == 200
    assert t.delete("/api/v1/questions/" + q["id"]).status_code == 200
    resource = t.post("/api/v1/files", data={"course_id": c["id"]}, files={"file": ("guide.txt", b"A" * 100, "text/plain")})
    assert resource.status_code == 201
    with SessionLocal.begin() as db:
        db.get(Course, c["id"]).max_learners = 1
    publish(t, c["id"])
    assert student.post("/api/v1/enrollments", json={"course_id": c["id"]}).json()["status"] == "active"
    assert peer.post("/api/v1/enrollments", json={"course_id": c["id"]}).json()["status"] == "waitlisted"
    assert t.put("/api/v1/sections/" + section["id"], json={"title": "Unsafe change", "position": 1}).status_code == 409
    with SessionLocal.begin() as db:
        db.get(Institution, ids["tenant"]).storage_quota_mb = 0
    assert t.post("/api/v1/courses/" + c["id"] + "/revision").status_code == 413
    assert admin.get("/api/v1/courses").json()["total"] == 1


def test_thumbnail_catalog_authorization_and_revision_copy(env, course):
    import io
    from PIL import Image

    clients, _ = env
    teacher, student, outsider = clients["teacher"], clients["student"], clients["outsider"]
    course_id = course[0]["id"]
    image = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 80, 90)).save(image, format="PNG")
    asset = teacher.post(
        "/api/v1/files", data={"course_id": course_id}, files={"file": ("cover.png", image.getvalue(), "image/png")}
    ).json()
    url = "/api/v1/courses/" + course_id + "/thumbnail"
    assert teacher.put(url, json={"file_id": asset["id"]}).status_code == 200
    assert student.get(url).status_code == 404
    assert teacher.get("/api/v1/courses/authoring-options").status_code == 200
    publish(teacher, course_id)
    assert student.get(url).content == image.getvalue()
    assert outsider.get(url).status_code == 404
    assert teacher.put(url, json={"file_id": None}).status_code == 409
    revision = teacher.post("/api/v1/courses/" + course_id + "/revision").json()
    assert revision["thumbnail_id"] != asset["id"]
    assert teacher.get("/api/v1/courses/" + revision["id"] + "/thumbnail").content == image.getvalue()
