# Implementation status — source delivery

The workspace was empty on inspection. Work was created in `learnsphere-enterprise` without replacing an existing project. This file is the continuation checkpoint; resume from the external verification gates below, not from scaffolding.

| Phase | Delivered work | Validation/status |
| --- | --- | --- |
| 1. Inspection and architecture | Repository inspection, assumptions and modular architecture | Complete; see `ARCHITECTURE.md` |
| 2. Foundation | FastAPI/React, settings/logging, 55 relational tables, Alembic, health, container files | SQLite migrations, schema parity and both dialects' DDL compilation verified |
| 3. Authentication/RBAC | Seven role mappings, resource/tenant isolation, hashed credentials/tokens, rotating sessions, CSRF, MFA, secure bootstrap | Automated authentication, privilege, tenant and replay tests |
| 4. Administration | Institutions, accounts, academics, cohort members, CSV preview/validation/import/error reports | CRUD/reference/role/filter/import tests |
| 5. Learning | Courses, ordered lessons, resources/thumbnails, draft editing, publication/revisions, enrollment/progress | API and browser workflows; protected-file, prerequisite, capacity, revision and quota tests |
| 6. Assessments | Quiz bank/types/randomization/timing/attempts/release, assignment versions/rubrics/manual grades | Automated objective/subjective/negative/rubric/late/release tests |
| 7. Certificates/community | PDF issuance/verification/revoke/reissue, attendance, discussions, notifications, SMTP outbox | Eligibility, ownership, communications, attendance and retry/deduplication tests |
| 8. Reports | Database-backed role dashboards, date-filtered reports/CSV, department/quiz summaries, audit/status | Tenant/scoped report assertions and browser dashboard rendering |
| 9. Frontend | Routed API-connected screens, validation, light/dark responsive design, tables/dialogs/error/empty states | Strict TS, lint, build, component tests and desktop/mobile browser checks |
| 10. QA/CI | Backend/component/browser suites, dependency scans; Linux/Windows/PostgreSQL/container CI jobs | Local executed results recorded in `ACCEPTANCE_REPORT.md`; CI jobs authored but not remotely executed |
| 11. Deployment | Windows batch scripts, separate development/production Docker configurations, maintenance/backup procedures | Windows wheels and npm platform entries verified; YAML reviewed. Native Windows, Docker health and PostgreSQL runtime/restore remain unverified |
| 12. Delivery | README, architecture/schema/API/security/user/operations/deployment guides and source archive | Source packaged without secrets, application databases, dependencies or test screenshots |

## Release gates still requiring the target environment

1. Execute `install.bat` and `run-local.bat` on a clean Windows 10/11 x64 host with Python 3.12 and Node 24.
2. Run the provided integration suite against PostgreSQL and start both Docker configurations; validate container health and file-volume ownership.
3. Exercise a PostgreSQL database/files backup and restoration in an isolated environment and record recovery timing.
4. Configure HTTPS and SMTP, verify production cookies/CSRF and actual mail delivery/retry with your provider.
5. Perform representative load/concurrency tests, an independent security review and an accessibility audit before production release.

The application must not be labeled production-ready until these gates pass. Optional external integrations (managed object storage, meeting provisioning and plagiarism checking) have clear boundaries but are not configured or claimed to work without implementations/credentials. See the user guide and acceptance report for additional bounded limitations.
