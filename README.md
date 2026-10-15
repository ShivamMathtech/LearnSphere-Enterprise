# LearnSphere Enterprise

A complete source project for an institution-based learning platform: React + TypeScript, FastAPI, SQLAlchemy and Alembic, with SQLite for local development and PostgreSQL for deployment. All screens use the API; dashboard metrics come from persisted records.

**Start here:** on Windows, install Python 3.12 x64 and Node.js 24 LTS, extract this project, run `install.bat`, then `run-local.bat`. Internet access is needed for the first dependency installation. Open **http://localhost:5173**. Swagger is at **http://127.0.0.1:8000/docs** in development.

This is production-oriented application source. The acceptance report distinguishes executed tests from deployment checks that still require a native Windows host and Docker. Do not treat this delivery as a security certification or a completed production release.

## Included workflows

- Seven seeded roles, an explicit permission registry, tenant isolation and course assignment/delegation checks in the API.
- Argon2id passwords; short-lived JWTs; rotating, revocable refresh sessions; CSRF protection; reset/invitation/verification tokens; TOTP; account lockout; security audits.
- Institutions, people, departments, programs, academic years, semesters, cohorts, course offerings and categories. CSV mapping, preview, validation and atomic user imports.
- Draft, review, publish and archive lifecycle; immutable published revisions; ordered lessons; uploaded course thumbnails, categories/tags and protected resources; prerequisites and drip schedules.
- Self/admin/bulk enrollment, approval and waitlists; server-calculated progress; resume learning and eligibility checks.
- Four quiz question types, randomized attempts, deadlines, attempt limits, negative marks, manual grading and controlled result release.
- Versioned text/file assignment submissions, late policies, rubrics, feedback and authorized exports.
- PDF certificates with public verification, revocation and reissuance history.
- Scheduled attendance, correction audits and CSV import; announcements, discussions, messages, notifications and SMTP outbox.
- Role-aware reports, audit viewer, session/security profile, configuration, responsive light/dark interface and accessible forms/dialogs.
- Windows startup scripts, Docker/Nginx/PostgreSQL configuration, CI, unit/integration/component/browser tests and operational runbooks.

## Development accounts

`install.bat` copies `.env.example` only if `.env` does not exist, applies migrations, and seeds the explicitly enabled development data. Normal startup never resets or reseeds your database.

| Email | Role |
| --- | --- |
| `admin@example.com` | Institution administrator |
| `faculty@example.com` | Instructor |
| `student@example.com` | Learner |
| `coordinator@example.com` | Academic coordinator |
| `assistant@example.com` | Teaching assistant |
| `auditor@example.com` | Read-only reviewer |
| `super@example.com` | Super administrator |

All development accounts use **`LearnSphere2026!`**. These are public sample credentials, permitted only when `APP_ENV=development` and `DEMO_ENABLED=true`. Production configuration rejects demo mode. The teaching assistant initially has no course assignments. Select an institution as super administrator before tenant operations. Seed courses are labeled development material; counts remain zero until actual learning activity exists.

For an empty installation, set `DEMO_ENABLED=false` in `.env` before running the installer. Then run the secure bootstrap below. SMTP must be configured to deliver invitations and reset links; the application accurately shows when delivery is unavailable. Administrator-created accounts with an initial password work without SMTP in development.

## Windows setup in separate terminals

Run from the extracted project directory in **Command Prompt**:

```bat
copy .env.example .env
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd frontend
npm ci
cd ..\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli seed-permissions
..\.venv\Scripts\python.exe -m app.cli seed-demo
```

Skip `seed-demo` for a non-demo installation. Terminal 1, from the project root:

```bat
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2:

```bat
cd frontend
npm run dev
```

Terminal 3 (deadline processing, timed quiz expiry and email retries):

```bat
cd backend
..\.venv\Scripts\python.exe -m app.tasks.scheduler
```

Stop each process using Ctrl+C. `run-local.bat` opens these three terminals and the browser. Keep all three open. Use `localhost:5173` consistently instead of switching between `localhost` and `127.0.0.1`, because browser cookies are host-specific.

## Secure first administrator

After migrations, from `backend`, using the virtual environment Python:

```bat
..\.venv\Scripts\python.exe -m app.cli bootstrap --email owner@your-institution.example --name "Platform Owner"
```

The password is prompted twice without echo; it is never passed as a command-line argument. Use at least 12 characters with upper/lowercase and a digit. The bootstrap creates a verified super administrator. Sign in, configure TOTP, create an institution, and appoint its administrator. Use unique accounts for daily work. Bootstrap refuses duplicate email addresses.

## Docker development

Install Docker Desktop with Linux containers. Run `run-docker.bat`, then:

```bat
docker compose -f docker-compose.dev.yml exec backend python -m app.cli seed-demo
```

Open **http://localhost:8080**. PostgreSQL and files use persistent named volumes. `stop-docker.bat` stops the stack without deleting those volumes. This separate development compose file uses clearly marked local credentials and must not be used on an exposed production host.

Production uses `docker-compose.yml` and a separate `.env.production`; see [DEPLOYMENT.md](docs/DEPLOYMENT.md). No PostgreSQL port is published by either compose file.

## Tests and quality checks

From `backend` with the virtual environment active:

```text
python -m ruff check app tests
python -m mypy app
python -m pytest -q
python -m alembic check
python -m pip_audit -r requirements.txt
```

`pytest` uses its own migrated temporary SQLite database; it never resets the local application database. Set `TEST_DATABASE_URL` to a disposable PostgreSQL database whose name contains `test` to run the same suite on PostgreSQL. **The test fixture deletes records in that test database.** Never point it at any database you need to keep.

From `frontend`:

```text
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm audit
npx playwright install chromium
npm run test:e2e
```

For browser tests on Windows, activate `..\.venv\Scripts\activate.bat` first or set `E2E_PYTHON` to its absolute `python.exe` path. The Playwright configuration starts isolated temporary backend and Vite servers. Stop other services using ports 8000/5173 first. On Linux CI use `npx playwright install --with-deps chromium`.

The backend requirements files pin transitive dependencies; frontend `package-lock.json` is committed. Direct requirements are in `requirements.in` / `requirements-dev.in`. Regenerate locks with `uv pip compile --universal --python-version 3.12`, rerun the suite and dependency scans, and review changes. Container base tags receive security updates; pin their tested image digests in your release pipeline.

## Project map

| Directory | Responsibility |
| --- | --- |
| `backend/app/api` | Versioned HTTP endpoints and dependency injection |
| `backend/app/security` | Authentication, RBAC, tenant/resource boundaries |
| `backend/app/models`, `schemas`, `db` | Relational entities, contracts, sessions |
| `backend/app/services` | Enrollment, progress, assessment, import and certificate rules |
| `backend/app/integrations`, `tasks` | Storage/provider interfaces, SMTP outbox and scheduler |
| `backend/alembic` | Portable schema history |
| `backend/tests` | Integration, rule and security tests |
| `frontend/src` | Reusable UI, routed pages, typed client, hooks and component tests |
| `frontend/e2e` | Browser workflow tests against the real backend |
| `scripts`, `nginx`, `.github/workflows` | Maintenance, routing and CI |
| `docs` | Architecture, schema, API, security, deployment and acceptance evidence |

Read [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md), [ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md), [SECURITY.md](docs/SECURITY.md), [DATABASE.md](docs/DATABASE.md), [OPERATIONS.md](docs/OPERATIONS.md) and [USER_GUIDE.md](docs/USER_GUIDE.md).
