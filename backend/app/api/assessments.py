from app.services.common import required
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.base import now
from app.models import (
    Quiz,
    Question,
    QuestionOption,
    QuizQuestion,
    QuizAttempt,
    QuizAnswer,
    Assignment,
    AssignmentAttachment,
    Rubric,
    RubricCriterion,
    Submission,
    SubmissionFile,
    FileAsset,
    Grade,
    Feedback,
    User,
)
from app.schemas import contracts as s
from app.security.access import Principal, permit, scoped, tenant, course_access, editable, visible_course_ids
from app.services.common import public, page, audit, check_dates
from app.services import assessments as service
from app.api.deps import Pagination

router = APIRouter(tags=["Assessments"])


@router.get("/questions", response_model=s.Page)
def question_bank(
    course_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)
):
    course_access(db, p, course_id, "write")
    query = select(Question).where(Question.institution_id == tenant(p), Question.course_id == course_id)
    return page(db, q.apply(query, Question, Question.prompt), q.page, q.page_size, lambda row: service.question_view(db, row, True))


@router.post("/questions", response_model=s.Record, status_code=201)
def add_question(data: s.QuestionInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    editable(course_access(db, p, data.course_id, "write"))
    row = Question(institution_id=tenant(p), **data.model_dump(exclude={"options"}))
    db.add(row)
    db.flush()
    for option in data.options:
        db.add(QuestionOption(question_id=row.id, **option.model_dump()))
    db.flush()
    return service.question_view(db, row, True)


@router.post("/quizzes", response_model=s.Record, status_code=201)
def add_quiz(data: s.QuizInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    editable(course_access(db, p, data.course_id, "write"))
    check_dates(data.opens_at, data.closes_at)
    if data.release_policy == "after_close" and not data.closes_at:
        raise HTTPException(422, "After-close release requires a closing date")
    if data.sample_size > len(set(data.question_ids)):
        raise HTTPException(422, "Sample size exceeds the question bank")
    for qid in data.question_ids:
        if scoped(db, Question, qid, p).course_id != data.course_id:
            raise HTTPException(422, "Questions must belong to this course")
    row = Quiz(institution_id=tenant(p), **data.model_dump(exclude={"question_ids"}))
    db.add(row)
    db.flush()
    for qid in set(data.question_ids):
        db.add(QuizQuestion(quiz_id=row.id, question_id=qid))
    audit(db, p, "quizzes.created", row)
    return public(row)


@router.get("/quizzes", response_model=s.Page)
def quizzes(course_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    course_access(db, p, course_id)
    return page(
        db,
        q.apply(select(Quiz).where(Quiz.institution_id == tenant(p), Quiz.course_id == course_id), Quiz, Quiz.title),
        q.page,
        q.page_size,
    )


@router.post("/quizzes/{quiz_id}/start", response_model=s.Record, status_code=201)
def start(quiz_id: str, p: Principal = Depends(permit("assessments.attempt")), db: Session = Depends(get_db)):
    return service.attempt_view(db, service.start_attempt(db, p, scoped(db, Quiz, quiz_id, p)))


@router.post("/quizzes/{quiz_id}/release", response_model=s.Result)
def release(quiz_id: str, p: Principal = Depends(permit("assessments.grade")), db: Session = Depends(get_db)):
    quiz = scoped(db, Quiz, quiz_id, p)
    course_access(db, p, quiz.course_id, "grade")
    quiz.released = True
    audit(db, p, "quizzes.results_released", quiz)
    return {"message": "Results released"}


@router.get("/attempts", response_model=s.Page)
def attempts(
    course_id: str | None = None, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)
):
    query = select(QuizAttempt).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(QuizAttempt.institution_id == tenant(p))
    staff = "assessments.grade" in p.permissions
    if staff:
        query = query.where(Quiz.course_id.in_(visible_course_ids(db, p)))
        # Course-level grading delegation is enforced per row, not merely by a role.
        from app.models import CourseInstructor

        if not p.manager:
            query = query.where(
                Quiz.course_id.in_(
                    select(CourseInstructor.course_id).where(CourseInstructor.user_id == p.user.id, CourseInstructor.can_grade.is_(True))
                )
            )
    else:
        query = query.where(QuizAttempt.user_id == p.user.id)
    if course_id:
        query = query.where(Quiz.course_id == course_id)
    return page(
        db,
        q.apply(query, QuizAttempt),
        q.page,
        q.page_size,
        lambda a: {**service.attempt_view(db, a, staff), "student_name": required(db, User, a.user_id).name},
    )


@router.get("/attempts/{attempt_id}", response_model=s.Record)
def attempt(attempt_id: str, p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    a, quiz = service.own_attempt(db, p, attempt_id, True)
    if a.status == "in_progress" and now() >= a.deadline:
        service.finish_attempt(db, a)
    return service.attempt_view(db, a, a.user_id != p.user.id)


@router.put("/attempts/{attempt_id}/answers", response_model=s.Record)
def save(attempt_id: str, data: s.AnswersInput, p: Principal = Depends(permit("assessments.attempt")), db: Session = Depends(get_db)):
    a, quiz = service.own_attempt(db, p, attempt_id)
    service.save_answers(db, p, a, data)
    return service.attempt_view(db, a)


@router.post("/attempts/{attempt_id}/submit", response_model=s.Record)
def submit(attempt_id: str, p: Principal = Depends(permit("assessments.attempt")), db: Session = Depends(get_db)):
    a, quiz = service.own_attempt(db, p, attempt_id)
    service.finish_attempt(db, a)
    audit(db, p, "quizzes.submitted", a)
    return service.attempt_view(db, a)


@router.put("/attempts/{attempt_id}/answers/{answer_id}/grade", response_model=s.Record)
def grade_answer(
    attempt_id: str,
    answer_id: str,
    data: s.ManualAnswerGrade,
    p: Principal = Depends(permit("assessments.grade")),
    db: Session = Depends(get_db),
):
    a, quiz = service.own_attempt(db, p, attempt_id, True)
    course_access(db, p, quiz.course_id, "grade")
    if a.user_id == p.user.id or a.status == "in_progress":
        raise HTTPException(403, "This attempt cannot be graded")
    answer = db.scalar(select(QuizAnswer).where(QuizAnswer.id == answer_id, QuizAnswer.attempt_id == a.id))
    if not answer:
        raise HTTPException(404, "Answer not found")
    snapshot = next(q for q in a.questions if q["id"] == answer.question_id)
    if snapshot["kind"] != "short" or data.marks > snapshot["points"]:
        raise HTTPException(422, "Only subjective answers within their maximum marks may be graded")
    previous = answer.marks
    answer.marks, answer.feedback = data.marks, data.feedback
    db.flush()
    answers = db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == a.id)).all()
    a.score = max(0, sum(x.marks or 0 for x in answers))
    a.status = "graded" if all(x.marks is not None for x in answers) else "pending_review"
    audit(db, p, "quiz_grades.changed", a, {"answer_id": answer_id, "old_marks": previous, "marks": data.marks})
    return service.attempt_view(db, a, True)


def assignment_view(db, row):
    rubric = db.scalar(select(Rubric).where(Rubric.assignment_id == row.id))
    return {
        **public(row),
        "rubric": [public(c) for c in db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id))] if rubric else [],
        "file_ids": list(db.scalars(select(AssignmentAttachment.file_id).where(AssignmentAttachment.assignment_id == row.id))),
    }


@router.post("/assignments", response_model=s.Record, status_code=201)
def add_assignment(data: s.AssignmentInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    editable(course_access(db, p, data.course_id, "write"))
    if data.rubric and abs(sum(c.max_marks for c in data.rubric) - data.max_marks) > 0.001:
        raise HTTPException(422, "Rubric maximum marks must sum to the assignment maximum")
    for fid in data.file_ids:
        f = scoped(db, FileAsset, fid, p)
        if f.course_id != data.course_id or f.purpose != "resource":
            raise HTTPException(422, "Attachment must be a course resource")
    row = Assignment(institution_id=tenant(p), **data.model_dump(exclude={"rubric", "file_ids"}))
    db.add(row)
    db.flush()
    if data.rubric:
        rubric = Rubric(institution_id=tenant(p), assignment_id=row.id, title=row.title)
        db.add(rubric)
        db.flush()
        for criterion in data.rubric:
            db.add(RubricCriterion(rubric_id=rubric.id, **criterion.model_dump()))
    for fid in set(data.file_ids):
        db.add(AssignmentAttachment(assignment_id=row.id, file_id=fid))
    audit(db, p, "assignments.created", row)
    db.flush()
    return assignment_view(db, row)


@router.get("/assignments", response_model=s.Page)
def assignments(course_id: str, q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    course_access(db, p, course_id)
    return page(
        db,
        q.apply(
            select(Assignment).where(Assignment.institution_id == tenant(p), Assignment.course_id == course_id),
            Assignment,
            Assignment.title,
        ),
        q.page,
        q.page_size,
        lambda a: assignment_view(db, a),
    )


@router.post("/assignments/{assignment_id}/submit", response_model=s.Record, status_code=201)
def submit_assignment(
    assignment_id: str, data: s.SubmissionInput, p: Principal = Depends(permit("submissions.create")), db: Session = Depends(get_db)
):
    return public(service.submit_assignment(db, p, scoped(db, Assignment, assignment_id, p), data))


def submission_view(db, row, staff):
    grade = db.scalar(select(Grade).where(Grade.submission_id == row.id))
    show = grade and (staff or grade.released)
    return {
        **public(row),
        "student_name": required(db, User, row.user_id).name,
        "assignment_title": db.get(Assignment, row.assignment_id).title,
        "grade": public(grade) if show else None,
        "feedback": [
            public(f) for f in db.scalars(select(Feedback).where(Feedback.grade_id == grade.id).order_by(Feedback.created_at.desc()))
        ]
        if show
        else [],
        "file_ids": list(db.scalars(select(SubmissionFile.file_id).where(SubmissionFile.submission_id == row.id))),
    }


@router.get("/submissions", response_model=s.Page)
def submissions(
    course_id: str | None = None,
    assignment_id: str | None = None,
    q: Pagination = Depends(),
    p: Principal = Depends(permit("courses.read")),
    db: Session = Depends(get_db),
):
    query = select(Submission).join(Assignment, Assignment.id == Submission.assignment_id).where(Submission.institution_id == tenant(p))
    staff = "assessments.grade" in p.permissions
    if staff:
        query = query.where(Assignment.course_id.in_(visible_course_ids(db, p)))
        if not p.manager:
            from app.models import CourseInstructor

            query = query.where(
                Assignment.course_id.in_(
                    select(CourseInstructor.course_id).where(CourseInstructor.user_id == p.user.id, CourseInstructor.can_grade.is_(True))
                )
            )
    else:
        query = query.where(Submission.user_id == p.user.id)
    if course_id:
        query = query.where(Assignment.course_id == course_id)
    if assignment_id:
        query = query.where(Submission.assignment_id == assignment_id)
    return page(db, q.apply(query, Submission), q.page, q.page_size, lambda row: submission_view(db, row, staff))


@router.put("/submissions/{submission_id}/grade", response_model=s.Record)
def grade_submission(
    submission_id: str, data: s.GradeInput, p: Principal = Depends(permit("assessments.grade")), db: Session = Depends(get_db)
):
    return public(service.grade_submission(db, p, scoped(db, Submission, submission_id, p), data))


@router.get("/grades", response_model=s.Page)
def my_grades(q: Pagination = Depends(), p: Principal = Depends(permit("courses.read")), db: Session = Depends(get_db)):
    query = (
        select(Submission)
        .join(Grade, Grade.submission_id == Submission.id)
        .where(Submission.institution_id == tenant(p), Submission.user_id == p.user.id, Grade.released.is_(True))
    )
    return page(db, q.apply(query, Submission), q.page, q.page_size, lambda row: submission_view(db, row, False))


@router.put("/questions/{question_id}", response_model=s.Record)
def edit_question(
    question_id: str, data: s.QuestionInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)
):
    from sqlalchemy import delete

    row = scoped(db, Question, question_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    if data.course_id != row.course_id:
        raise HTTPException(422, "A question cannot be moved to another course")
    for key, value in data.model_dump(exclude={"options"}).items():
        setattr(row, key, value)
    db.execute(delete(QuestionOption).where(QuestionOption.question_id == row.id))
    for option in data.options:
        db.add(QuestionOption(question_id=row.id, **option.model_dump()))
    db.flush()
    audit(db, p, "questions.updated", row)
    return service.question_view(db, row, True)


@router.delete("/questions/{question_id}", response_model=s.Result)
def delete_question(question_id: str, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    from sqlalchemy import delete

    row = scoped(db, Question, question_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    if db.scalar(select(QuizQuestion.quiz_id).where(QuizQuestion.question_id == row.id)):
        raise HTTPException(409, "Remove this question from its quizzes before deleting it")
    db.execute(delete(QuestionOption).where(QuestionOption.question_id == row.id))
    audit(db, p, "questions.deleted", row)
    db.delete(row)
    return {"message": "Question deleted"}


@router.get("/quizzes/{quiz_id}/author", response_model=s.Record)
def quiz_author(quiz_id: str, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    quiz = scoped(db, Quiz, quiz_id, p)
    course_access(db, p, quiz.course_id, "write")
    return {**public(quiz), "question_ids": list(db.scalars(select(QuizQuestion.question_id).where(QuizQuestion.quiz_id == quiz.id)))}


@router.put("/quizzes/{quiz_id}", response_model=s.Record)
def edit_quiz(quiz_id: str, data: s.QuizInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    from sqlalchemy import delete

    row = scoped(db, Quiz, quiz_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    if row.course_id != data.course_id:
        raise HTTPException(422, "A quiz cannot be moved to another course")
    check_dates(data.opens_at, data.closes_at)
    if data.release_policy == "after_close" and not data.closes_at:
        raise HTTPException(422, "After-close release requires a closing date")
    if data.sample_size > len(set(data.question_ids)):
        raise HTTPException(422, "Sample size exceeds the question bank")
    for qid in data.question_ids:
        if scoped(db, Question, qid, p).course_id != row.course_id:
            raise HTTPException(422, "Questions must belong to this course")
    for key, value in data.model_dump(exclude={"question_ids"}).items():
        setattr(row, key, value)
    db.execute(delete(QuizQuestion).where(QuizQuestion.quiz_id == row.id))
    for qid in set(data.question_ids):
        db.add(QuizQuestion(quiz_id=row.id, question_id=qid))
    audit(db, p, "quizzes.updated", row)
    db.flush()
    return public(row)


@router.delete("/quizzes/{quiz_id}", response_model=s.Result)
def delete_quiz(quiz_id: str, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    from sqlalchemy import delete

    row = scoped(db, Quiz, quiz_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    db.execute(delete(QuizQuestion).where(QuizQuestion.quiz_id == row.id))
    audit(db, p, "quizzes.deleted", row)
    db.delete(row)
    return {"message": "Draft quiz deleted"}


@router.put("/assignments/{assignment_id}", response_model=s.Record)
def edit_assignment(
    assignment_id: str, data: s.AssignmentInput, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)
):
    from sqlalchemy import delete

    row = scoped(db, Assignment, assignment_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    if row.course_id != data.course_id:
        raise HTTPException(422, "An assignment cannot be moved to another course")
    if data.rubric and abs(sum(c.max_marks for c in data.rubric) - data.max_marks) > 0.001:
        raise HTTPException(422, "Rubric maximum marks must equal the assignment maximum")
    for fid in data.file_ids:
        asset = scoped(db, FileAsset, fid, p)
        if asset.course_id != row.course_id or asset.purpose != "resource":
            raise HTTPException(422, "Attachment must be a resource of this course")
    for key, value in data.model_dump(exclude={"rubric", "file_ids"}).items():
        setattr(row, key, value)
    rubric = db.scalar(select(Rubric).where(Rubric.assignment_id == row.id))
    if rubric:
        db.execute(delete(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id))
    elif data.rubric:
        rubric = Rubric(institution_id=tenant(p), assignment_id=row.id, title=row.title)
        db.add(rubric)
        db.flush()
    if data.rubric and rubric is None:
        raise HTTPException(409, "Rubric creation failed")
    for criterion in data.rubric:
        assert rubric is not None
        db.add(RubricCriterion(rubric_id=rubric.id, **criterion.model_dump()))
    if rubric and not data.rubric:
        db.delete(rubric)
    db.execute(delete(AssignmentAttachment).where(AssignmentAttachment.assignment_id == row.id))
    for fid in set(data.file_ids):
        db.add(AssignmentAttachment(assignment_id=row.id, file_id=fid))
    audit(db, p, "assignments.updated", row)
    db.flush()
    return assignment_view(db, row)


@router.delete("/assignments/{assignment_id}", response_model=s.Result)
def delete_assignment(assignment_id: str, p: Principal = Depends(permit("assessments.create")), db: Session = Depends(get_db)):
    from sqlalchemy import delete

    row = scoped(db, Assignment, assignment_id, p)
    editable(course_access(db, p, row.course_id, "write"))
    rubric = db.scalar(select(Rubric).where(Rubric.assignment_id == row.id))
    if rubric:
        db.execute(delete(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id))
        db.delete(rubric)
    db.execute(delete(AssignmentAttachment).where(AssignmentAttachment.assignment_id == row.id))
    audit(db, p, "assignments.deleted", row)
    db.delete(row)
    return {"message": "Draft assignment deleted"}
