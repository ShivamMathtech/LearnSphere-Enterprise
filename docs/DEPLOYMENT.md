# Deployment runbook

## Release prerequisites

Use a supported Linux container host with Docker Engine and Compose v2.20+ (or Docker Desktop for evaluation), an HTTPS reverse proxy at the edge, DNS, unique secrets, a backup destination and a configured SMTP provider if email verification/invitations are enabled. The app containers run as non-root; PostgreSQL is private to the Compose network. Production rejects SQLite, demo mode, short/example JWT keys, invalid encryption keys and non-HTTPS origins.

Create `.env.production` from `.env.production.example`. Generate keys with `python -m app.cli generate-secrets` in the backend virtual environment. This explicitly prints **new** secrets for transfer to your deployment secret manager; do not commit or log them. Generate a separate URL-safe random `POSTGRES_PASSWORD`, avoiding `@`, `:`, `/`, `#`, `%` and `?` in this Compose URL format. Otherwise URL-encode database credentials in a custom `DATABASE_URL` deployment configuration.

Set `FRONTEND_URL` and `CORS_ORIGINS` to the exact HTTPS origin, without a trailing slash. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`; STARTTLS is enabled by default. Keep `EMAIL_VERIFICATION_REQUIRED=true` and `REQUIRE_PRIVILEGED_MFA=true`. Secrets should be injected by the deployment system; the supplied env file is a simple host-level option and needs restricted filesystem permissions.

## Build, migrate and start

From the repository root (commands work in Command Prompt, PowerShell or a POSIX terminal):

```text
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production build --pull
docker compose --env-file .env.production up -d db
docker compose --env-file .env.production run --rm migrate
docker compose --env-file .env.production up -d --wait
docker compose --env-file .env.production ps
docker compose --env-file .env.production exec backend python -m app.cli bootstrap --email owner@your-domain.example --name "Platform Owner"
```

`up` also runs the one-shot migration service, safely applying any unapplied revisions before the API/worker starts. Run only one deployment/migration job per database. No seed accounts are created in production. An already applied migration is a no-op.

The frontend is bound only to host `127.0.0.1:8080`. Configure your host edge proxy to forward your HTTPS virtual host to this address. The Nginx frontend routes `/api/*` to the API service and serves the SPA. Terminate TLS at the edge; secure cookies will not work over plain HTTP in production. Configure HTTPS redirects and TLS certificates at the edge. For a containerized edge proxy, use a shared private network and service name instead of host loopback, and remove the unnecessary host port mapping.

Do not expose the API or database directly. Do not enable debug mode. The API ignores untrusted forwarded headers by default. Consequently IP rate limits group requests behind the proxy; account-specific lockouts still apply. For larger deployments, explicitly configure a trusted proxy address in Uvicorn and a reviewed ingress rate limiter; never trust arbitrary `X-Forwarded-For` from the internet. Adjust the 22 MiB Nginx body limit if changing `UPLOAD_MAX_MB`.

## Health and logs

```text
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs --tail 100 backend worker migrate
docker compose --env-file .env.production exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').read().decode())"
docker compose --env-file .env.production exec worker python -m app.tasks.scheduler --health
```

The API checks a real database query and the Alembic revision. The worker heartbeat becomes unhealthy after three minutes without a completed cycle. The frontend has `/healthz`. Application logs contain request IDs, route templates, status and duration, without bodies, credentials or cookies. Send logs to your central log system with appropriate retention. Nginx access logs should be disabled/redacted at an edge that may receive sensitive URL paths; reset tokens are carried in URL fragments, which are not sent to servers.

## Update

1. Take and validate database and file backups using `DATABASE.md`.
2. Review migration changes and dependency scans. Test the release against a restored staging database.
3. Stop worker/backend during a coordinated maintenance window for schema changes that are not backwards compatible.
4. Build the new images, apply `migrate`, start with `up -d --wait`, and verify health and the browser smoke workflow.
5. Record the application version, image digests, migration revision and backup identifier in your release record.

```text
docker compose --env-file .env.production stop worker backend
docker compose --env-file .env.production build --pull
docker compose --env-file .env.production run --rm migrate
docker compose --env-file .env.production up -d --wait
```

Roll back code only if its schema compatibility has been checked. Otherwise restore a coordinated database/files backup in a maintenance window. Alembic downgrade is a development tool, not a substitute for a reviewed production rollback.

## Stop safely

```text
docker compose --env-file .env.production down
```

This preserves named volumes. **Do not add `--volumes` / `-v` unless you intentionally want to delete the database and uploaded files.** A normal restart never resets data.

## Capacity and configuration boundaries

This release uses a modular monolith and one scheduler. The production API has a 1 GiB/2 CPU limit, worker 512 MiB, frontend 256 MiB, database 1 GiB. These are initial settings, not measured capacity guarantees. Benchmark realistic courses and concurrent quiz starts before allocating production capacity. Local storage must be persistent and shared by any replicated APIs; implement the provided storage interface for managed object storage before horizontally distributing file-serving instances.
