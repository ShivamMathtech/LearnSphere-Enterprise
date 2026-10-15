from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import DateTime, MetaData, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC).replace(tzinfo=None)
        return None

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value else None


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class Tenant:
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id", ondelete="RESTRICT"), index=True)
