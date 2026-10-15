from fastapi import HTTPException
from sqlalchemy import select, func, update
from app.db.base import uid, now
from app.models import (
    Institution,
    CourseInstructor,
    CourseSection,
    Lesson,
    FileAsset,
    LessonResource,
    Question,
    QuestionOption,
    Quiz,
    QuizQuestion,
    Assignment,
    AssignmentAttachment,
    Rubric,
    RubricCriterion,
)
from app.integrations.storage import storage
from app.services.common import audit, required


def clone_entity(db, original, **overrides):
    fields = {c.name: getattr(original, c.name) for c in original.__table__.columns if c.name not in {"id", "created_at", "updated_at"}}
    row = type(original)(**(fields | overrides))
    db.add(row)
    db.flush()
    return row


def _clone_course(db, p, course, created_keys):
    # A unique suffix supports multiple parallel draft branches without overwriting history.
    new = clone_entity(
        db,
        course,
        slug=course.slug[:140] + "-r" + str(course.version + 1) + "-" + uid()[:8],
        status="draft",
        parent_id=course.id,
        version=course.version + 1,
        created_by=p.user.id,
    )
    for staff in db.scalars(select(CourseInstructor).where(CourseInstructor.course_id == course.id)):
        clone_entity(db, staff, course_id=new.id)
    sections, lessons, files, questions = {}, {}, {}, {}
    for row in db.scalars(select(CourseSection).where(CourseSection.course_id == course.id)):
        sections[row.id] = clone_entity(db, row, course_id=new.id).id
    for row in db.scalars(select(Lesson).where(Lesson.course_id == course.id)):
        lessons[row.id] = clone_entity(db, row, course_id=new.id, section_id=sections[row.section_id], prerequisite_id=None)
    for row in db.scalars(select(Lesson).where(Lesson.course_id == course.id)):
        lessons[row.id].prerequisite_id = lessons[row.prerequisite_id].id if row.prerequisite_id else None
    for row in db.scalars(select(FileAsset).where(FileAsset.course_id == course.id, FileAsset.purpose == "resource")):
        key = uid()
        created_keys.append(key)
        storage.copy(row.storage_key, key)
        files[row.id] = clone_entity(db, row, course_id=new.id, storage_key=key).id
    new.thumbnail_id = files.get(course.thumbnail_id) if course.thumbnail_id else None
    for old_id, lesson in lessons.items():
        for fid in db.scalars(select(LessonResource.file_id).where(LessonResource.lesson_id == old_id)):
            db.add(LessonResource(lesson_id=lesson.id, file_id=files[fid]))
    for row in db.scalars(select(Question).where(Question.course_id == course.id)):
        q = clone_entity(db, row, course_id=new.id)
        questions[row.id] = q.id
        for option in db.scalars(select(QuestionOption).where(QuestionOption.question_id == row.id)):
            clone_entity(db, option, question_id=q.id)
    for row in db.scalars(select(Quiz).where(Quiz.course_id == course.id)):
        q = clone_entity(
            db,
            row,
            course_id=new.id,
            released=False,
            opens_at=None,
            closes_at=None,
            release_policy="manual" if row.release_policy == "after_close" else row.release_policy,
        )
        for qid in db.scalars(select(QuizQuestion.question_id).where(QuizQuestion.quiz_id == row.id)):
            db.add(QuizQuestion(quiz_id=q.id, question_id=questions[qid]))
    for row in db.scalars(select(Assignment).where(Assignment.course_id == course.id)):
        a = clone_entity(db, row, course_id=new.id, due_at=None)
        for fid in db.scalars(select(AssignmentAttachment.file_id).where(AssignmentAttachment.assignment_id == row.id)):
            db.add(AssignmentAttachment(assignment_id=a.id, file_id=files[fid]))
        r = db.scalar(select(Rubric).where(Rubric.assignment_id == row.id))
        if r:
            new_r = clone_entity(db, r, assignment_id=a.id)
            for criterion in db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == r.id)):
                clone_entity(db, criterion, rubric_id=new_r.id)
    audit(db, p, "courses.revision_created", new, {"previous_revision": course.id})
    return new


def clone_course(db, p, course):
    institution = required(db, Institution, course.institution_id)
    db.execute(update(Institution).where(Institution.id == institution.id).values(updated_at=now()))
    used = db.scalar(select(func.coalesce(func.sum(FileAsset.size), 0)).where(FileAsset.institution_id == institution.id))
    copied = db.scalar(
        select(func.coalesce(func.sum(FileAsset.size), 0)).where(FileAsset.course_id == course.id, FileAsset.purpose == "resource")
    )
    if used + copied > institution.storage_quota_mb * 1024 * 1024:
        raise HTTPException(413, "Institution storage quota would be exceeded by this revision")
    created_keys: list[str] = []
    try:
        result = _clone_course(db, p, course, created_keys)
        db.commit()
        return result
    except Exception:
        db.rollback()
        for key in created_keys:
            storage.delete(key)
        raise
