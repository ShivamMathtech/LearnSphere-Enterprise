from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT.parent / ".env"), extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/learnsphere.db"
    secret_key: str = "development-only-change-before-production-123456789"
    encryption_key: str = ""
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    access_minutes: int = Field(default=10, ge=1, le=60)
    refresh_days: int = Field(default=7, ge=1, le=90)
    demo_enabled: bool = False
    email_verification_required: bool = False
    require_privileged_mfa: bool = False
    upload_max_mb: int = Field(default=20, ge=1, le=200)
    storage_path: str = "./storage"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "learnsphere@example.invalid"
    smtp_starttls: bool = True
    audit_retention_days: int = 365
    notification_retention_days: int = 90

    @property
    def production(self):
        return self.app_env == "production"

    @property
    def origins(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_production(self):
        if self.production:
            if len(self.secret_key) < 48 or "development" in self.secret_key or "CHANGE" in self.secret_key:
                raise ValueError("Production SECRET_KEY must be a unique random secret of at least 48 characters")
            if not self.encryption_key or "CHANGE" in self.encryption_key:
                raise ValueError("Production ENCRYPTION_KEY is required (Fernet key)")
            from cryptography.fernet import Fernet

            Fernet(self.encryption_key.encode())
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL with psycopg")
            if self.demo_enabled:
                raise ValueError("Demo mode is forbidden in production")
            if (
                not self.origins
                or not self.frontend_url.startswith("https://")
                or any(not u.startswith("https://") for u in self.origins)
                or "*" in self.origins
            ):
                raise ValueError("Production requires explicit HTTPS origins")
        return self


@lru_cache
def settings():
    return Settings()
