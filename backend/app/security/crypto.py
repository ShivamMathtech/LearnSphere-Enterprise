import base64
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.core.config import settings

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password):
    if (
        len(password) < 12
        or len(password) > 128
        or not any(c.isupper() for c in password)
        or not any(c.islower() for c in password)
        or not any(c.isdigit() for c in password)
    ):
        raise HTTPException(422, "Use 12–128 characters including upper/lower case and a number")
    return hasher.hash(password)


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def token():
    return secrets.token_urlsafe(40)


def cipher():
    s = settings()
    key = s.encryption_key or base64.urlsafe_b64encode(hashlib.sha256(s.secret_key.encode()).digest()).decode()
    return Fernet(key.encode())
