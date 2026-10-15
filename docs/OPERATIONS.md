# Operations and troubleshooting

## Mail, reminders and integrations

The single scheduler runs `app.tasks.worker.run_once()` every minute. It finalizes expired quiz attempts, creates deduplicated reminders for assignments due within 24 hours, and claims up to 50 eligible outbox messages. Email retry backoff uses 2^attempt minutes, with at most five attempts. A send left in `sending` for more than 15 minutes is recovered. Delivery is at-least-once: a crash after SMTP acceptance may cause a retry; the stable Message-ID can help downstream deduplication.

Without `SMTP_HOST`, mail is **unconfigured** and no delivery is claimed. Notifications still persist in the application. Configuring SMTP later allows pending messages to be processed; expired account tokens still require a new invitation/reset. Use port 587/STARTTLS by default. SMTP implicit TLS on port 465 is not implemented. Inspect the system configuration view for integration and queue status and the worker logs for error class names. Providers must be tested with real credentials before enabling email-dependent onboarding.

```text
python -m app.cli worker
python -m app.tasks.scheduler
```

Run one scheduler per deployment. It uses transactional claims for mail; multi-scheduler reminder/quiz coordination is not advertised as a scalable queue service. On Windows it runs in its own terminal or can be scheduled using Task Scheduler. On Docker the worker service handles it. Close the local worker with Ctrl+C.

Meeting and plagiarism protocols are defined in `app/integrations/providers.py`. The supported meeting workflow is manual scheduling with a provider URL. No meeting provisioning or plagiarism score is fabricated. Object storage's protocol is in `app/integrations/storage.py`; a future remote adapter must support secure retrieval/staging and cleanup as well as writes and copies.

## Maintenance

After deciding your retention periods, run the explicit command below from `backend`. It removes only rows covered by the implemented retention policy, so review that policy before scheduling it:

```text
python -m app.cli retention
```

Keep database and file backups coordinated. See `DATABASE.md` for backup/restore, secret retention and the mandatory restore drill. Uploaded bytes are retained after a demo reset to support recovery; clean orphaned objects only after comparing against the current `file_assets` rows and all retained backups. No background garbage collector deletes arbitrary files.

The development reset script requires two explicit confirmations, permits only the default SQLite development database with demo mode enabled, and creates a backup before resetting. **Never run it as normal startup or on production data.** It was not run against any user database during delivery.

## Common local issues

| Symptom | Resolution |
| --- | --- |
| Python package tries to compile with Rust/MSVC | Use Python **3.12 x64** as documented. Check `py -3.12 --version`; create a new project virtual environment rather than reusing one from Python 3.13/3.14. Do not remove version pins to bypass a failed install. |
| `npm` or `vite` is not recognized | Install Node.js 24 LTS, reopen the terminal, then run `npm ci` from `frontend`. |
| `EBADPLATFORM` / Rollup binding error after moving a project | Do not transfer `node_modules` from another OS. Install from `package-lock.json` using `npm ci` on the target OS. The ZIP excludes installed dependencies. |
| SQLite table missing / server startup fails | Run Alembic from `backend` with the same environment configuration as the server. Startup deliberately requires a migrated schema. |
| `403` requires an institution | As super administrator, select the institution from the header before opening tenant tools. |
| `403` requires authenticator setup | Open **Profile & security**, confirm the password and enroll TOTP. Production privileged-MFA policy blocks other protected operations until setup. |
| TOTP code rejected immediately after setup | Each code is single-use; wait for the next 30-second code. Ensure device clocks are synchronized. |
| Login locks after mistakes | Wait 15 minutes; do not disable authentication checks. Investigate repeated failures in the audit log. |
| Password reset email does not arrive | Check SMTP configuration and worker status. Unconfigured mail is queued, not delivered. Expired/single-use tokens require a fresh reset. |
| Login works but refresh fails locally | Use one host consistently (`localhost`), ensure cookies are enabled and access via Vite/Nginx so `/api` shares the origin. |
| Production login does not persist over `http://` | Production cookies require HTTPS. Configure the edge proxy; do not disable secure cookies. |
| Course edit returns 409 | Published revisions are immutable. Create a revision and edit the new draft. |
| Course cannot publish | Add description/objectives, an assigned instructor, at least one valid lesson and required lesson resources. |
| Learner file/lesson access denied | Check enrollment dates/status, prerequisite completion and drip days. A catalog listing does not grant content access. |
| Certificate still unavailable at 100% lesson progress | Required quizzes and the latest assignment submissions must also satisfy the completion policy and release rules. |
| Browser end-to-end test cannot start | Stop services on ports 8000 and 5173; install Playwright Chromium; activate the Python environment or set `E2E_PYTHON`. |
| Docker backend is unhealthy | Inspect `migrate` and backend logs, production secret validation, PostgreSQL health and storage ownership. Do not reset volumes to hide an error. |
| Local database locked | Keep the intended single local backend/worker pair, avoid long external write transactions, and use PostgreSQL for concurrency evaluation. |

## Release checklist

Record actual results, not assumed results: clean Windows setup; PostgreSQL migrations/integration tests; Docker health; HTTPS cookie/CSRF behavior; SMTP delivery/retry; backup and restoration; representative performance; accessible keyboard navigation; security review. CI is provided but is not executed automatically merely because a workflow file exists. Push to your chosen repository and review the resulting jobs before release.
