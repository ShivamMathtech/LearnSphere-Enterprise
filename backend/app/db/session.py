from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


def make_engine(url):
    if url.startswith("sqlite"):
        filename = url.split("///", 1)[-1]
        if filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, hide_parameters=True, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(conn, record):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA journal_mode=WAL")

        return engine
    return create_engine(url, hide_parameters=True, pool_pre_ping=True, pool_size=10, max_overflow=10)


engine = make_engine(settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
