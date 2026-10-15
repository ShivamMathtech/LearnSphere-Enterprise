from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Short = Annotated[str, Field(min_length=1, max_length=200)]
Body = Annotated[str, Field(max_length=50000)]
Password = Annotated[str, Field(min_length=12, max_length=128)]
Identifier = Annotated[str, Field(max_length=36)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def normalize_dates(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, datetime):
                setattr(self, name, value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC))
        return self


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class Record(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str


class Result(BaseModel):
    message: str


class Login(Strict):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]
    totp: str | None = Field(default=None, max_length=6)
    institution_id: Identifier | None = None


class AuthResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


class EmailInput(Strict):
    email: EmailStr


class ResetInput(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: Password


class TokenInput(Strict):
    token: str = Field(min_length=20, max_length=200)


class PasswordChange(Strict):
    current_password: str = Field(max_length=128)
    password: Password


class MFASetup(Strict):
    current_password: str = Field(max_length=128)


class MFAInput(Strict):
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(max_length=128)


class UserCreate(Strict):
    name: Short
    email: EmailStr
    password: Password | None = None
    role: Literal["institution_admin", "coordinator", "instructor", "teaching_assistant", "student", "auditor"] = "student"
    identifier: str | None = Field(default=None, max_length=80)
    department_id: Identifier | None = None
    invite: bool = False


class UserUpdate(Strict):
    name: Short | None = None
    active: bool | None = None
    department_id: Identifier | None = None
    identifier: str | None = Field(default=None, max_length=80)


class RoleAssign(Strict):
    role: Literal["institution_admin", "coordinator", "instructor", "teaching_assistant", "student", "auditor"]


class ProfileInput(Strict):
    name: Short
    bio: str = Field(default="", max_length=2000)
    timezone: str = Field(default="Asia/Kolkata", max_length=100)


class InstitutionInput(Strict):
    name: Short
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    active: bool = True
    storage_quota_mb: int = Field(default=1024, ge=20, le=1000000)
    branding: dict[str, str] = Field(default_factory=dict, max_length=10)


class AcademicInput(Strict):
    name: Short
    code: str | None = Field(default=None, max_length=50)
    department_id: Identifier | None = None
    program_id: Identifier | None = None
    academic_year_id: Identifier | None = None
    semester_id: Identifier | None = None
    cohort_id: Identifier | None = None
    course_id: Identifier | None = None
    level: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CourseInput(Strict):
    title: Short
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=180)
    description: Body = ""
    objectives: Body = ""
    prerequisites: Body = ""
    tags: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=15)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    category_id: Identifier | None = None
    department_id: Identifier | None = None
    visibility: Literal["institution", "assigned"] = "institution"
    enrollment_policy: Literal["open", "approval", "closed"] = "open"
    max_learners: int = Field(default=100, ge=1, le=100000)
    estimated_minutes: int = Field(default=60, ge=1, le=100000)
    require_assessments: bool = True


class SectionInput(Strict):
    title: Short
    position: int = Field(default=0, ge=0)


class LessonInput(Strict):
    section_id: Identifier
    title: Short
    kind: Literal["text", "video", "pdf", "document", "link", "resource"] = "text"
    content: Body = ""
    url: str | None = Field(default=None, max_length=2000)
    position: int = Field(default=0, ge=0)
    duration_minutes: int = Field(default=10, ge=1, le=10000)
    prerequisite_id: Identifier | None = None
    drip_days: int = Field(default=0, ge=0, le=3650)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Use an HTTP or HTTPS URL")
        return value


class StaffInput(Strict):
    user_id: Identifier
    can_grade: bool = False
    can_discuss: bool = True


class EnrollmentInput(Strict):
    course_id: Identifier
    user_id: Identifier | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class EnrollmentDecision(Strict):
    status: Literal["active", "rejected", "withdrawn"]


class BulkEnroll(Strict):
    course_id: Identifier
    user_ids: list[Identifier] = Field(min_length=1, max_length=500)


class OptionInput(Strict):
    text: Short
    correct: bool = False


class QuestionInput(Strict):
    course_id: Identifier
    category: str = Field(default="General", max_length=100)
    kind: Literal["single", "multiple", "boolean", "short"]
    prompt: Annotated[str, Field(min_length=1, max_length=10000)]
    points: float = Field(default=1, gt=0, le=1000)
    negative_points: float = Field(default=0, ge=0, le=1000)
    explanation: Body = ""
    options: list[OptionInput] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def options_valid(self):
        correct = sum(o.correct for o in self.options)
        if self.kind != "short" and (len(self.options) < 2 or correct == 0):
            raise ValueError("Objective questions need at least two options and a correct answer")
        if self.kind in {"single", "boolean"} and correct != 1:
            raise ValueError("Single-choice questions need exactly one correct answer")
        if self.kind == "boolean" and len(self.options) != 2:
            raise ValueError("True/false questions need two options")
        if self.kind == "short" and self.options:
            raise ValueError("Short-answer questions do not use options")
        return self


class QuizInput(Strict):
    course_id: Identifier
    title: Short
    time_limit_minutes: int = Field(default=30, ge=1, le=300)
    attempt_limit: int = Field(default=3, ge=1, le=20)
    pass_percent: float = Field(default=60, ge=0, le=100)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    sample_size: int = Field(default=0, ge=0, le=200)
    release_policy: Literal["immediate", "after_close", "manual"] = "immediate"
    required: bool = True
    question_ids: list[Identifier] = Field(min_length=1, max_length=200)


class AnswerInput(Strict):
    question_id: Identifier
    selected: list[Identifier] = Field(default_factory=list, max_length=12)
    text: str = Field(default="", max_length=10000)


class AnswersInput(Strict):
    answers: list[AnswerInput] = Field(max_length=200)


class ManualAnswerGrade(Strict):
    marks: float = Field(ge=0, le=1000)
    feedback: str = Field(default="", max_length=5000)


class CriterionInput(Strict):
    title: Short
    description: str = Field(default="", max_length=3000)
    max_marks: float = Field(gt=0, le=10000)


class AssignmentInput(Strict):
    course_id: Identifier
    title: Short
    instructions: Body
    due_at: datetime | None = None
    allow_late: bool = False
    max_submissions: int = Field(default=3, ge=1, le=20)
    max_marks: float = Field(default=100, gt=0, le=10000)
    pass_percent: float = Field(default=50, ge=0, le=100)
    required: bool = True
    rubric: list[CriterionInput] = Field(default_factory=list, max_length=30)
    file_ids: list[Identifier] = Field(default_factory=list, max_length=10)


class SubmissionInput(Strict):
    text: Body = ""
    file_ids: list[Identifier] = Field(default_factory=list, max_length=10)


class GradeInput(Strict):
    marks: float = Field(ge=0, le=10000)
    feedback: str = Field(default="", max_length=10000)
    rubric_scores: dict[str, float] = Field(default_factory=dict, max_length=30)
    released: bool = True


class AttendanceInput(Strict):
    course_id: Identifier
    title: Short
    starts_at: datetime
    ends_at: datetime
    instructor_id: Identifier | None = None
    meeting_url: str | None = Field(default=None, max_length=2000)

    @field_validator("meeting_url")
    @classmethod
    def url(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("Meeting URL must use HTTPS")
        return value


class AttendanceMark(Strict):
    user_id: Identifier
    status: Literal["present", "absent", "late", "excused"]
    note: str = Field(default="", max_length=500)


class PostInput(Strict):
    course_id: Identifier
    title: Short
    body: Annotated[str, Field(min_length=1, max_length=10000)]


class ReplyInput(Strict):
    body: Annotated[str, Field(min_length=1, max_length=10000)]


class MessageInput(ReplyInput):
    course_id: Identifier
    recipient_id: Identifier


class SettingInput(Strict):
    value: dict[str, Any] = Field(max_length=20)


class RevokeInput(Strict):
    reason: str = Field(min_length=5, max_length=500)


class ImportInput(Strict):
    csv_text: str = Field(min_length=1, max_length=500000)
    mapping: dict[str, str] = Field(max_length=8)
    role: Literal["student", "instructor"] = "student"
    preview_hash: str | None = Field(default=None, max_length=64)


class ThumbnailInput(Strict):
    file_id: Identifier | None = None
