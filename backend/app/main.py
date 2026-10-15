import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db.session import engine
from app.api import auth, admin, courses, assessments, files, community, reports

log = logging.getLogger("learnsphere")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app):
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.execute(text("SELECT version_num FROM alembic_version"))
    log.info(json.dumps({"event": "startup", "environment": settings().app_env}))
    yield
    engine.dispose()


app = FastAPI(
    title="LearnSphere Enterprise API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings().production else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Institution-ID"],
)


@app.middleware("http")
async def headers_and_logging(request: Request, call_next):
    request_id = str(uuid4())
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if settings().production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Never log headers, query strings, cookies, credentials or request bodies.
    log.info(
        json.dumps(
            {
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
            }
        )
    )
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409, content={"detail": "The record conflicts with an existing record or a related record still references it."}
    )


@app.get("/api/v1/health", tags=["Health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return {"status": "ok", "database": "ok", "schema_revision": revision}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(community.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
