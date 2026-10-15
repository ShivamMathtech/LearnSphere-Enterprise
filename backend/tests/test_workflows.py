from datetime import timedelta
from app.db.base import now
from app.db.session import SessionLocal
from app.models import QuizAttempt, User
from app.services.auth import queue_token
from conftest import publish


def test_end_to_end_administration_learning_assessment_certificate(env, course):
    clients, ids = env
    admin, teacher, student = clients["admin"], clients["teacher"], clients["student"]
    for role in ["student", "instructor"]:
        r = admin.post(
            "/api/v1/users", json={"name": "New " + role, "email": role + "2@example.com", "role": role, "password": "StrongPassword2026!"}
        )
        assert r.status_code == 201, r.text
    c, section, lesson = course
    q = teacher.post(
        "/api/v1/questions",
        json={
            "course_id": c["id"],
            "kind": "single",
            "prompt": "Which layer must enforce permissions?",
            "options": [{"text": "Server", "correct": True}, {"text": "Hidden UI buttons"}],
        },
    ).json()
    quiz = teacher.post(
        "/api/v1/quizzes", json={"course_id": c["id"], "title": "Security quiz", "question_ids": [q["id"]], "attempt_limit": 1}
    ).json()
    assignment = teacher.post(
        "/api/v1/assignments", json={"course_id": c["id"], "title": "Design exercise", "instructions": "Describe a secure endpoint"}
    ).json()
    publish(teacher, c["id"])
    assert teacher.put("/api/v1/courses/" + c["id"], json={"title": "Mutation", "slug": "mutation"}).status_code == 409
    e = student.post("/api/v1/enrollments", json={"course_id": c["id"]}).json()
    assert student.post("/api/v1/certificates/issue/" + e["id"]).status_code == 409
    first = student.post("/api/v1/progress/" + lesson["id"] + "/complete")
    assert first.status_code == 200, first.text
    assert student.post("/api/v1/progress/" + lesson["id"] + "/complete").json()["completed"] == 1
    attempt = student.post("/api/v1/quizzes/" + quiz["id"] + "/start").json()
    assert "correct" not in str(attempt["questions"]) and "explanation" not in attempt["questions"][0]
    correct_id = next(o["id"] for o in q["options"] if o["correct"])
    answer = student.put(
        "/api/v1/attempts/" + attempt["id"] + "/answers", json={"answers": [{"question_id": q["id"], "selected": [correct_id]}]}
    )
    assert answer.status_code == 200, answer.text
    result = student.post("/api/v1/attempts/" + attempt["id"] + "/submit")
    assert result.json()["score"] == 1, result.text
    assert student.post("/api/v1/quizzes/" + quiz["id"] + "/start").status_code == 409
    submission = student.post(
        "/api/v1/assignments/" + assignment["id"] + "/submit",
        json={"text": "Authenticate, resolve tenant, verify permission and check enrollment."},
    ).json()
    graded = teacher.put("/api/v1/submissions/" + submission["id"] + "/grade", json={"marks": 94, "feedback": "Clear reasoning."})
    assert graded.status_code == 200, graded.text
    assert student.get("/api/v1/grades").json()["items"][0]["grade"]["marks"] == 94
    cert = student.post("/api/v1/certificates/issue/" + e["id"])
    assert cert.status_code == 201, cert.text
    certificate = cert.json()
    assert student.post("/api/v1/certificates/issue/" + e["id"]).json()["id"] == certificate["id"]
    assert student.get("/api/v1/certificates/" + certificate["id"] + "/pdf").content.startswith(b"%PDF-")
    verified = student.get("/api/v1/certificates/verify/" + certificate["code"]).json()
    assert verified["valid"] is True and "email" not in verified
    assert student.get("/api/v1/users").status_code == 403
    assert student.get("/api/v1/reports/export.csv").status_code == 403
    revision = teacher.post("/api/v1/courses/" + c["id"] + "/revision")
    assert revision.status_code == 201, revision.text
    assert revision.json()["parent_id"] == c["id"]
    assert (
        admin.post("/api/v1/certificates/" + certificate["id"] + "/revoke", json={"reason": "Administrative correction"}).status_code == 200
    )
    assert student.get("/api/v1/certificates/verify/" + certificate["code"]).json()["valid"] is False
    assert student.post("/api/v1/certificates/issue/" + e["id"]).status_code == 403
    assert admin.post("/api/v1/certificates/issue/" + e["id"]).status_code == 201


def test_tenant_isolation_idor_and_roles(env, course):
    clients, ids = env
    c, _, lesson = course
    assert clients["outsider"].get("/api/v1/courses/" + c["id"]).status_code == 404
    assert clients["outsider"].get("/api/v1/lessons/" + lesson["id"]).status_code == 404
    assert clients["student"].get("/api/v1/courses", headers={"X-Institution-ID": ids["other_tenant"]}).status_code == 403
    assert clients["admin"].put("/api/v1/users/" + ids["student"] + "/role", json={"role": "institution_admin"}).status_code == 403
    assert clients["admin"].patch("/api/v1/users/" + ids["outsider"], json={"name": "Hacked"}).status_code == 404
    assert clients["teacher"].get("/api/v1/users").status_code == 403
    assert clients["auditor"].post("/api/v1/courses", json={"title": "No", "slug": "no"}).status_code == 403
    assert clients["auditor"].get("/api/v1/reports/enrollments").status_code == 200
    assert clients["student"].get("/api/v1/questions", params={"course_id": c["id"]}).status_code == 403
    assert clients["ta"].get("/api/v1/courses/" + c["id"]).status_code == 404
    assert (
        clients["teacher"].post("/api/v1/courses/" + c["id"] + "/instructors", json={"user_id": ids["ta"], "can_grade": False}).status_code
        == 200
    )
    assert clients["ta"].post("/api/v1/courses/" + c["id"] + "/sections", json={"title": "No", "position": 5}).status_code == 403


def test_refresh_csrf_rotation_replay_logout_and_reset(env):
    clients, ids = env
    client = clients["student"]
    original, csrf = client.cookies.get("ls_refresh"), client.cookies.get("ls_csrf")
    assert client.post("/api/v1/auth/refresh").status_code == 403
    refreshed = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200, refreshed.text
    assert client.cookies.get("ls_refresh") != original
    client.cookies.set("ls_refresh", original, domain="testserver.local", path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    other = clients["peer"]
    with SessionLocal.begin() as db:
        raw = queue_token(db, db.get(User, ids["peer"]), "reset")
    assert other.post("/api/v1/auth/reset-password", json={"token": raw, "password": "NewStrongPassword2026!"}).status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401
    assert other.post("/api/v1/auth/reset-password", json={"token": raw, "password": "NewStrongPassword2026!"}).status_code == 400
    admin = clients["admin"]
    assert admin.post("/api/v1/auth/logout", headers={"X-CSRF-Token": admin.cookies.get("ls_csrf")}).status_code == 200
    assert admin.get("/api/v1/auth/me").status_code == 401


def test_files_progress_prerequisites_and_timing(env, course):
    clients, ids = env
    t, student, outsider = clients["teacher"], clients["student"], clients["outsider"]
    c, section, lesson = course
    upload = t.post("/api/v1/files", data={"course_id": c["id"]}, files={"file": ("guide.txt", b"Learning resource", "text/plain")})
    assert upload.status_code == 201, upload.text
    f = upload.json()
    assert "storage_key" not in f
    later = t.post(
        "/api/v1/courses/" + c["id"] + "/lessons",
        json={
            "section_id": section["id"],
            "title": "Advanced",
            "content": "More detail",
            "position": 1,
            "prerequisite_id": lesson["id"],
            "drip_days": 2,
        },
    ).json()
    t.post("/api/v1/files/" + f["id"] + "/lessons/" + later["id"])
    for name, content in [("exploit.html", b"<script>alert(1)</script>"), ("fake.pdf", b"not a pdf")]:
        assert t.post("/api/v1/files", data={"course_id": c["id"]}, files={"file": (name, content)}).status_code == 422
    q = t.post(
        "/api/v1/questions",
        json={"course_id": c["id"], "kind": "single", "prompt": "2 + 2?", "options": [{"text": "4", "correct": True}, {"text": "5"}]},
    ).json()
    quiz = t.post(
        "/api/v1/quizzes", json={"course_id": c["id"], "title": "Timed", "question_ids": [q["id"]], "release_policy": "manual"}
    ).json()
    publish(t, c["id"])
    student.post("/api/v1/enrollments", json={"course_id": c["id"]})
    assert student.get("/api/v1/lessons/" + later["id"]).status_code == 403
    assert student.get("/api/v1/files/" + f["id"] + "/download").status_code == 403
    assert outsider.get("/api/v1/files/" + f["id"] + "/download").status_code == 404
    assert student.get("/api/v1/courses/" + c["id"]).json()["sections"][0]["lessons"][0].get("content") is None
    a = student.post("/api/v1/quizzes/" + quiz["id"] + "/start").json()
    with SessionLocal.begin() as db:
        db.get(QuizAttempt, a["id"]).deadline = now() - timedelta(seconds=1)
    assert student.put("/api/v1/attempts/" + a["id"] + "/answers", json={"answers": []}).status_code == 409
    result = student.get("/api/v1/attempts/" + a["id"]).json()
    assert result["status"] == "graded" and result["score"] is None
    assert "correct" not in str(result["questions"])
    assert t.post("/api/v1/quizzes/" + quiz["id"] + "/release").status_code == 200
    assert student.get("/api/v1/attempts/" + a["id"]).json()["score"] == 0


def test_import_atomic_preview_and_attendance_notifications(env, course):
    clients, ids = env
    admin, teacher, student = clients["admin"], clients["teacher"], clients["student"]
    payload = {
        "csv_text": "Full name,Email\nAda,Ada@example.com\nBad,not-an-email",
        "mapping": {"name": "Full name", "email": "Email"},
        "role": "student",
    }
    preview = admin.post("/api/v1/users/import/preview", json=payload).json()
    assert preview["valid_count"] == 1 and preview["error_count"] == 1
    assert admin.post("/api/v1/users/import/commit", json=payload | {"preview_hash": preview["preview_hash"]}).status_code == 422
    payload["csv_text"] = "Full name,Email\nAda,ada@example.com"
    preview = admin.post("/api/v1/users/import/preview", json=payload).json()
    imported = admin.post("/api/v1/users/import/commit", json=payload | {"preview_hash": preview["preview_hash"]})
    assert imported.status_code == 200, imported.text
    c, _, _ = course
    publish(teacher, c["id"])
    student.post("/api/v1/enrollments", json={"course_id": c["id"]})
    session = teacher.post(
        "/api/v1/attendance",
        json={
            "course_id": c["id"],
            "title": "Seminar",
            "starts_at": now().isoformat(),
            "ends_at": (now() + timedelta(hours=1)).isoformat(),
        },
    ).json()
    payload = {"user_id": ids["student"], "status": "present"}
    first = teacher.put("/api/v1/attendance/" + session["id"] + "/records", json=payload).json()
    correction = teacher.put(
        "/api/v1/attendance/" + session["id"] + "/records", json=payload | {"status": "late", "note": "Register correction"}
    ).json()
    assert correction["id"] == first["id"]
    assert student.get("/api/v1/attendance/" + session["id"] + "/records").json()["total"] == 1
    assert (
        teacher.post("/api/v1/announcements", json={"course_id": c["id"], "title": "Welcome", "body": "Bring questions."}).status_code
        == 201
    )
    assert student.get("/api/v1/notifications").json()["total"] >= 2
    assert admin.get("/api/v1/reports/export.csv?kind=attendance").status_code == 200
    assert admin.get("/api/v1/reports/dashboard").json()["metrics"]["Enrollments"] == 1
    assert clients["outsider"].get("/api/v1/reports/dashboard").json()["metrics"]["Enrollments"] == 0
