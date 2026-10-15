from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column as col
from app.db.base import Base, Entity, Tenant, UTCDateTime


class Institution(Entity, Base):
    __tablename__ = "institutions"
    name: Mapped[str] = col(String(200))
    slug: Mapped[str] = col(String(100), unique=True)
    active: Mapped[bool] = col(Boolean, default=True)
    branding: Mapped[dict] = col(JSON, default=dict)
    storage_quota_mb: Mapped[int] = col(Integer, default=1024)


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = col(String(254), unique=True, index=True)
    name: Mapped[str] = col(String(150))
    password_hash: Mapped[str] = col(String(255))
    active: Mapped[bool] = col(Boolean, default=True)
    verified: Mapped[bool] = col(Boolean, default=False)
    failed_logins: Mapped[int] = col(Integer, default=0)
    locked_until: Mapped[datetime | None] = col(UTCDateTime)
    totp_secret: Mapped[str | None] = col(Text)
    totp_pending: Mapped[str | None] = col(Text)
    totp_last_step: Mapped[int] = col(Integer, default=0)


class UserProfile(Entity, Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    bio: Mapped[str] = col(Text, default="")
    timezone: Mapped[str] = col(String(100), default="Asia/Kolkata")


class Membership(Entity, Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    institution_id: Mapped[str | None] = col(ForeignKey("institutions.id", ondelete="RESTRICT"), index=True)
    identifier: Mapped[str | None] = col(String(80))
    department_id: Mapped[str | None] = col(ForeignKey("departments.id", ondelete="SET NULL"))
    __table_args__ = (UniqueConstraint("user_id", "institution_id"), UniqueConstraint("institution_id", "identifier"))


class Role(Entity, Base):
    __tablename__ = "roles"
    name: Mapped[str] = col(String(80), unique=True)
    description: Mapped[str] = col(Text, default="")


class Permission(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = col(String(100), primary_key=True)
    description: Mapped[str] = col(String(250))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = col(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_code: Mapped[str] = col(ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    membership_id: Mapped[str] = col(ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = col(ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)


class Department(Entity, Tenant, Base):
    __tablename__ = "departments"
    name: Mapped[str] = col(String(200))
    code: Mapped[str] = col(String(50))
    __table_args__ = (UniqueConstraint("institution_id", "code"),)


class Program(Entity, Tenant, Base):
    __tablename__ = "programs"
    name: Mapped[str] = col(String(200))
    code: Mapped[str] = col(String(50))
    department_id: Mapped[str | None] = col(ForeignKey("departments.id", ondelete="RESTRICT"))
    level: Mapped[str] = col(String(80), default="Undergraduate")
    __table_args__ = (UniqueConstraint("institution_id", "code"),)


class AcademicYear(Entity, Tenant, Base):
    __tablename__ = "academic_years"
    name: Mapped[str] = col(String(150))
    starts_at: Mapped[datetime] = col(UTCDateTime)
    ends_at: Mapped[datetime] = col(UTCDateTime)
    __table_args__ = (UniqueConstraint("institution_id", "name"),)


class Semester(Entity, Tenant, Base):
    __tablename__ = "semesters"
    name: Mapped[str] = col(String(150))
    academic_year_id: Mapped[str] = col(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("institution_id", "academic_year_id", "name"),)


class Cohort(Entity, Tenant, Base):
    __tablename__ = "cohorts"
    name: Mapped[str] = col(String(150))
    code: Mapped[str] = col(String(50))
    program_id: Mapped[str | None] = col(ForeignKey("programs.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("institution_id", "code"),)


class CohortMember(Base):
    __tablename__ = "cohort_members"
    cohort_id: Mapped[str] = col(ForeignKey("cohorts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)


class CourseCategory(Entity, Tenant, Base):
    __tablename__ = "course_categories"
    name: Mapped[str] = col(String(150))
    __table_args__ = (UniqueConstraint("institution_id", "name"),)


class Course(Entity, Tenant, Base):
    __tablename__ = "courses"
    title: Mapped[str] = col(String(200))
    slug: Mapped[str] = col(String(180))
    description: Mapped[str] = col(Text, default="")
    objectives: Mapped[str] = col(Text, default="")
    prerequisites: Mapped[str] = col(Text, default="")
    tags: Mapped[list] = col(JSON, default=list)
    difficulty: Mapped[str] = col(String(30), default="beginner")
    category_id: Mapped[str | None] = col(ForeignKey("course_categories.id", ondelete="SET NULL"))
    department_id: Mapped[str | None] = col(ForeignKey("departments.id", ondelete="RESTRICT"))
    thumbnail_id: Mapped[str | None] = col(String(36))
    status: Mapped[str] = col(String(30), default="draft", index=True)
    visibility: Mapped[str] = col(String(30), default="institution")
    enrollment_policy: Mapped[str] = col(String(30), default="open")
    max_learners: Mapped[int] = col(Integer, default=100)
    estimated_minutes: Mapped[int] = col(Integer, default=60)
    version: Mapped[int] = col(Integer, default=1)
    parent_id: Mapped[str | None] = col(ForeignKey("courses.id", ondelete="RESTRICT"))
    created_by: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    require_assessments: Mapped[bool] = col(Boolean, default=True)
    __table_args__ = (UniqueConstraint("institution_id", "slug"), CheckConstraint("max_learners > 0", name="positive_capacity"))


class CourseVersion(Entity, Tenant, Base):
    __tablename__ = "course_versions"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), unique=True)
    version: Mapped[int] = col(Integer)
    snapshot: Mapped[dict] = col(JSON)


class CourseOffering(Entity, Tenant, Base):
    __tablename__ = "course_offerings"
    name: Mapped[str] = col(String(150))
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"))
    cohort_id: Mapped[str] = col(ForeignKey("cohorts.id", ondelete="RESTRICT"))
    semester_id: Mapped[str | None] = col(ForeignKey("semesters.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("course_id", "cohort_id"),)


class CourseInstructor(Base):
    __tablename__ = "course_instructors"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    can_grade: Mapped[bool] = col(Boolean, default=False)
    can_discuss: Mapped[bool] = col(Boolean, default=True)


class CourseSection(Entity, Tenant, Base):
    __tablename__ = "course_sections"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = col(String(200))
    position: Mapped[int] = col(Integer, default=0)
    __table_args__ = (UniqueConstraint("course_id", "position"),)


class Lesson(Entity, Tenant, Base):
    __tablename__ = "lessons"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    section_id: Mapped[str] = col(ForeignKey("course_sections.id", ondelete="RESTRICT"))
    title: Mapped[str] = col(String(200))
    kind: Mapped[str] = col(String(30), default="text")
    content: Mapped[str] = col(Text, default="")
    url: Mapped[str | None] = col(String(2000))
    position: Mapped[int] = col(Integer, default=0)
    duration_minutes: Mapped[int] = col(Integer, default=10)
    prerequisite_id: Mapped[str | None] = col(ForeignKey("lessons.id", ondelete="RESTRICT"))
    drip_days: Mapped[int] = col(Integer, default=0)
    __table_args__ = (UniqueConstraint("section_id", "position"),)


class FileAsset(Entity, Tenant, Base):
    __tablename__ = "file_assets"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    uploaded_by: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = col(String(250))
    storage_key: Mapped[str] = col(String(80), unique=True)
    mime_type: Mapped[str] = col(String(120))
    size: Mapped[int] = col(Integer)
    purpose: Mapped[str] = col(String(30), default="resource")
    sha256: Mapped[str] = col(String(64))


class LessonResource(Base):
    __tablename__ = "lesson_resources"
    lesson_id: Mapped[str] = col(ForeignKey("lessons.id", ondelete="RESTRICT"), primary_key=True)
    file_id: Mapped[str] = col(ForeignKey("file_assets.id", ondelete="RESTRICT"), primary_key=True)


class Enrollment(Entity, Tenant, Base):
    __tablename__ = "enrollments"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = col(String(30), default="active", index=True)
    starts_at: Mapped[datetime | None] = col(UTCDateTime)
    ends_at: Mapped[datetime | None] = col(UTCDateTime)
    completed_at: Mapped[datetime | None] = col(UTCDateTime)
    last_lesson_id: Mapped[str | None] = col(ForeignKey("lessons.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)


class LessonProgress(Entity, Tenant, Base):
    __tablename__ = "lesson_progress"
    enrollment_id: Mapped[str] = col(ForeignKey("enrollments.id", ondelete="RESTRICT"))
    lesson_id: Mapped[str] = col(ForeignKey("lessons.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("enrollment_id", "lesson_id"),)


class LearningActivity(Entity, Tenant, Base):
    __tablename__ = "learning_activities"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"))
    action: Mapped[str] = col(String(100))
    lesson_id: Mapped[str | None] = col(ForeignKey("lessons.id", ondelete="RESTRICT"))


class Quiz(Entity, Tenant, Base):
    __tablename__ = "quizzes"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = col(String(200))
    time_limit_minutes: Mapped[int] = col(Integer, default=30)
    attempt_limit: Mapped[int] = col(Integer, default=3)
    pass_percent: Mapped[float] = col(Float, default=60)
    opens_at: Mapped[datetime | None] = col(UTCDateTime)
    closes_at: Mapped[datetime | None] = col(UTCDateTime)
    sample_size: Mapped[int] = col(Integer, default=0)
    release_policy: Mapped[str] = col(String(30), default="immediate")
    released: Mapped[bool] = col(Boolean, default=False)
    required: Mapped[bool] = col(Boolean, default=True)


class Question(Entity, Tenant, Base):
    __tablename__ = "questions"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    category: Mapped[str] = col(String(100), default="General")
    kind: Mapped[str] = col(String(30))
    prompt: Mapped[str] = col(Text)
    points: Mapped[float] = col(Float, default=1)
    negative_points: Mapped[float] = col(Float, default=0)
    explanation: Mapped[str] = col(Text, default="")


class QuestionOption(Entity, Base):
    __tablename__ = "question_options"
    question_id: Mapped[str] = col(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    text: Mapped[str] = col(Text)
    correct: Mapped[bool] = col(Boolean, default=False)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    quiz_id: Mapped[str] = col(ForeignKey("quizzes.id", ondelete="RESTRICT"), primary_key=True)
    question_id: Mapped[str] = col(ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True)


class QuizAttempt(Entity, Tenant, Base):
    __tablename__ = "quiz_attempts"
    quiz_id: Mapped[str] = col(ForeignKey("quizzes.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    number: Mapped[int] = col(Integer)
    status: Mapped[str] = col(String(30), default="in_progress")
    deadline: Mapped[datetime] = col(UTCDateTime)
    submitted_at: Mapped[datetime | None] = col(UTCDateTime)
    questions: Mapped[list] = col(JSON)
    score: Mapped[float | None] = col(Float)
    max_score: Mapped[float] = col(Float)
    __table_args__ = (UniqueConstraint("quiz_id", "user_id", "number"),)


class QuizAnswer(Entity, Base):
    __tablename__ = "quiz_answers"
    attempt_id: Mapped[str] = col(ForeignKey("quiz_attempts.id", ondelete="RESTRICT"))
    question_id: Mapped[str] = col(ForeignKey("questions.id", ondelete="RESTRICT"))
    value: Mapped[dict] = col(JSON, default=dict)
    marks: Mapped[float | None] = col(Float)
    feedback: Mapped[str] = col(Text, default="")
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)


class Assignment(Entity, Tenant, Base):
    __tablename__ = "assignments"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = col(String(200))
    instructions: Mapped[str] = col(Text)
    due_at: Mapped[datetime | None] = col(UTCDateTime)
    allow_late: Mapped[bool] = col(Boolean, default=False)
    max_submissions: Mapped[int] = col(Integer, default=3)
    max_marks: Mapped[float] = col(Float, default=100)
    pass_percent: Mapped[float] = col(Float, default=50)
    required: Mapped[bool] = col(Boolean, default=True)


class AssignmentAttachment(Base):
    __tablename__ = "assignment_attachments"
    assignment_id: Mapped[str] = col(ForeignKey("assignments.id", ondelete="RESTRICT"), primary_key=True)
    file_id: Mapped[str] = col(ForeignKey("file_assets.id", ondelete="RESTRICT"), primary_key=True)


class Rubric(Entity, Tenant, Base):
    __tablename__ = "rubrics"
    assignment_id: Mapped[str] = col(ForeignKey("assignments.id", ondelete="RESTRICT"), unique=True)
    title: Mapped[str] = col(String(200))


class RubricCriterion(Entity, Base):
    __tablename__ = "rubric_criteria"
    rubric_id: Mapped[str] = col(ForeignKey("rubrics.id", ondelete="RESTRICT"))
    title: Mapped[str] = col(String(200))
    description: Mapped[str] = col(Text, default="")
    max_marks: Mapped[float] = col(Float)


class Submission(Entity, Tenant, Base):
    __tablename__ = "submissions"
    assignment_id: Mapped[str] = col(ForeignKey("assignments.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = col(Integer)
    text: Mapped[str] = col(Text, default="")
    late: Mapped[bool] = col(Boolean, default=False)
    status: Mapped[str] = col(String(30), default="submitted")
    __table_args__ = (UniqueConstraint("assignment_id", "user_id", "version"),)


class SubmissionFile(Base):
    __tablename__ = "submission_files"
    submission_id: Mapped[str] = col(ForeignKey("submissions.id", ondelete="RESTRICT"), primary_key=True)
    file_id: Mapped[str] = col(ForeignKey("file_assets.id", ondelete="RESTRICT"), primary_key=True)


class Grade(Entity, Tenant, Base):
    __tablename__ = "grades"
    submission_id: Mapped[str] = col(ForeignKey("submissions.id", ondelete="RESTRICT"), unique=True)
    graded_by: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    marks: Mapped[float] = col(Float)
    rubric_scores: Mapped[dict] = col(JSON, default=dict)
    released: Mapped[bool] = col(Boolean, default=True)


class Feedback(Entity, Tenant, Base):
    __tablename__ = "feedback"
    grade_id: Mapped[str] = col(ForeignKey("grades.id", ondelete="RESTRICT"))
    author_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    text: Mapped[str] = col(Text)


class Certificate(Entity, Tenant, Base):
    __tablename__ = "certificates"
    enrollment_id: Mapped[str] = col(ForeignKey("enrollments.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = col(String(80), unique=True)
    student_name: Mapped[str] = col(String(150))
    course_title: Mapped[str] = col(String(200))
    issuer: Mapped[str] = col(String(200))
    revoked_at: Mapped[datetime | None] = col(UTCDateTime)
    revocation_reason: Mapped[str | None] = col(String(500))
    supersedes_id: Mapped[str | None] = col(ForeignKey("certificates.id", ondelete="RESTRICT"))


class AttendanceSession(Entity, Tenant, Base):
    __tablename__ = "attendance_sessions"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = col(String(200))
    starts_at: Mapped[datetime] = col(UTCDateTime)
    ends_at: Mapped[datetime] = col(UTCDateTime)
    instructor_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    meeting_url: Mapped[str | None] = col(String(2000))


class AttendanceRecord(Entity, Tenant, Base):
    __tablename__ = "attendance_records"
    session_id: Mapped[str] = col(ForeignKey("attendance_sessions.id", ondelete="RESTRICT"))
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = col(String(20))
    recorded_by: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    note: Mapped[str] = col(String(500), default="")
    __table_args__ = (UniqueConstraint("session_id", "user_id"),)


class Announcement(Entity, Tenant, Base):
    __tablename__ = "announcements"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    author_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = col(String(200))
    body: Mapped[str] = col(Text)


class Discussion(Entity, Tenant, Base):
    __tablename__ = "discussions"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    author_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = col(String(200))
    body: Mapped[str] = col(Text)


class DiscussionReply(Entity, Tenant, Base):
    __tablename__ = "discussion_replies"
    discussion_id: Mapped[str] = col(ForeignKey("discussions.id", ondelete="RESTRICT"))
    author_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = col(Text)


class Message(Entity, Tenant, Base):
    __tablename__ = "messages"
    course_id: Mapped[str] = col(ForeignKey("courses.id", ondelete="RESTRICT"))
    sender_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"))
    recipient_id: Mapped[str] = col(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    body: Mapped[str] = col(Text)


class Notification(Entity, Tenant, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = col(String(200))
    body: Mapped[str] = col(Text)
    read_at: Mapped[datetime | None] = col(UTCDateTime)
    dedupe_key: Mapped[str | None] = col(String(200), unique=True)


class RefreshSession(Entity, Base):
    __tablename__ = "refresh_sessions"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[str] = col(ForeignKey("memberships.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = col(String(64), unique=True)
    csrf_hash: Mapped[str] = col(String(64))
    expires_at: Mapped[datetime] = col(UTCDateTime)
    revoked: Mapped[bool] = col(Boolean, default=False)
    user_agent: Mapped[str] = col(String(250), default="")
    ip_hash: Mapped[str] = col(String(64))


class UsedRefreshToken(Base):
    __tablename__ = "used_refresh_tokens"
    token_hash: Mapped[str] = col(String(64), primary_key=True)
    session_id: Mapped[str] = col(ForeignKey("refresh_sessions.id", ondelete="CASCADE"))


class PasswordResetToken(Entity, Base):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = col(String(64), unique=True)
    kind: Mapped[str] = col(String(30), default="reset")
    expires_at: Mapped[datetime] = col(UTCDateTime)
    used_at: Mapped[datetime | None] = col(UTCDateTime)


class AuditEvent(Entity, Base):
    __tablename__ = "audit_events"
    institution_id: Mapped[str | None] = col(ForeignKey("institutions.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[str | None] = col(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = col(String(100), index=True)
    resource_type: Mapped[str] = col(String(80))
    resource_id: Mapped[str | None] = col(String(36))
    detail: Mapped[dict] = col(JSON, default=dict)


class SystemSetting(Entity, Tenant, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = col(String(100))
    value: Mapped[dict] = col(JSON)
    __table_args__ = (UniqueConstraint("institution_id", "key"),)


class EmailOutbox(Entity, Base):
    __tablename__ = "email_outbox"
    recipient: Mapped[str] = col(String(254))
    subject: Mapped[str] = col(String(250))
    encrypted_body: Mapped[str] = col(Text)
    status: Mapped[str] = col(String(30), default="pending")
    attempts: Mapped[int] = col(Integer, default=0)
    next_attempt_at: Mapped[datetime] = col(UTCDateTime)
    last_error: Mapped[str | None] = col(String(100))


class RateLimit(Base):
    __tablename__ = "rate_limits"
    key: Mapped[str] = col(String(128), primary_key=True)
    count: Mapped[int] = col(Integer, default=1)
    resets_at: Mapped[datetime] = col(UTCDateTime)
