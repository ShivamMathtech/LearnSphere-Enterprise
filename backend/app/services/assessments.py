from datetime import timedelta
import random
from fastapi import HTTPException
from sqlalchemy import select, func, update
from app.db.base import now
from app.models import (
    Quiz,
    Question,
    QuestionOption,
    QuizQuestion,
    QuizAttempt,
    QuizAnswer,
    Assignment,
    Submission,
    SubmissionFile,
    Grade,
    Feedback,
    Rubric,
    RubricCriterion,
    FileAsset,
)
from app.security.access import tenant, active_enrollment, course_access, scoped
from app.services.common import public, audit, notify, require_window


def question_view(db, question, answers=False):
    return {
        **public(question, [] if answers else ["explanation"]),
        "options": [
            public(o, [] if answers else ["correct"])
            for o in db.scalars(
                select(QuestionOption)
                .where(QuestionOption.question_id == question.id)
                .order_by(QuestionOption.created_at, QuestionOption.id)
            )
        ],
    }


def start_attempt(db, p, quiz):
    active_enrollment(db, p, quiz.course_id)
    require_window(quiz.opens_at, quiz.closes_at)
    db.execute(update(Quiz).where(Quiz.id == quiz.id).values(updated_at=now()))
    existing = db.scalar(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == p.user.id, QuizAttempt.status == "in_progress")
    )
    if existing:
        if now() >= existing.deadline:
            finish_attempt(db, existing)
        else:
            return existing
    count = db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == p.user.id))
    if count >= quiz.attempt_limit:
        raise HTTPException(409, "Attempt limit reached")
    questions = db.scalars(
        select(Question).join(QuizQuestion, QuizQuestion.question_id == Question.id).where(QuizQuestion.quiz_id == quiz.id)
    ).all()
    if not questions:
        raise HTTPException(409, "No questions configured")
    random.SystemRandom().shuffle(questions)
    questions = questions[: quiz.sample_size or len(questions)]
    snapshot = [question_view(db, q, True) for q in questions]
    for q in snapshot:
        random.SystemRandom().shuffle(q["options"])
    deadline = now() + timedelta(minutes=quiz.time_limit_minutes)
    if quiz.closes_at:
        deadline = min(deadline, quiz.closes_at)
    attempt = QuizAttempt(
        institution_id=tenant(p),
        quiz_id=quiz.id,
        user_id=p.user.id,
        number=count + 1,
        deadline=deadline,
        questions=snapshot,
        max_score=sum(q.points for q in questions),
    )
    db.add(attempt)
    db.flush()
    audit(db, p, "quizzes.started", attempt)
    return attempt


def released(quiz):
    return (
        quiz.released
        or quiz.release_policy == "immediate"
        or (quiz.release_policy == "after_close" and quiz.closes_at and now() >= quiz.closes_at)
    )


def attempt_view(db, attempt, staff=False):
    quiz = db.get(Quiz, attempt.quiz_id)
    show = staff or (attempt.status == "graded" and released(quiz))
    result = public(attempt, ["questions", "score"])
    result["result_released"] = bool(show)
    result["score"] = attempt.score if show else None
    result["quiz_title"] = quiz.title
    result["pass_percent"] = quiz.pass_percent
    result["server_time"] = now().isoformat()
    result["questions"] = [
        {k: v for k, v in q.items() if k not in {"options", "explanation"}}
        | {
            "options": [{k: v for k, v in o.items() if show or k != "correct"} for o in q["options"]],
            **({"explanation": q["explanation"]} if show else {}),
        }
        for q in attempt.questions
    ]
    result["answers"] = [
        public(a, [] if show else ["marks", "feedback"]) for a in db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))
    ]
    return result


def own_attempt(db, p, attempt_id, allow_staff=False):
    a = scoped(db, QuizAttempt, attempt_id, p)
    quiz = scoped(db, Quiz, a.quiz_id, p)
    if a.user_id != p.user.id:
        if not allow_staff:
            raise HTTPException(404, "Attempt not found")
        p.require("assessments.grade")
        course_access(db, p, quiz.course_id, "grade")
    else:
        active_enrollment(db, p, quiz.course_id)
    return a, quiz


def save_answers(db, p, attempt, data):
    if attempt.status != "in_progress":
        raise HTTPException(409, "Attempt already submitted")
    if now() >= attempt.deadline:
        finish_attempt(db, attempt)
        db.commit()
        raise HTTPException(409, "Time limit reached; saved answers were submitted")
    snapshots = {q["id"]: q for q in attempt.questions}
    if len({a.question_id for a in data.answers}) != len(data.answers):
        raise HTTPException(422, "Duplicate question answer")
    for answer in data.answers:
        q = snapshots.get(answer.question_id)
        if not q:
            raise HTTPException(422, "Question is not part of this attempt")
        if set(answer.selected) - {o["id"] for o in q["options"]}:
            raise HTTPException(422, "Unknown answer option")
        if (q["kind"] in {"single", "boolean"} and len(answer.selected) > 1) or (q["kind"] == "short" and answer.selected):
            raise HTTPException(422, "Invalid answer format")
        row = db.scalar(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id, QuizAnswer.question_id == answer.question_id))
        if not row:
            row = QuizAnswer(attempt_id=attempt.id, question_id=answer.question_id)
            db.add(row)
        row.value = {"selected": list(dict.fromkeys(answer.selected)), "text": answer.text}
    db.flush()


def finish_attempt(db, attempt):
    if attempt.status != "in_progress":
        return
    rows = {a.question_id: a for a in db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))}
    manual = False
    for q in attempt.questions:
        row = rows.get(q["id"])
        if not row:
            row = QuizAnswer(attempt_id=attempt.id, question_id=q["id"], value={})
            db.add(row)
        if q["kind"] == "short" and row.value.get("text", "").strip():
            manual = True
            row.marks = None
        elif q["kind"] == "short":
            row.marks = 0
        else:
            selected = set(row.value.get("selected", []))
            correct = {o["id"] for o in q["options"] if o["correct"]}
            row.marks = q["points"] if selected == correct else (-q["negative_points"] if selected else 0)
    attempt.submitted_at = min(now(), attempt.deadline)
    attempt.status = "pending_review" if manual else "graded"
    db.flush()
    attempt.score = max(0, sum(a.marks or 0 for a in db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))))
    notify(
        db,
        attempt.institution_id,
        attempt.user_id,
        "Quiz submitted",
        "Your saved answers were submitted. Results follow the course release policy.",
    )


def submit_assignment(db, p, assignment, data):
    active_enrollment(db, p, assignment.course_id)
    db.execute(update(Assignment).where(Assignment.id == assignment.id).values(updated_at=now()))
    late = bool(assignment.due_at and now() > assignment.due_at)
    if late and not assignment.allow_late:
        raise HTTPException(409, "The deadline has passed")
    if not data.text.strip() and not data.file_ids:
        raise HTTPException(422, "Add a text response or upload a submission file")
    count = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.assignment_id == assignment.id, Submission.user_id == p.user.id)
    )
    if count >= assignment.max_submissions:
        raise HTTPException(409, "Resubmission limit reached")
    for file_id in data.file_ids:
        f = scoped(db, FileAsset, file_id, p)
        if f.course_id != assignment.course_id or f.uploaded_by != p.user.id or f.purpose != "submission":
            raise HTTPException(403, "Only your own submission uploads are allowed")
    row = Submission(institution_id=tenant(p), assignment_id=assignment.id, user_id=p.user.id, text=data.text, late=late, version=count + 1)
    db.add(row)
    db.flush()
    for file_id in set(data.file_ids):
        db.add(SubmissionFile(submission_id=row.id, file_id=file_id))
    audit(db, p, "assignments.submitted", row)
    return row


def grade_submission(db, p, submission, data):
    assignment = scoped(db, Assignment, submission.assignment_id, p)
    course_access(db, p, assignment.course_id, "grade")
    if submission.user_id == p.user.id:
        raise HTTPException(403, "You cannot grade your own work")
    if data.marks > assignment.max_marks:
        raise HTTPException(422, "Marks exceed the assignment maximum")
    rubric = db.scalar(select(Rubric).where(Rubric.assignment_id == assignment.id))
    if rubric:
        criteria = db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id)).all()
        if set(data.rubric_scores) != {c.id for c in criteria}:
            raise HTTPException(422, "Provide a mark for each rubric criterion")
        if any(data.rubric_scores[c.id] < 0 or data.rubric_scores[c.id] > c.max_marks for c in criteria):
            raise HTTPException(422, "Rubric marks are outside their permitted ranges")
        if abs(sum(data.rubric_scores.values()) - data.marks) > 0.001:
            raise HTTPException(422, "Total marks must equal rubric scores")
    elif data.rubric_scores:
        raise HTTPException(422, "This assignment has no rubric")
    grade = db.scalar(select(Grade).where(Grade.submission_id == submission.id))
    old = grade.marks if grade else None
    if not grade:
        grade = Grade(institution_id=tenant(p), submission_id=submission.id, graded_by=p.user.id, marks=data.marks)
        db.add(grade)
    grade.marks, grade.rubric_scores, grade.released, grade.graded_by = data.marks, data.rubric_scores, data.released, p.user.id
    submission.status = "graded"
    db.flush()
    db.add(Feedback(institution_id=tenant(p), grade_id=grade.id, author_id=p.user.id, text=data.feedback))
    audit(db, p, "grades.changed", grade, {"old_marks": old, "new_marks": data.marks, "released": data.released})
    if data.released:
        notify(db, tenant(p), submission.user_id, "Feedback available", assignment.title)
    return grade
