# Database, migration and recovery guide

## Shared schema

One SQLAlchemy metadata model and one Alembic history support SQLite and PostgreSQL. Use Python 3.12 and the pinned psycopg binary driver. Database selection comes only from `DATABASE_URL`; no service constructs vendor-specific SQL. SQLite connection PRAGMAs enable foreign keys, WAL and a 30-second busy timeout. UUID strings and UTC timestamps work on both engines. File bytes live outside the database; rows contain ownership, size, type, digest and opaque object keys.

Run all backend commands from `backend` so relative SQLite and file paths resolve consistently. The default is `sqlite:///./data/learnsphere.db`. Use an absolute SQLite path with forward slashes if running from another directory. PostgreSQL uses `postgresql+psycopg://USER:ENCODED_PASSWORD@HOST:5432/DB`.

```text
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Schema creation always uses Alembic. Do not call `Base.metadata.create_all()` on an application database. Add future revisions with `alembic revision --autogenerate -m "description"`, review the generated operations on both engines, test upgrade from a prior release, and commit the revision. SQLite schema alterations use Alembic batch rendering where needed. The first revision is an empty-database installation baseline; upgrades from an older product do not yet exist.

SQLite is appropriate for a small local demo, not a replacement for PostgreSQL concurrency. Business services serialize capacity/attempt decisions using portable row updates; unique constraints enforce duplicate enrollment, lesson progress, attendance and attempt invariants. SQLite ignores row-level `FOR UPDATE` and uses database-level write locking. Retry transient database contention at the client after a visible error; do not swallow it.

## Switching databases

For a **new empty PostgreSQL installation**:

1. Stop the API and worker; back up the existing SQLite database and files.
2. Provision the PostgreSQL database and restricted application login. Use the Docker private database or an external managed service.
3. Update `DATABASE_URL` in `.env` for local PostgreSQL, or use `.env.production` + production Compose. Production requires PostgreSQL.
4. Run `alembic upgrade head`, `alembic check`, and `app.cli seed-permissions`.
5. Securely bootstrap the administrator. Keep demo seed disabled in production.
6. Start the app and run the acceptance workflow.

Changing the URL **does not transfer records**. For an existing populated institution, use a reviewed migration project: export each table with UUIDs and UTC values, transform portable JSON/booleans, load parents before children into a migrated staging database, transfer file objects without changing keys, verify foreign keys/counts/checksums, reconcile learning outcomes and certificates, then cut over during a write freeze. There is deliberately no unchecked automatic cross-engine data copier. Keep the original backup until reconciliation and restore drills pass.

## SQLite backup and restore

From the project root:

```text
python scripts/sqlite-backup.py
```

This uses SQLite's online backup API on the **default** database, including a consistent view of WAL changes, and refuses to overwrite an existing destination. For a custom URL, use the same SQLite backup API with your configured absolute path. To obtain a coordinated database/files snapshot, stop application writes while backing up, copy `backend/storage`, and retain the encryption key in secure secret storage. The key is required to decrypt TOTP secrets and queued account emails.

To restore, stop all application processes, copy the current data/files to a separate recovery directory, replace the target database and storage with the matching backup, remove only stale target `-wal`/`-shm` files while no connection exists, run migrations and integrity checks, then start the app. Validate users, enrollment/progress counts, grades, certificate verification and at least one protected file download before reopening access. Never restore over a live database.

## PostgreSQL backup

The commands below use files inside the container then `docker compose cp`; this avoids binary corruption from older Windows PowerShell redirection. Keep backups encrypted and off-host, restrict access, and apply an approved retention policy. Substitute your database/login if different.

```text
docker compose --env-file .env.production exec db pg_dump -U lms_user -d learnsphere -Fc -f /tmp/learnsphere.backup
docker compose --env-file .env.production cp db:/tmp/learnsphere.backup ./backups/learnsphere.backup
docker compose --env-file .env.production exec db rm /tmp/learnsphere.backup
```

Create the host `backups` directory first. Use a unique date/version filename for each run. PostgreSQL dump is transactionally consistent; freeze file writes for a coordinated snapshot. Use the cross-platform maintenance utility to create a coordinated, retrievable database and file archive:

```text
python scripts/postgres-backup.py --output backups/release-backup
```

That utility stops application writers, creates and copies both database and file archives to a new host directory, then restarts services in a `finally` block. It never removes volumes or databases, refuses existing output directories, and requires Docker access. Review resulting exit status; a restarted service is not evidence a backup succeeded. Preserve `.env.production` secrets separately in your secret manager. Do not place secrets in the archive.

## PostgreSQL restore drill

Restore into a **new isolated database/environment**, not the live production database. These commands create a separate database on the current server for validation:

```text
docker compose --env-file .env.production cp ./backups/learnsphere.backup db:/tmp/restore.backup
docker compose --env-file .env.production exec db createdb -U lms_user learnsphere_restore_test
docker compose --env-file .env.production exec db pg_restore -U lms_user -d learnsphere_restore_test --no-owner --exit-on-error /tmp/restore.backup
```

For an actual recovery, obtain explicit operational approval, stop writers, provision a new empty database, restore it, restore the matching file archive into the persistent file volume with owner 10001:10001, point the app at it, and run migrations. Do not use `--clean` on a live database. Validate row counts against the backup manifest; inspect foreign-key validation; exercise authentication, progress, grading, certificate verification and file download. Record elapsed recovery time, recovered data timestamp and any loss. Keep the previous environment available for rollback.

This delivery documents and automates backup creation; an actual PostgreSQL backup/restore drill remains a deployment acceptance gate. It was not executable in the build environment without Docker/PostgreSQL.

## Database compatibility tests

The same pytest suite migrates and exercises whichever disposable `TEST_DATABASE_URL` is selected. PostgreSQL database names must contain `test`. CI provides a PostgreSQL 16 service and runs the suite separately from SQLite. A test also checks Alembic/model parity, both dialects' DDL compilation and SQLite foreign-key enforcement. DDL compilation is useful but is **not** evidence of a successful PostgreSQL runtime test; see the acceptance report for executed results.
