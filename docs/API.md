# API contracts

Development Swagger: `http://127.0.0.1:8000/docs`. The API lives under `/api/v1`; `/openapi.json` exposes the live machine-readable contract. The delivery includes a generated `openapi.json` snapshot. Regenerate it after router/schema changes using `python scripts/export-contracts.py` from the project root with the backend environment active. Swagger UI is disabled in production; the contract contains no credentials or data.

Requests use JSON except file uploads (`multipart/form-data`), protected downloads/PDFs and CSV exports. Errors use `{"detail": "message"}` or a Pydantic validation detail list. Success status codes use 200/201; missing or cross-tenant resources return 404, missing authentication 401, denied permission 403, state conflicts 409 and input errors 422. Database uniqueness/reference violations become a safe 409 message. Backend internals and SQL parameters are not returned.

## Authentication

`POST /auth/login` accepts email/password, optional TOTP code and optional institution ID for users with multiple memberships. It returns an access token, expiry seconds and the user's roles/permissions; it sets refresh and CSRF cookies. Send `Authorization: Bearer ACCESS_TOKEN` on protected data calls. Read the non-HttpOnly `ls_csrf` cookie and supply `X-CSRF-Token` on refresh/logout. Access tokens belong in memory. A refresh rotation must be serialized in the client; the included Axios client shares one refresh promise.

Only a super administrator can override its tenant using `X-Institution-ID`; other users may only echo their own tenant. An ordinary user cannot obtain cross-tenant records by guessing UUIDs or passing a different header.

## Pagination and filtering

Collection endpoints normally return `items`, `total`, `page`, and `page_size`. Use `page` >= 1 and `page_size` 1–100. Shared query fields include `search`, `sort` (`name`, `title`, `created_at`) and `direction` (`asc`, `desc`). Resource-specific filters include course, status, role/active account, date range or assessment ID; consult the generated operation schema for each endpoint. Report CSV exports are capped at 10,000 records.

## Endpoint groups

| Group | Main operations |
| --- | --- |
| `/auth` | Login, rotating refresh, logout, reset/verification, profile, password, TOTP, session list/revocation |
| `/users`, `/roles`, `/permissions` | Institution users, fixed-role mapping inspection, guarded role assignment, CSV preview/import/errors |
| `/institutions`, `/institution-branding`, `/settings` | Platform tenant management, administrator appointment, branding and certificate settings |
| `/departments`, `/programs`, `/academic-years`, `/semesters`, `/cohorts`, `/course-categories`, `/course-offerings` | Academic CRUD and cohort membership |
| `/courses`, `/sections`, `/lessons`, `/files` | Catalog, authoring, lifecycle, staff, revisions, secure upload/attachments/download |
| `/enrollments`, `/progress` | Enrollment/bulk/approval/access and idempotent lesson completion |
| `/questions`, `/quizzes`, `/attempts` | Question bank, quiz authoring, server snapshots, answer persistence/submission, manual marks/release |
| `/assignments`, `/submissions`, `/grades` | Resources/rubrics, submission versions, scoped grading and released results |
| `/certificates` | Eligibility issuance, PDF, minimized public verification, revocation/reissuance |
| `/attendance` | Scheduled sessions, records/corrections and CSV import |
| `/announcements`, `/discussions`, `/messages`, `/notifications` | Scoped course communication and persistent inbox |
| `/reports`, `/audit-logs`, `/system/status`, `/health` | Real aggregates, CSV, sensitive-change audit, integration/system state and health |

## Contract maintenance

Request schemas reject unexpected fields and non-finite numeric values and normalize dates to UTC. Response pages use a common envelope; model serializers exclude password/MFA/token/storage secrets, and quiz/submission services apply result-release filtering before serialization. Some general administrative response entries are flexible record maps; specific frontend domain types are maintained in `frontend/src/types/domain.ts`. The browser workflow and API tests exercise the shared contracts. Fully generated TypeScript clients and exhaustive per-entity response DTOs remain a hardening improvement, not a claimed feature of this release.

State-changing operations require explicit business transitions. Do not replay an attempt submit as a new attempt, set browser progress percentages, change published records in place or send answer-key fields to learner clients. Never derive authorization from frontend navigation state.
