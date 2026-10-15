# Working with LearnSphere

## First teaching workflow

1. Sign in as an institution administrator. In **People**, create an instructor and a learner with initial passwords, or send invitations if SMTP is configured. Assign identifiers and departments. Review **Roles & permissions** to see the fixed permission mappings.
2. Sign in as the instructor. Choose **Create a course**, set a unique slug, description, objectives and enrollment policy. Drafts belong to the creating instructor; other faculty need explicit assignment.
3. Add sections, ordered lessons and resources. Edit the course details to choose its category/department, enter comma-separated tags and upload a PNG/JPEG thumbnail. Text is rendered as text, so pasted HTML cannot execute. Video lessons use a direct media URL; links open externally. PDF/document/resource lessons require an uploaded file before publication. Set prerequisite lessons and drip days when needed.
4. Under **Assessments**, add questions, select them into a quiz and configure attempts, timing, pass mark and release policy. Add an assignment and optional rubric whose criteria sum to the maximum marks. Draft quizzes/questions/assignments can be edited or deleted. Published content requires a new revision.
5. Submit the course for review, then publish using an authorized role. The current permission policy allows assigned instructors to publish their own courses; institutions requiring independent approval should remove `courses.publish` from the instructor mapping in a reviewed code change and let administrators publish.
6. As the learner, browse published visible courses and enroll. Approval courses enter a pending queue, full courses enter a waitlist, and assigned/closed courses require administrator enrollment.
7. Continue learning. Lesson completion is persisted idempotently; the API calculates progress. Prerequisites, drip days and enrollment dates are enforced before lesson or file access.
8. Start the quiz. Save answers while working; submission saves current answers before finalizing. The server deadline is authoritative. Closing the tab does not pause the attempt. The worker finalizes expired attempts using the last saved answers.
9. Submit the assignment as text and/or files. Each resubmission is retained as a separate version. Instructors review submissions, grade within permitted ranges and release feedback. Teaching assistants can grade only when explicitly delegated `can_grade` for that course.
10. Once all required lessons and configured required assessments pass, use **Issue my certificate**. Download the PDF from **Certificates**. Public verification exposes only a masked learner name, course, institution, issue date and validity. Revoked certificates remain in history; an authorized issuer may reissue.

## Academic administration and imports

Use **Academic structure** for departments, programs/levels, academic years, semesters, cohorts, categories and class/course offerings. Use a cohort's **Members** control to add/remove learners. An offering groups a course with a cohort and semester; learner access still requires an enrollment record. Use **Enrollments** for bulk enrollment, approvals, waitlist promotion, access dates and withdrawal.

For CSV imports, choose student or instructor, upload/paste UTF-8 CSV and map name/email/identifier/department columns. Preview validates every row and detects duplicate emails/identifiers. Correct errors before committing. A preview digest binds the confirmation to the exact input; validation repeats inside the transaction. Download the row error report when needed. Imports are limited to 500 rows per transaction; split larger jobs into reviewed batches.

Users are disabled rather than deleted to preserve learning history. Referenced academic records cannot be deleted until their dependencies have been resolved. Institution deactivation is the supported archival action for tenant records.

## Attendance and community

Create a session under **Live sessions** with course, instructor and time window. Paste a meeting URL from your chosen provider or use the manual classroom workflow. LearnSphere does not create external meetings without an implemented/configured provider. Record attendance for enrolled learners; corrections retain audit events. CSV import expects the headers shown by the screen and validates the entire request before applying it.

Course announcements notify enrolled learners. Discussions and replies require enrollment or assigned/delegated staff access. Instructor-to-learner messaging is restricted to the authorized course relationship. Notifications persist read/unread state. The worker generates assignment reminders and processes timed quizzes and mail. System configuration shows whether SMTP is configured; queued messages do not imply delivery.

## Reports and audit

Dashboard cards, trends, course progress and deadlines are computed from database queries scoped to your role and course assignments. A new installation has legitimate zero/empty states. Reports support date filters, search, pages and authorized CSV exports. CSV formula prefixes are neutralized for spreadsheet safety. Exports are capped at 10,000 records; use date windows for larger datasets. The audit viewer records sensitive account, role, grade, attendance, publication and certificate changes.

## Security profile

Change your password, edit your profile/timezone, view and revoke sessions, or configure an authenticator from **Profile & security**. TOTP setup requires your current password and a valid code before activation. Each 30-second TOTP code is single-use; wait for the next code after enabling MFA. Password changes and resets revoke sessions. Privileged MFA can be required by production configuration; privileged users must finish setup before other protected operations.

Reset/invitation links are short-lived and single-use. If SMTP is not configured, ask the operator to configure it; the interface does not invent successful email delivery. Five failed passwords cause a 15-minute lockout, with additional database-backed request throttles. A production MFA account without its authenticator requires an operator-reviewed recovery procedure; backup recovery codes are not implemented in this release.

## Practical limits

- Relationship pickers and course assessment panels load up to 100 records; their underlying APIs paginate. Institutions needing larger pickers should add server-search controls before broad rollout.
- Documents are downloaded securely; no SCORM, LTI, xAPI, document conversion or adaptive-learning engine is included.
- Text lessons intentionally use plain text. No rich HTML editor is exposed.
- Certificates use the PDF base font in this release. Non-Latin names need an institution-licensed Unicode font and a tested rendering configuration.
- Times are stored in UTC and rendered in the browser's locale/timezone. The saved profile timezone is informational; browser timezone controls presentation in this release.
- No custom role editor or invitation delivery simulator is provided. Role mappings are explicit and version controlled; assignment controls use the API.
