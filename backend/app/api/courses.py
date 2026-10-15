from app.services.common import required
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, func, update
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.base import now
from app.models import FileAsset, Course, CourseCategory, Department, CourseSection, CourseInstructor, Lesson, Enrollment, User
from app.schemas import contracts as s
from app.api.deps import Pagination
from app.security.access import (
    Principal,
    permit,
    tenant,
    scoped,
    course_access,
    active_enrollment,
    editable,
    member,
    roles_for,
    visible_course_ids,
)
from app.services.common import public, page, audit, notify
from app.services import learning

router = APIRouter(tags=["Courses and learning"])


def validate_refs(db, p, data):
    if data.category_id:
        scoped(db, CourseCategory, data.category_id, p)
    if data.department_id:
        scoped(db, Department, data.department_id, p)


@router.get("/courses/authoring-options")
def authoring_options(p: Principal = Depends(permit("courses.create")), db: Session = Depends(get_db)):
    lookups: list[tuple[str, type[CourseCategory] | type[Department]]] = [("categories", CourseCategory), ("departments", Department)]
    return {
        key: [
            {"id": row.id, "name": row.name}
            for row in db.execute(select(model.id, model.name).where(model.institution_id == tenant(p)).order_by(model.name).limit(100))
        ]
        for key, model in lookups
    }


@router.get("/courses", response_model=s.Page)
def courses(
    status: str | None = None,
    difficulty: str | None = None,
    category_id: str | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("courses.read")),
    db: Session = Depends(get_db),
):
    query = select(Course).where(Course.institution_id == tenant(p))
    if not p.manager:
        if p.roles & {"instructor", "teaching_assistant"}:
            query = query.where(Course.id.in_(visible_course_ids(db, p)))
        else:
            query = query.where(
                or_((Course.status == "published") & (Course.visibility == "institution"), Course.id.in_(visible_course_ids(db, p)))
            )
    if status:
        query = query.where(Course.status == status)
    if difficulty:
        query = query.where(Course.difficulty == difficulty)
    if category_id:
        query = query.where(Course.category_id == category_id)
    return page(db, q.apply(query, Course, Course.title), q.page, q.page_size)


@router.post("/courses", response_model=s.Record, status_code=201)
def add_course(data: s.CourseInput, p: Principal = Depends(permit("courses.create")), db: Session = Depends(get_db)):
    validate_refs(db, p, data)
    row = Course(institution_id=tenant(p), created_by=p.user.id, **data.model_dump())
    db.add(row)
    db.flush()
    db.add(CourseInstructor(course_id=row.id, user_id=p.user.id, can_grade=True))
    audit(db, p, "courses.created", row)
    return public(row)


@router.get("/courses/{course_id}", response_model=s.Record)
def course_detail(course_id: str, p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    c = scoped(db, Course, course_id, p)
    enrolled = db.scalar(select(Enrollment).where(Enrollment.course_id == c.id, Enrollment.user_id == p.user.id))
    staff = p.manager or bool(db.get(CourseInstructor, (c.id, p.user.id)))
    can_catalog = c.status == "published" and c.visibility == "institution"
    if not staff and not enrolled and not can_catalog:
        raise HTTPException(404, "Course not found")
    # Lesson bodies are retrieved individually so prerequisite/drip checks cannot be bypassed.
    result = {
        **public(c),
        "sections": learning.course_outline(db, c, bool(staff)),
        "enrollment": public(enrolled) if enrolled else None,
        "instructors": [
            {**public(a), "name": required(db, User, a.user_id).name}
            for a in db.scalars(select(CourseInstructor).where(CourseInstructor.course_id == c.id))
        ],
        "can_author": bool(staff and "courses.update" in p.permissions),
    }
    if enrolled:
        result["progress"] = learning.eligibility(db, enrolled)
    return result


@router.put("/courses/{course_id}", response_model=s.Record)
def edit_course(course_id: str, data: s.CourseInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    editable(c)
    validate_refs(db, p, data)
    for key, value in data.model_dump().items():
        setattr(c, key, value)
    audit(db, p, "courses.updated", c)
    db.flush()
    return public(c)


@router.post("/courses/{course_id}/review", response_model=s.Record)
def review(course_id: str, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    if c.status != "draft":
        raise HTTPException(409, "Only drafts can be submitted for review")
    c.status = "in_review"
    audit(db, p, "courses.in_review", c)
    return public(c)


@router.post("/courses/{course_id}/publish", response_model=s.Record)
def publish(course_id: str, p: Principal = Depends(permit("courses.publish")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    learning.publish(db, p, c)
    return public(c)


@router.post("/courses/{course_id}/archive", response_model=s.Record)
def archive(course_id: str, p: Principal = Depends(permit("courses.publish")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    c.status = "archived"
    audit(db, p, "courses.archived", c)
    return public(c)


@router.post("/courses/{course_id}/revision", response_model=s.Record, status_code=201)
def revision(course_id: str, p: Principal = Depends(permit("courses.create")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    if c.status not in {"published", "archived"}:
        raise HTTPException(409, "Publish the current revision first")
    from app.services.revision import clone_course

    return public(clone_course(db, p, c))


@router.post("/courses/{course_id}/instructors", response_model=s.Result)
def assign_staff(
    course_id: str, data: s.StaffInput, p: Principal = Depends(permit("courses.assign_assistant")), db: Session = Depends(get_db)
):
    c = course_access(db, p, course_id, "write")
    membership = member(db, data.user_id, p)
    roles = roles_for(db, membership.id)
    if not roles & {"instructor", "teaching_assistant"}:
        raise HTTPException(422, "Assign an instructor or teaching assistant")
    if not p.manager and "instructor" in roles:
        raise HTTPException(403, "Only an administrator may assign instructors")
    row = db.get(CourseInstructor, (c.id, data.user_id))
    if not row:
        row = CourseInstructor(course_id=c.id, user_id=data.user_id)
        db.add(row)
    row.can_grade, row.can_discuss = data.can_grade, data.can_discuss
    audit(db, p, "courses.staff_assigned", c, data.model_dump())
    return {"message": "Course assignment saved"}


@router.post("/courses/{course_id}/sections", response_model=s.Record, status_code=201)
def add_section(course_id: str, data: s.SectionInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    editable(c)
    row = CourseSection(institution_id=tenant(p), course_id=c.id, **data.model_dump())
    db.add(row)
    db.flush()
    return public(row)


@router.post("/courses/{course_id}/lessons", response_model=s.Record, status_code=201)
def add_lesson(course_id: str, data: s.LessonInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    c = course_access(db, p, course_id, "write")
    editable(c)
    section = scoped(db, CourseSection, data.section_id, p)
    if section.course_id != c.id:
        raise HTTPException(422, "Section must belong to this course")
    if data.prerequisite_id:
        prerequisite = scoped(db, Lesson, data.prerequisite_id, p)
        if prerequisite.course_id != c.id:
            raise HTTPException(422, "Prerequisite must belong to this course")
    row = Lesson(institution_id=tenant(p), course_id=c.id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, p, "lessons.created", row)
    return public(row)


@router.get("/lessons/{lesson_id}", response_model=s.Record)
def lesson_detail(lesson_id: str, p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    lesson = scoped(db, Lesson, lesson_id, p)
    learning.lesson_open(db, p, lesson)
    from app.models import LessonResource

    return {**public(lesson), "file_ids": list(db.scalars(select(LessonResource.file_id).where(LessonResource.lesson_id == lesson.id)))}


@router.put("/lessons/{lesson_id}", response_model=s.Record)
def edit_lesson(lesson_id: str, data: s.LessonInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    lesson = scoped(db, Lesson, lesson_id, p)
    c = course_access(db, p, lesson.course_id, "write")
    editable(c)
    section = scoped(db, CourseSection, data.section_id, p)
    if section.course_id != c.id:
        raise HTTPException(422, "Wrong course section")
    visited = {lesson.id}
    prerequisite_id = data.prerequisite_id
    while prerequisite_id:
        if prerequisite_id in visited:
            raise HTTPException(422, "Prerequisites cannot contain cycles")
        prerequisite = scoped(db, Lesson, prerequisite_id, p)
        if prerequisite.course_id != c.id:
            raise HTTPException(422, "Wrong prerequisite course")
        visited.add(prerequisite_id)
        prerequisite_id = prerequisite.prerequisite_id
    for key, value in data.model_dump().items():
        setattr(lesson, key, value)
    audit(db, p, "lessons.updated", lesson)
    db.flush()
    return public(lesson)


@router.delete("/lessons/{lesson_id}", response_model=s.Result)
def delete_lesson(lesson_id: str, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    lesson = scoped(db, Lesson, lesson_id, p)
    editable(course_access(db, p, lesson.course_id, "write"))
    audit(db, p, "lessons.deleted", lesson)
    db.delete(lesson)
    db.flush()
    return {"message": "Lesson deleted"}


@router.post("/enrollments", response_model=s.Record, status_code=201)
def enroll(data: s.EnrollmentInput, p: Principal = Depends(permit("enrollments.create")), db: Session = Depends(get_db)):
    return public(learning.enroll(db, p, data))


@router.post("/enrollments/bulk")
def bulk_enroll(data: s.BulkEnroll, p: Principal = Depends(permit("enrollments.manage")), db: Session = Depends(get_db)):
    rows = [
        learning.enroll(db, p, s.EnrollmentInput(course_id=data.course_id, user_id=user_id), bulk=True)
        for user_id in dict.fromkeys(data.user_ids)
    ]
    return {"items": [public(r) for r in rows]}


@router.get("/enrollments", response_model=s.Page)
def enrollments(
    course_id: str | None = None,
    status: str | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("courses.read")),
    db: Session = Depends(get_db),
):
    query = select(Enrollment).where(Enrollment.institution_id == tenant(p))
    if "enrollments.read" in p.permissions or "enrollments.manage" in p.permissions:
        query = query.where(Enrollment.course_id.in_(visible_course_ids(db, p)))
    else:
        query = query.where(Enrollment.user_id == p.user.id)
    if course_id:
        query = query.where(Enrollment.course_id == course_id)
    if status:
        query = query.where(Enrollment.status == status)
    return page(
        db,
        q.apply(query, Enrollment),
        q.page,
        q.page_size,
        lambda e: {
            **public(e),
            "student_name": required(db, User, e.user_id).name,
            "course_title": required(db, Course, e.course_id).title,
            "progress": learning.progress(db, e),
        },
    )


@router.patch("/enrollments/{enrollment_id}", response_model=s.Record)
def decision(
    enrollment_id: str, data: s.EnrollmentDecision, p: Principal = Depends(permit("enrollments.manage")), db: Session = Depends(get_db)
):
    e = scoped(db, Enrollment, enrollment_id, p)
    c = course_access(db, p, e.course_id, "write")
    db.execute(update(Course).where(Course.id == c.id).values(updated_at=now()))
    if e.status == "completed":
        raise HTTPException(409, "Completed learning records are retained")
    if data.status == "active" and e.status != "active":
        count = db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.course_id == c.id, Enrollment.status.in_(["active", "completed"]))
        )
        if count >= c.max_learners:
            raise HTTPException(409, "Course capacity reached")
    e.status = data.status
    audit(db, p, "enrollments.status_changed", e, {"status": data.status})
    notify(db, tenant(p), e.user_id, "Enrollment " + data.status, c.title)
    return public(e)


@router.post("/progress/{lesson_id}/complete")
def complete(lesson_id: str, p: Principal = Depends(permit("progress.update")), db: Session = Depends(get_db)):
    return learning.complete_lesson(db, p, scoped(db, Lesson, lesson_id, p))


@router.get("/progress/{course_id}")
def progress(course_id: str, p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    return learning.eligibility(db, active_enrollment(db, p, course_id))


@router.get("/courses/{course_id}/staff-candidates", response_model=s.Page)
def staff_candidates(
    course_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.assign_assistant")), db: Session = Depends(get_db)
):
    from app.models import Membership, Role, UserRole

    course_access(db, p, course_id, "write")
    allowed_roles = ["instructor", "teaching_assistant"] if p.manager else ["teaching_assistant"]
    query = (
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .join(UserRole, UserRole.membership_id == Membership.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Membership.institution_id == tenant(p), Role.name.in_(allowed_roles), User.active.is_(True))
    )
    return page(db, q.apply(query, User, User.name), q.page, q.page_size, lambda u: {"id": u.id, "name": u.name})


@router.put("/sections/{section_id}", response_model=s.Record)
def edit_section(section_id: str, data: s.SectionInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    section = scoped(db, CourseSection, section_id, p)
    editable(course_access(db, p, section.course_id, "write"))
    section.title, section.position = data.title, data.position
    db.flush()
    audit(db, p, "sections.updated", section)
    return public(section)


@router.delete("/sections/{section_id}", response_model=s.Result)
def delete_section(section_id: str, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    section = scoped(db, CourseSection, section_id, p)
    editable(course_access(db, p, section.course_id, "write"))
    if db.scalar(select(Lesson.id).where(Lesson.section_id == section.id)):
        raise HTTPException(409, "Move or remove all lessons before deleting a section")
    audit(db, p, "sections.deleted", section)
    db.delete(section)
    return {"message": "Section deleted"}


@router.put("/courses/{course_id}/thumbnail", response_model=s.Record)
def set_thumbnail(course_id: str, data: s.ThumbnailInput, p: Principal = Depends(permit("courses.update")), db: Session = Depends(get_db)):
    course = course_access(db, p, course_id, "write")
    editable(course)
    if data.file_id:
        asset = scoped(db, FileAsset, data.file_id, p)
        if asset.course_id != course.id or asset.purpose != "resource" or asset.mime_type not in {"image/png", "image/jpeg"}:
            raise HTTPException(422, "Choose a PNG or JPEG resource uploaded to this course")
    course.thumbnail_id = data.file_id
    audit(db, p, "courses.thumbnail_updated", course)
    return public(course)


@router.get("/courses/{course_id}/thumbnail")
def thumbnail(course_id: str, p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    from app.integrations.storage import storage

    detail = course_detail(course_id, p, db)  # Catalog/assignment visibility applies before image retrieval.
    if not detail["thumbnail_id"]:
        raise HTTPException(404, "No thumbnail configured")
    asset = scoped(db, FileAsset, detail["thumbnail_id"], p)
    if asset.course_id != course_id or asset.mime_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(404, "Thumbnail unavailable")
    path = storage.path(asset.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Thumbnail bytes unavailable")
    return FileResponse(path, media_type=asset.mime_type)
