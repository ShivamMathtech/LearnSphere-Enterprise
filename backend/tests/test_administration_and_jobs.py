from datetime import timedelta
from sqlalchemy import select, func
from app.core.config import settings
from app.db.base import now
from app.db.session import SessionLocal
from app.models import EmailOutbox, Notification, User
from app.services.auth import queue_token
from app.tasks import worker
from conftest import publish


def test_academic_crud_relations_cohort_filters_and_platform_scope(env, course):
    clients, ids = env
    admin, root = clients["admin"], clients["super"]

    def create(path, body):
        response = admin.post("/api/v1/" + path, json=body)
        assert response.status_code == 201, response.text
        return response.json()

    department = create("departments", {"name": "Engineering", "code": "ENG"})
    program = create(
        "programs", {"name": "Software Engineering", "code": "SWE", "department_id": department["id"], "level": "Undergraduate"}
    )
    year = create("academic-years", {"name": "2026", "starts_at": now().isoformat(), "ends_at": (now() + timedelta(days=365)).isoformat()})
    semester = create("semesters", {"name": "Autumn", "academic_year_id": year["id"]})
    cohort = create("cohorts", {"name": "Class A", "code": "A", "program_id": program["id"]})
    category = create("course-categories", {"name": "Computing"})
    offering = create(
        "course-offerings",
        {"name": "Morning class", "course_id": course[0]["id"], "cohort_id": cohort["id"], "semester_id": semester["id"]},
    )
    assert admin.delete("/api/v1/departments/" + department["id"]).status_code == 409
    edited = admin.put("/api/v1/programs/" + program["id"], json={"name": "Software", "code": "SWE", "department_id": None})
    assert edited.status_code == 200 and edited.json()["department_id"] is None
    assert admin.delete("/api/v1/departments/" + department["id"]).status_code == 200
    for who, expected in [("student", 200), ("teacher", 422), ("outsider", 404)]:
        assert admin.post("/api/v1/cohorts/" + cohort["id"] + "/members/" + ids[who]).status_code == expected
    assert admin.get("/api/v1/cohorts/" + cohort["id"] + "/members").json()["total"] == 1
    assert admin.delete("/api/v1/cohorts/" + cohort["id"] + "/members/" + ids["student"]).status_code == 200
    assert admin.get("/api/v1/users?role=student").json()["total"] == 2
    assert admin.get("/api/v1/users?page_size=1").json()["page_size"] == 1
    assert admin.get("/api/v1/users?sort=name&direction=asc&search=Student").json()["total"] == 1
    assert len(admin.get("/api/v1/roles").json()) == 7
    assert len(admin.get("/api/v1/permissions").json()) > 20
    assert admin.get("/api/v1/institutions").status_code == 403
    institution = root.post("/api/v1/institutions", json={"name": "New University", "slug": "new-university"}).json()
    owner = root.post(
        "/api/v1/institutions/" + institution["id"] + "/administrator",
        json={"name": "New Owner", "email": "new-owner@example.com", "role": "student", "password": "StrongPassword2026!"},
    )
    assert owner.status_code == 201, owner.text
    assert root.get("/api/v1/users", headers={"X-Institution-ID": institution["id"]}).json()["total"] == 1
    for path, row in [
        ("course-offerings", offering),
        ("course-categories", category),
        ("cohorts", cohort),
        ("semesters", semester),
        ("academic-years", year),
        ("programs", program),
    ]:
        assert admin.delete("/api/v1/" + path + "/" + row["id"]).status_code == 200


def test_scoped_communications_and_notification_ownership(env, course):
    clients, ids = env
    teacher, student, peer, outsider = [clients[k] for k in ("teacher", "student", "peer", "outsider")]
    course_id = course[0]["id"]
    publish(teacher, course_id)
    student.post("/api/v1/enrollments", json={"course_id": course_id})
    thread = student.post(
        "/api/v1/discussions", json={"course_id": course_id, "title": "Question", "body": "How do memberships scope a query?"}
    )
    assert thread.status_code == 201
    path = "/api/v1/discussions/" + thread.json()["id"] + "/replies"
    assert teacher.post(path, json={"body": "Resolve the tenant from the verified session."}).status_code == 201
    assert student.get(path).json()["total"] == 1
    assert peer.get(path).status_code == 403
    assert outsider.get(path).status_code == 404
    assert (
        teacher.post("/api/v1/messages", json={"course_id": course_id, "recipient_id": ids["outsider"], "body": "Denied"}).status_code
        == 403
    )
    assert (
        teacher.post(
            "/api/v1/messages", json={"course_id": course_id, "recipient_id": ids["student"], "body": "Feedback for you."}
        ).status_code
        == 201
    )
    assert student.get("/api/v1/messages").json()["total"] == 1
    assert peer.get("/api/v1/messages").json()["total"] == 0
    notification = student.get("/api/v1/notifications?unread=true").json()["items"][0]
    read = "/api/v1/notifications/" + notification["id"] + "/read"
    assert peer.post(read).status_code == 404
    assert student.post(read).status_code == 200
    assert student.post(read).status_code == 200


def test_worker_deadline_deduplication_unconfigured_mail_and_retry(env, course, monkeypatch):
    clients, ids = env
    teacher, student = clients["teacher"], clients["student"]
    course_id = course[0]["id"]
    teacher.post(
        "/api/v1/assignments",
        json={
            "course_id": course_id,
            "title": "Tomorrow",
            "instructions": "Submit your design.",
            "due_at": (now() + timedelta(hours=12)).isoformat(),
        },
    )
    publish(teacher, course_id)
    student.post("/api/v1/enrollments", json={"course_id": course_id})
    with SessionLocal.begin() as db:
        queue_token(db, db.get(User, ids["student"]), "reset")
    monkeypatch.setattr(settings(), "smtp_host", "")
    assert worker.run_once()["smtp"] == "unconfigured"
    worker.run_once()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.dedupe_key.like("due:%"))) == 1
        mail = db.scalar(select(EmailOutbox))
        assert mail.status != "sent" and mail.encrypted_body
    monkeypatch.setattr(settings(), "smtp_host", "test.invalid")

    def unavailable(*args, **kwargs):
        raise ConnectionError("No network delivery in this test")

    monkeypatch.setattr(worker.smtplib, "SMTP", unavailable)
    assert worker.run_once()["sent"] == 0
    with SessionLocal.begin() as db:
        mail = db.scalar(select(EmailOutbox))
        assert mail.status == "retry" and mail.attempts == 1 and mail.last_error == "ConnectionError"
        mail.created_at = now() - timedelta(days=31)
    worker.retention()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0
