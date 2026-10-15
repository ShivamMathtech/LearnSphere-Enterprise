# LearnSphere Enterprise architecture

The supplied workspace was empty. This is a new, self-contained source project;
no existing application was overwritten. Python 3.12 and Node 24 are available
in the build environment. Windows and a Docker daemon require separate runtime
verification. No external mail, meeting, or plagiarism credentials were provided.

## Decisions

- Modular FastAPI monolith; SQLAlchemy 2 models and Alembic schema history.
- SQLite local development and PostgreSQL deployment use identical domain models.
- UUID strings identify entities. UTC-aware timestamps are normalized through a
  portable SQLAlchemy type (SQLite stores UTC without timezone, restored on read).
- A user has institutional memberships; roles attach to memberships. Each login
  selects one institution. Super administrators explicitly select an institution
  with `X-Institution-ID` for tenant operations. All ordinary resource lookup uses
  tenant-filtered queries before assignment and business-policy checks.
- Short-lived access JWTs stay in browser memory. Rotating refresh tokens use an
  HttpOnly cookie. Refresh sessions store hashes, support revocation and detect
  replay. A session-bound CSRF cookie/header protects cookie-authenticated actions.
- Publications create immutable course snapshots. Published content is locked;
  a new revision is a new draft linked to the course lineage. Existing enrollments,
  quiz attempts, and certificates continue to reference their original revision.
- Quiz attempts snapshot randomized questions server-side. Answer keys never
  appear in learner course responses. Server time, enrollment, attempt and release
  policies govern every attempt operation.
- Files are opaque UUID objects outside the web root, with authenticated downloads.
  A storage protocol permits later object-store adapters. Production antivirus,
  S3, meeting and plagiarism providers are integration extensions, not simulated.
- Reports aggregate persisted domain records. Seed data is explicitly marked as
  development data and is never created by normal startup.
- Email is delivered through a persisted outbox, with an explicit worker command,
  bounded retries and visible unconfigured/failed status.

## Boundaries

`api` translates HTTP requests; `security` resolves principals and authorization;
`services` implements workflow policy; `models` owns persistence; `schemas`
validates contracts; `integrations` handles storage/mail/provider boundaries.
React pages call the typed API client and TanStack Query; reusable forms and
tables provide validation, errors, pagination and empty states.

## Acceptance policy

The application is production-oriented source software, not a certification of
production readiness. `ACCEPTANCE_REPORT.md` records commands actually run and
any deployment checks that this environment cannot perform. Production release
requires those checks, HTTPS, external secrets, retention policy and security review.
