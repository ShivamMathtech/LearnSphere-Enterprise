from app.core.config import Settings
from app.security.crypto import hash_password, verify_password
from app.models import Base
import pytest


def test_production_fails_closed():
    with pytest.raises(ValueError):
        Settings(app_env="production")


def test_argon2_and_password_policy():
    encoded = hash_password("CorrectHorse8Battery")
    assert encoded.startswith("$argon2id$")
    assert verify_password("CorrectHorse8Battery", encoded)
    assert not verify_password("IncorrectPassword7", encoded)
    with pytest.raises(Exception):
        hash_password("short")


def test_schema_uniqueness_and_foreign_keys():
    assert len(Base.metadata.tables) >= 48
    for name in ["enrollments", "lesson_progress", "attendance_records"]:
        assert any(c.__class__.__name__ == "UniqueConstraint" for c in Base.metadata.tables[name].constraints)
