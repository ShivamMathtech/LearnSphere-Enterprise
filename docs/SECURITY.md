# Security controls and review boundaries

This project implements application controls; it does not claim legal compliance, a security certification or an independent penetration test. The operator is responsible for privacy notices, lawful data processing, account lifecycle, retention requirements, incident response and deployment hardening.

## Authentication and session model

Passwords use Argon2id (64 MiB, three iterations). New passwords require 12–128 characters including uppercase, lowercase and a digit. Authentication runs a dummy hash check for unknown emails. Five failed password attempts lock the account for 15 minutes. Database-backed rate counters also limit login, password recovery, token consumption and MFA verification. Limits are shared across API processes using the database; the proxy trust configuration affects IP granularity.

Access JWTs expire after 10 minutes by default, validate algorithm/audience/issuer, and stay in browser memory. Every authenticated request also checks the database session, active account, current role mapping, tenant availability and MFA policy. Role or account changes therefore do not rely solely on stale JWT claims.

Refresh tokens are random, stored only as SHA-256 hashes, rotated transactionally and tracked for replay. Reusing a rotated token revokes its session. The refresh cookie is HttpOnly, SameSite=Lax, scoped to `/api/v1/auth`, and Secure in production. A session-bound double-submit CSRF token and explicit Origin validation protect refresh; logout also requires bearer authentication and CSRF. Credentialed CORS uses an explicit origin allowlist. Normal data APIs require a bearer header rather than relying on ambient cookies.

Password-reset, invitation and verification tokens are short-lived, single-use and stored as hashes. Email bodies containing token links are encrypted in the persisted outbox until successful sending or retention removal. Links keep tokens in the URL fragment. TOTP secrets are encrypted with a separately configured Fernet key, and accepted codes cannot be replayed in the same time step. Password changes/resets revoke all sessions. Production MFA can be required for privileged roles.

## Authorization boundaries

| Role | Scope and mutation policy |
| --- | --- |
| Super administrator | Global tenant/audit/health operations; explicit institution selection for tenant work; appoints tenant administrators |
| Institution administrator | Own institution's users, academics, courses, enrollment, reports and settings; cannot promote accounts to administrator |
| Academic coordinator | Own institution's academic organization and enrollment operations; no role assignment or grading permission |
| Instructor | Own explicitly assigned courses; creation assigns the creator; authoring, grading, reports and communication remain course-scoped |
| Teaching assistant | Explicitly assigned courses; grading/discussion require delegation flags; cannot author courses or assessments |
| Learner | Own active enrollments, attempts, submissions, grades and certificates; eligible catalog browsing/self-enrollment |
| Auditor | Read-only institutional reports/audit access granted by the auditor role; no learning-record/admin mutations |

The canonical registry is `app/security/permissions.py`. `Role`, `Permission`, `RolePermission` and `UserRole` persist the mappings; roles are seeded idempotently. UI navigation is only a convenience. Every protected router resolves a principal, checks the required permission, scopes tenant records, validates ownership/assignment and applies business policy. Cross-tenant objects return 404; unauthorized institution overrides return 403. Instructors can delegate assistants, not appoint arbitrary administrators. Passwords, MFA values, token hashes and storage paths are excluded from general serialization.

The auditor grant authorizes institutional reports as a set; per-report grants are not separately configurable. Fixed role mappings are intentionally version controlled. If customizing permissions, review existing mappings and apply removals explicitly: the seed routine adds missing mappings but does not silently revoke existing configured grants.

## Learning-record integrity

- Enrollment, progress and attendance uniqueness is enforced in the schema. Course capacity, attempt counts and submission versions are serialized in transactions.
- Lesson progress comes from persisted completion records. Enrollment, prerequisites and drip rules apply to lesson and protected-file reads.
- Published revisions are immutable; a new revision copies authoring records and resources, preserving existing enrollment/assessment/certificate references.
- Attempts snapshot questions, randomized ordering and scoring parameters. Only saved server answers count. Deadlines, availability, enrollment and attempt limits are validated on the server. Learners do not receive keys before the result-release policy permits it.
- Subjective quiz marks, rubric totals and assignment maxima are validated. Delegated staff cannot grade their own work. Grade changes and feedback are audited.
- Certificate issuance rechecks completion eligibility; revocation and reissuance retain history. Public verification returns minimized learner identity without an email address.

## Content and files

Uploads have size limits, institution quotas, allowlisted extensions, signatures/content validation and UUID storage keys. Macro-enabled office files, HTML and executable formats are refused. File paths are never taken from user input or returned to clients. Downloads require course/resource or submission ownership authorization and use attachments with `nosniff`. Revision copies are quota-checked and cleaned up when their transaction fails. Plain text lessons and React escaping avoid raw user HTML execution. External URLs are validated for allowed HTTP(S) schemes; the backend does not fetch arbitrary user URLs.

These controls are not malware scanning. Before accepting untrusted public uploads in production, add antivirus/quarantine scanning, a tested document handling policy and appropriate storage isolation. PDF and Office content can still be malicious to a user's external viewer. There is no fabricated antivirus verdict. The storage interface is ready for a real object-store implementation; only local persistent storage is implemented.

## Operational security

Use HTTPS, private PostgreSQL networking, non-root containers, distinct random secrets, restrictive CORS and managed backups. Store the encryption key separately from backups but retain it for recovery; rotating it without re-encrypting persisted secrets will make those records unreadable. Do not copy development accounts into production. Do not commit `.env` or generated databases/files. Security-sensitive environment settings require an operator-controlled restart and are not editable through a low-privilege UI.

Audit records cover role/account changes, grading, attendance corrections, sessions, course publication and certificate changes. Request logs omit headers, cookies, request bodies and submitted answers; use request IDs to correlate events. Retention is an explicit maintenance operation for notifications, audit rows, expired token/rate records and old outbox messages. Academic/assessment/certificate deletion is not automatic; institutions must define and implement their records-retention policy with appropriate reviews.

Dependency scans run in CI. A passing scan means no advisories were reported by that scanner at that time, not that the software is vulnerability-free. Before production, complete native database/deployment tests, backup restoration, concurrency/load testing, accessibility audit, threat-model review, secret handling review and independent security testing. See the dated acceptance report for the current evidence.
