# Relational schema inventory

Generated from the single SQLAlchemy model. UUID strings identify entities; UTC timestamps are normalized through `UTCDateTime`. Association tables use composite primary keys. Tenant-owned domain rows carry indexed `institution_id`; child joins inherit scope through validated parents.

| Table | Columns | References |
| --- | --- | --- |
| `email_outbox` | `recipient`, `subject`, `encrypted_body`, `status`, `attempts`, `next_attempt_at`, `last_error`?, `id` PK, `created_at`, `updated_at` | — |
| `institutions` | `name`, `slug`, `active`, `branding`, `storage_quota_mb`, `id` PK, `created_at`, `updated_at` | — |
| `permissions` | `code` PK, `description` | — |
| `rate_limits` | `key` PK, `count`, `resets_at` | — |
| `roles` | `name`, `description`, `id` PK, `created_at`, `updated_at` | — |
| `users` | `email`, `name`, `password_hash`, `active`, `verified`, `failed_logins`, `locked_until`?, `totp_secret`?, `totp_pending`?, `totp_last_step`, `id` PK, `created_at`, `updated_at` | — |
| `academic_years` | `name`, `starts_at`, `ends_at`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT) |
| `audit_events` | `institution_id`?, `actor_id`?, `action`, `resource_type`, `resource_id`?, `detail`, `id` PK, `created_at`, `updated_at` | actor_id → users.id (SET NULL), institution_id → institutions.id (RESTRICT) |
| `course_categories` | `name`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT) |
| `departments` | `name`, `code`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT) |
| `notifications` | `user_id`, `title`, `body`, `read_at`?, `dedupe_key`?, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT), user_id → users.id (CASCADE) |
| `password_reset_tokens` | `user_id`, `token_hash`, `kind`, `expires_at`, `used_at`?, `id` PK, `created_at`, `updated_at` | user_id → users.id (CASCADE) |
| `role_permissions` | `role_id` PK, `permission_code` PK | permission_code → permissions.code (CASCADE), role_id → roles.id (CASCADE) |
| `system_settings` | `key`, `value`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT) |
| `user_profiles` | `user_id`, `bio`, `timezone`, `id` PK, `created_at`, `updated_at` | user_id → users.id (CASCADE) |
| `courses` | `title`, `slug`, `description`, `objectives`, `prerequisites`, `tags`, `difficulty`, `category_id`?, `department_id`?, `thumbnail_id`?, `status`, `visibility`, `enrollment_policy`, `max_learners`, `estimated_minutes`, `version`, `parent_id`?, `created_by`, `require_assessments`, `id` PK, `created_at`, `updated_at`, `institution_id` | category_id → course_categories.id (SET NULL), created_by → users.id (RESTRICT), department_id → departments.id (RESTRICT), institution_id → institutions.id (RESTRICT), parent_id → courses.id (RESTRICT) |
| `memberships` | `user_id`, `institution_id`?, `identifier`?, `department_id`?, `id` PK, `created_at`, `updated_at` | department_id → departments.id (SET NULL), institution_id → institutions.id (RESTRICT), user_id → users.id (CASCADE) |
| `programs` | `name`, `code`, `department_id`?, `level`, `id` PK, `created_at`, `updated_at`, `institution_id` | department_id → departments.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `semesters` | `name`, `academic_year_id`, `id` PK, `created_at`, `updated_at`, `institution_id` | academic_year_id → academic_years.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `announcements` | `course_id`, `author_id`, `title`, `body`, `id` PK, `created_at`, `updated_at`, `institution_id` | author_id → users.id (RESTRICT), course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `assignments` | `course_id`, `title`, `instructions`, `due_at`?, `allow_late`, `max_submissions`, `max_marks`, `pass_percent`, `required`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `attendance_sessions` | `course_id`, `title`, `starts_at`, `ends_at`, `instructor_id`, `meeting_url`?, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), instructor_id → users.id (RESTRICT) |
| `cohorts` | `name`, `code`, `program_id`?, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT), program_id → programs.id (RESTRICT) |
| `course_instructors` | `course_id` PK, `user_id` PK, `can_grade`, `can_discuss` | course_id → courses.id (CASCADE), user_id → users.id (RESTRICT) |
| `course_sections` | `course_id`, `title`, `position`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `course_versions` | `course_id`, `version`, `snapshot`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `discussions` | `course_id`, `author_id`, `title`, `body`, `id` PK, `created_at`, `updated_at`, `institution_id` | author_id → users.id (RESTRICT), course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `file_assets` | `course_id`, `uploaded_by`, `name`, `storage_key`, `mime_type`, `size`, `purpose`, `sha256`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), uploaded_by → users.id (RESTRICT) |
| `messages` | `course_id`, `sender_id`, `recipient_id`, `body`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), recipient_id → users.id (RESTRICT), sender_id → users.id (RESTRICT) |
| `questions` | `course_id`, `category`, `kind`, `prompt`, `points`, `negative_points`, `explanation`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `quizzes` | `course_id`, `title`, `time_limit_minutes`, `attempt_limit`, `pass_percent`, `opens_at`?, `closes_at`?, `sample_size`, `release_policy`, `released`, `required`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `refresh_sessions` | `user_id`, `membership_id`, `token_hash`, `csrf_hash`, `expires_at`, `revoked`, `user_agent`, `ip_hash`, `id` PK, `created_at`, `updated_at` | membership_id → memberships.id (CASCADE), user_id → users.id (CASCADE) |
| `user_roles` | `membership_id` PK, `role_id` PK | membership_id → memberships.id (CASCADE), role_id → roles.id (RESTRICT) |
| `assignment_attachments` | `assignment_id` PK, `file_id` PK | assignment_id → assignments.id (RESTRICT), file_id → file_assets.id (RESTRICT) |
| `attendance_records` | `session_id`, `user_id`, `status`, `recorded_by`, `note`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT), recorded_by → users.id (RESTRICT), session_id → attendance_sessions.id (RESTRICT), user_id → users.id (RESTRICT) |
| `cohort_members` | `cohort_id` PK, `user_id` PK | cohort_id → cohorts.id (CASCADE), user_id → users.id (RESTRICT) |
| `course_offerings` | `name`, `course_id`, `cohort_id`, `semester_id`?, `id` PK, `created_at`, `updated_at`, `institution_id` | cohort_id → cohorts.id (RESTRICT), course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), semester_id → semesters.id (RESTRICT) |
| `discussion_replies` | `discussion_id`, `author_id`, `body`, `id` PK, `created_at`, `updated_at`, `institution_id` | author_id → users.id (RESTRICT), discussion_id → discussions.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `lessons` | `course_id`, `section_id`, `title`, `kind`, `content`, `url`?, `position`, `duration_minutes`, `prerequisite_id`?, `drip_days`, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), prerequisite_id → lessons.id (RESTRICT), section_id → course_sections.id (RESTRICT) |
| `question_options` | `question_id`, `text`, `correct`, `id` PK, `created_at`, `updated_at` | question_id → questions.id (RESTRICT) |
| `quiz_attempts` | `quiz_id`, `user_id`, `number`, `status`, `deadline`, `submitted_at`?, `questions`, `score`?, `max_score`, `id` PK, `created_at`, `updated_at`, `institution_id` | institution_id → institutions.id (RESTRICT), quiz_id → quizzes.id (RESTRICT), user_id → users.id (RESTRICT) |
| `quiz_questions` | `quiz_id` PK, `question_id` PK | question_id → questions.id (RESTRICT), quiz_id → quizzes.id (RESTRICT) |
| `rubrics` | `assignment_id`, `title`, `id` PK, `created_at`, `updated_at`, `institution_id` | assignment_id → assignments.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `submissions` | `assignment_id`, `user_id`, `version`, `text`, `late`, `status`, `id` PK, `created_at`, `updated_at`, `institution_id` | assignment_id → assignments.id (RESTRICT), institution_id → institutions.id (RESTRICT), user_id → users.id (RESTRICT) |
| `used_refresh_tokens` | `token_hash` PK, `session_id` | session_id → refresh_sessions.id (CASCADE) |
| `enrollments` | `course_id`, `user_id`, `status`, `starts_at`?, `ends_at`?, `completed_at`?, `last_lesson_id`?, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), last_lesson_id → lessons.id (RESTRICT), user_id → users.id (RESTRICT) |
| `grades` | `submission_id`, `graded_by`, `marks`, `rubric_scores`, `released`, `id` PK, `created_at`, `updated_at`, `institution_id` | graded_by → users.id (RESTRICT), institution_id → institutions.id (RESTRICT), submission_id → submissions.id (RESTRICT) |
| `learning_activities` | `user_id`, `course_id`, `action`, `lesson_id`?, `id` PK, `created_at`, `updated_at`, `institution_id` | course_id → courses.id (RESTRICT), institution_id → institutions.id (RESTRICT), lesson_id → lessons.id (RESTRICT), user_id → users.id (RESTRICT) |
| `lesson_resources` | `lesson_id` PK, `file_id` PK | file_id → file_assets.id (RESTRICT), lesson_id → lessons.id (RESTRICT) |
| `quiz_answers` | `attempt_id`, `question_id`, `value`, `marks`?, `feedback`, `id` PK, `created_at`, `updated_at` | attempt_id → quiz_attempts.id (RESTRICT), question_id → questions.id (RESTRICT) |
| `rubric_criteria` | `rubric_id`, `title`, `description`, `max_marks`, `id` PK, `created_at`, `updated_at` | rubric_id → rubrics.id (RESTRICT) |
| `submission_files` | `submission_id` PK, `file_id` PK | file_id → file_assets.id (RESTRICT), submission_id → submissions.id (RESTRICT) |
| `certificates` | `enrollment_id`, `code`, `student_name`, `course_title`, `issuer`, `revoked_at`?, `revocation_reason`?, `supersedes_id`?, `id` PK, `created_at`, `updated_at`, `institution_id` | enrollment_id → enrollments.id (RESTRICT), institution_id → institutions.id (RESTRICT), supersedes_id → certificates.id (RESTRICT) |
| `feedback` | `grade_id`, `author_id`, `text`, `id` PK, `created_at`, `updated_at`, `institution_id` | author_id → users.id (RESTRICT), grade_id → grades.id (RESTRICT), institution_id → institutions.id (RESTRICT) |
| `lesson_progress` | `enrollment_id`, `lesson_id`, `id` PK, `created_at`, `updated_at`, `institution_id` | enrollment_id → enrollments.id (RESTRICT), institution_id → institutions.id (RESTRICT), lesson_id → lessons.id (RESTRICT) |

55 tables. `?` marks nullable fields. Course tags are a bounded JSON list; options, attachments, progress, role mappings, rubrics and grades have dedicated relational entities.

## Unique constraints

| Table | Unique fields |
| --- | --- |
| `institutions` | slug |
| `roles` | name |
| `academic_years` | institution_id, name |
| `course_categories` | institution_id, name |
| `departments` | institution_id, code |
| `notifications` | dedupe_key |
| `password_reset_tokens` | token_hash |
| `system_settings` | institution_id, key |
| `user_profiles` | user_id |
| `courses` | institution_id, slug |
| `memberships` | institution_id, identifier |
| `memberships` | user_id, institution_id |
| `programs` | institution_id, code |
| `semesters` | institution_id, academic_year_id, name |
| `cohorts` | institution_id, code |
| `course_sections` | course_id, position |
| `course_versions` | course_id |
| `file_assets` | storage_key |
| `refresh_sessions` | token_hash |
| `attendance_records` | session_id, user_id |
| `course_offerings` | course_id, cohort_id |
| `lessons` | section_id, position |
| `quiz_attempts` | quiz_id, user_id, number |
| `rubrics` | assignment_id |
| `submissions` | assignment_id, user_id, version |
| `enrollments` | course_id, user_id |
| `grades` | submission_id |
| `quiz_answers` | attempt_id, question_id |
| `certificates` | code |
| `lesson_progress` | enrollment_id, lesson_id |
