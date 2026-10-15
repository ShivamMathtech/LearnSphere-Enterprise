from app.services.common import required
import hashlib
import io
from pathlib import Path
import re
from uuid import uuid4
import zipfile
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import now
from app.db.session import get_db
from app.models import FileAsset, Institution, Lesson, LessonResource, AssignmentAttachment, SubmissionFile
from app.security.access import Principal, current, scoped, tenant, course_access, active_enrollment, editable
from app.services.common import public, audit
from app.services.learning import lesson_open
from app.integrations.storage import storage
from app.schemas import contracts as s

router = APIRouter(prefix="/files", tags=["Files"])
TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def validate_bytes(extension, contents):
    signatures = {".pdf": b"%PDF-", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}
    if extension in signatures and not contents.startswith(signatures[extension]):
        raise HTTPException(422, "File signature does not match its extension")
    if extension == ".mp4" and contents[4:8] != b"ftyp":
        raise HTTPException(422, "Invalid MP4 container")
    if extension in {".txt", ".csv"}:
        try:
            contents.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Text files must use UTF-8") from None
        if b"\x00" in contents:
            raise HTTPException(422, "Invalid text file")
    if extension in {".docx", ".pptx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as z:
                names = z.namelist()
                if "[Content_Types].xml" not in names or any("vbaproject" in name.lower() for name in names):
                    raise ValueError()
                if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024 or len(names) > 5000:
                    raise ValueError()
        except (ValueError, zipfile.BadZipFile):
            raise HTTPException(422, "Invalid or unsafe Office document") from None


@router.post("", response_model=s.Record, status_code=201)
async def upload(
    course_id: str = Form(...),
    purpose: str = Form("resource"),
    file: UploadFile = File(...),
    p: Principal = Depends(current),
    db: Session = Depends(get_db),
):
    if purpose == "submission":
        p.require("submissions.create")
        active_enrollment(db, p, course_id)
    elif purpose == "resource":
        p.require("files.create")
        editable(course_access(db, p, course_id, "write"))
    else:
        raise HTTPException(422, "Unsupported upload purpose")
    name = re.sub(r"[^\w.() -]", "_", (file.filename or "upload").replace("\\", "/").split("/")[-1])[:180]
    extension = Path(name).suffix.lower()
    if extension not in TYPES:
        raise HTTPException(422, "Allowed files: PDF, UTF-8 text/CSV, PNG/JPEG, MP4 and macro-free Office documents")
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > settings().upload_max_mb * 1024 * 1024:
            raise HTTPException(413, "Upload exceeds the configured file-size limit")
    if not content:
        raise HTTPException(422, "Empty file")
    validate_bytes(extension, bytes(content))
    institution = required(db, Institution, tenant(p))
    db.execute(update(Institution).where(Institution.id == institution.id).values(updated_at=now()))
    used = db.scalar(select(func.coalesce(func.sum(FileAsset.size), 0)).where(FileAsset.institution_id == tenant(p)))
    if (used or 0) + len(content) > institution.storage_quota_mb * 1024 * 1024:
        raise HTTPException(413, "Institution storage quota reached")
    key = str(uuid4())
    asset = FileAsset(
        institution_id=tenant(p),
        course_id=course_id,
        uploaded_by=p.user.id,
        name=name,
        storage_key=key,
        mime_type=TYPES[extension],
        size=len(content),
        purpose=purpose,
        sha256=hashlib.sha256(content).hexdigest(),
    )
    db.add(asset)
    db.flush()
    try:
        storage.write(key, content)
        audit(db, p, "files.uploaded", asset, {"size": len(content)})
        db.commit()
    except Exception:
        storage.delete(key)
        raise
    return public(asset)


@router.post("/{file_id}/lessons/{lesson_id}", response_model=s.Result)
def attach(file_id: str, lesson_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    p.require("courses.update")
    lesson = scoped(db, Lesson, lesson_id, p)
    editable(course_access(db, p, lesson.course_id, "write"))
    asset = scoped(db, FileAsset, file_id, p)
    if asset.course_id != lesson.course_id or asset.purpose != "resource":
        raise HTTPException(422, "File must be a resource of the same course")
    if not db.get(LessonResource, (lesson.id, asset.id)):
        db.add(LessonResource(lesson_id=lesson.id, file_id=asset.id))
    return {"message": "Resource attached"}


@router.get("/{file_id}/download")
def download(file_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    asset = scoped(db, FileAsset, file_id, p)
    if asset.purpose == "submission":
        if asset.uploaded_by != p.user.id:
            p.require("assessments.grade")
            course_access(db, p, asset.course_id, "grade")
            if not db.scalar(select(SubmissionFile.submission_id).where(SubmissionFile.file_id == asset.id)):
                raise HTTPException(403, "File has not been submitted for review")
        else:
            active_enrollment(db, p, asset.course_id)
    else:
        course_access(db, p, asset.course_id)
        from app.models import CourseInstructor

        staff = p.manager or db.get(CourseInstructor, (asset.course_id, p.user.id))
        if not staff:
            lessons = db.scalars(
                select(Lesson).join(LessonResource, LessonResource.lesson_id == Lesson.id).where(LessonResource.file_id == asset.id)
            ).all()
            authorized = bool(db.scalar(select(AssignmentAttachment.assignment_id).where(AssignmentAttachment.file_id == asset.id)))
            for lesson in lessons:
                try:
                    lesson_open(db, p, lesson)
                    authorized = True
                except HTTPException:
                    continue
            if not authorized:
                raise HTTPException(403, "This resource is not available to you yet")
    path = storage.path(asset.storage_key)
    if not path.is_file():
        raise HTTPException(404, "File bytes are unavailable; contact the administrator")
    audit(db, p, "files.downloaded", asset)
    return FileResponse(
        path,
        filename=asset.name,
        media_type=asset.mime_type,
        content_disposition_type="attachment",
        headers={"Content-Security-Policy": "sandbox; default-src 'none'"},
    )
