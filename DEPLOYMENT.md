# Ectama — Deployment & Operations

This covers running Ectama locally with Docker Compose, deploying it to
production, backup/restore, and rollback. It documents what actually
exists in this repository today — nothing here describes an
unimplemented feature as if it were live infrastructure.

## Local development (Docker Compose)

```bash
cp backend/.env.example backend/.env
# edit backend/.env — at minimum set POSTGRES_PASSWORD to match what you
# pass to docker compose (see below), and FIELD_ENCRYPTION_KEY to a real
# Fernet key:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up --build
```

This starts Postgres (with the pgvector extension, via the
`pgvector/pgvector` image), Redis, the Django backend (`runserver`,
live-reloads from your checkout), a Celery worker, and the frontend
(built once, served by nginx — rebuild the `frontend` service after
frontend changes). First run also applies migrations automatically.

- Backend: http://localhost:8000 (API docs at `/api/docs/`)
- Frontend: http://localhost:5173
- Health check: http://localhost:8000/health/

This compose file is a **local dev** topology (published Postgres/Redis
ports, `runserver`, no TLS) — see Production below for what changes.

## Production topology

Master spec section 25 requirements and where they're satisfied:

| Requirement | How |
|---|---|
| Separate web and worker processes | `backend/Dockerfile` CMD runs `daphne` (web); run a second container/service from the same image with `celery -A config worker -l info` instead |
| HTTPS / reverse proxy | Terminate TLS at your own Nginx/load balancer in front of the `backend` and `frontend` containers — not included here, since the cert/domain setup is environment-specific |
| Secure PostgreSQL | Use a managed Postgres instance (e.g. RDS/Cloud SQL/Supabase) with the `vector` extension enabled and TLS-enforced connections, not a self-hosted container, in production — `scripts/setup_postgres.sql` is the dev provisioning equivalent |
| Redis protected from public access | Use a managed Redis instance or bind it to a private network only — never expose port 6379 publicly (the Compose file's published port is dev-only) |
| Private object storage | Set `STORAGE_BACKEND`/`STORAGE_BUCKET`/etc. in `.env` to an S3-compatible provider (Cloudflare R2, S3) — see `apps/core/storage.py` |
| Environment/secrets management | Inject `backend/.env` values via your platform's secrets manager, never commit them. `config.settings.prod` refuses to start if `DJANGO_SECRET_KEY`/`FIELD_ENCRYPTION_KEY` are still the insecure dev defaults, so a misconfigured deploy fails loudly instead of running with weak secrets |
| Database backups + tested restore | `backend/scripts/backup_postgres.sh` / `restore_postgres.sh` — see below |
| Structured logs | Already configured, `config/settings/base.py LOGGING` (secret-redacting filter) |
| Monitoring/alerting | Optional Sentry wiring — set `SENTRY_DSN` (see `.env.example`); nothing is sent unless configured |
| Health checks | `GET /health/` — checks DB + cache connectivity, returns 503 on failure |
| Deployment and rollback | See below |

Build and push the two images from CI:

```bash
docker build -t your-registry/ectama-backend:GIT_SHA ./backend
docker build -t your-registry/ectama-frontend:GIT_SHA ./frontend \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
docker push your-registry/ectama-backend:GIT_SHA
docker push your-registry/ectama-frontend:GIT_SHA
```

Deploy by pointing your orchestrator (ECS/Kubernetes/Docker Swarm/a
single VM running `docker compose` with a production override file) at
the new tag for both the web and worker services, run
`python manage.py migrate` as a one-off task before traffic shifts to
the new web containers, then roll the web/worker services.

### Rollback

1. Re-point the web/worker services at the previous image tag (every
   image is tagged by git SHA, so this is always available).
2. If the failed deploy included a migration, check whether it's
   backward-compatible before rolling back code. If not, restore from
   the pre-deploy backup (see below) rather than rolling back code
   against a newer schema.
3. Confirm `GET /health/` returns 200 after rollback before considering
   the incident resolved.

## Backups and restore

```bash
# Backup (run on a schedule — cron/systemd timer/CI scheduled job):
cd backend
PGPASSWORD=*** ./scripts/backup_postgres.sh ./backups

# Restore — DESTRUCTIVE, overwrites the target database:
PGPASSWORD=*** ./scripts/restore_postgres.sh ./backups/ai_sales_20260101T000000Z.sql.gz
```

`backup_postgres.sh` keeps the last 14 daily dumps in its output
directory and deletes older ones — point `OUTPUT_DIR` at a path synced
to object storage (e.g. an `rclone`/`aws s3 sync` cron job) for
durability beyond the host it runs on.

**Test the restore path periodically** against a throwaway database —
an untested backup is not a backup. A reasonable quarterly check:
restore the latest dump into a scratch Postgres instance (with the
`vector` extension available) and run `python manage.py check` + a
smoke test (log in, list agents) against it.

## Vector search (pgvector vs. external store)

Knowledge retrieval (`apps/knowledge/retrieval.py::get_retriever()`)
defaults to native Postgres pgvector (`PgVectorRetriever`) — no extra
service to run or back up; the vectors live in the same database and
the same backup above covers them. An external store (Qdrant) is
available as an opt-in alternative via `QDRANT_URL` for deployments
that specifically want a standalone vector database instead — if you
set it, that store needs its own backup/restore plan, not covered here.

## Disaster recovery notes

- The two things that must be backed up: the Postgres database (covered
  above, which includes the pgvector embeddings — they're an ordinary
  column, not a separate system) and anything in object storage
  (`STORAGE_BUCKET` — knowledge document uploads). Object storage
  durability is the provider's responsibility (S3/R2 already
  replicate); Postgres is this repo's responsibility via the scripts
  above.
- Redis holds only ephemeral state (Celery queue, cache, channel layer
  for WebSocket fan-out) — nothing there needs backing up; losing it
  loses in-flight background jobs and open WebSocket sessions, not data.
- `FIELD_ENCRYPTION_KEY` encrypts integration credentials at rest
  (`apps/core/fields.py`). Losing this key makes existing encrypted
  credentials (e.g. WhatsApp access tokens) unrecoverable — back it up
  separately from the database dump, in your secrets manager, not in
  the same backup file.
