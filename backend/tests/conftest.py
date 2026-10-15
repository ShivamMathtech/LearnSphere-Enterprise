import os
from pathlib import Path
import tempfile
import pytest
from alembic import command
from alembic.config import Config

TEMP = tempfile.TemporaryDirectory(prefix="learnsphere-tests-")
TEST_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///" + str(Path(TEMP.name) / "tests.db"))
if not TEST_URL.startswith("sqlite") and "test" not in TEST_URL.rsplit("/", 1)[-1]:
    raise RuntimeError("TEST_DATABASE_URL must target a disposable database with test in its name")
os.environ.update(
    DATABASE_URL=TEST_URL,
    APP_ENV="development",
    DEMO_ENABLED="false",
    STORAGE_PATH=str(Path(TEMP.name) / "storage"),
    EMAIL_VERIFICATION_REQUIRED="false",
)
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.models import Institution
from app.cli import add_user
from app.security.permissions import seed_permissions
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def migrate():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    yield
    engine.dispose()
    TEMP.cleanup()


@pytest.fixture
def env():
    with SessionLocal.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            for col in table.columns:
                if col.nullable and any(fk.column.table is table for fk in col.foreign_keys):
                    db.execute(update(table).values({col.name: None}))
            db.execute(delete(table))
        seed_permissions(db)
        a = Institution(name="Academy A", slug="academy-a")
        b = Institution(name="Academy B", slug="academy-b")
        db.add_all([a, b])
        db.flush()
        ids = {"tenant": a.id, "other_tenant": b.id}
        for key, role, institution in [
            ("admin", "institution_admin", a.id),
            ("teacher", "instructor", a.id),
            ("student", "student", a.id),
            ("peer", "student", a.id),
            ("ta", "teaching_assistant", a.id),
            ("outsider", "student", b.id),
            ("auditor", "auditor", a.id),
            ("super", "super_admin", None),
        ]:
            u = add_user(db, key + "@example.com", key.title(), "StrongPassword2026!", role, institution)
            ids[key] = u.id
    clients = {}
    for role in ["admin", "teacher", "student", "peer", "ta", "outsider", "auditor", "super"]:
        client = TestClient(app)
        result = client.post("/api/v1/auth/login", json={"email": role + "@example.com", "password": "StrongPassword2026!"})
        assert result.status_code == 200, result.text
        client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
        clients[role] = client
    yield clients, ids
    for c in clients.values():
        c.close()


@pytest.fixture
def course(env):
    clients, ids = env
    teacher = clients["teacher"]
    r = teacher.post(
        "/api/v1/courses",
        json={
            "title": "Practical API Design",
            "slug": "practical-api",
            "description": "A real course",
            "objectives": "Build a secure endpoint",
        },
    )
    assert r.status_code == 201, r.text
    c = r.json()
    section = teacher.post(f"/api/v1/courses/{c['id']}/sections", json={"title": "Introduction", "position": 0}).json()
    lesson = teacher.post(
        f"/api/v1/courses/{c['id']}/lessons",
        json={
            "section_id": section["id"],
            "title": "Authorization",
            "content": "Always verify institution and resource scope.",
            "position": 0,
        },
    ).json()
    return c, section, lesson


def publish(client, course_id):
    assert client.post(f"/api/v1/courses/{course_id}/review").status_code == 200
    r = client.post(f"/api/v1/courses/{course_id}/publish")
    assert r.status_code == 200, r.text
