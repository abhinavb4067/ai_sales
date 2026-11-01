# AI Sales & Support Agent — Backend (Phase 1)

Django + DRF backend for the multi-tenant AI sales/support agent SaaS.

## Setup

```bash
cd backend
py -m venv venv                    # or: python -m venv venv
./venv/Scripts/activate             # Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env: set POSTGRES_PASSWORD to match what you used in scripts/setup_postgres.sql,
# and OPENAI_API_KEY if you want the playground to produce real AI responses.
```

### Database

Provision Postgres once (requires a Postgres superuser login; the
`vector` extension needs pgvector installed — see docker-compose.yml's
`pgvector/pgvector` image if you're not installing it manually):

```bash
psql -U postgres -f scripts/setup_postgres.sql
```

Then:

```bash
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
```

### Run

```bash
python manage.py runserver
```

Document processing (PDF/DOCX/CSV/URL uploads) runs asynchronously via
Celery — start a worker alongside the server (requires Redis running):

```bash
celery -A config worker -l info --pool=solo   # --pool=solo needed on Windows
```

Without a worker running, file/URL/API/database knowledge uploads stay
in `pending` status forever — manual/FAQ text entries don't need it
(they're ingested synchronously).

Scheduled re-sync of URL/API knowledge sources and overdue-follow-up
detection run via Celery Beat (see `config.settings.base
CELERY_BEAT_SCHEDULE`) — start it alongside the worker if you want
those to actually fire in dev:

```bash
celery -A config beat -l info
```

API docs (Swagger UI): http://localhost:8000/api/docs/
Django admin: http://localhost:8000/admin/

### Tests

Tests run against an in-memory SQLite database — no Postgres/Redis/OpenAI
required:

```bash
python manage.py test apps --settings=config.settings.test
```

The mandatory tenant-isolation suite lives in
`apps/tenants/tests/test_isolation.py`.

## Architecture notes

- `apps/core` — StorageProvider abstraction, tenant-scoping mixins/permissions,
  shared exception format, logging redaction.
- `apps/ai` — AIProvider abstraction (`providers/`), the prompt builder that
  enforces the system/agent/knowledge/customer instruction hierarchy, the
  tool service that validates+executes AI-proposed actions, and the single
  `orchestrator.receive_message()` pipeline every channel (playground today;
  widget/API/WhatsApp later) calls.
- `apps/knowledge` — `KnowledgeRetriever` abstraction; `PgVectorRetriever`
  (native Postgres pgvector) is the default, with `KeywordRetriever` as a
  DB-agnostic fallback and an external Qdrant store as an opt-in
  alternative — see `apps/knowledge/retrieval.py::get_retriever()`.
  Source types: manual/FAQ text, file upload (PDF/DOCX/TXT/CSV), website
  URL (multi-page crawl respecting robots.txt — `apps/knowledge/crawler.py`),
  external REST API, and a restricted read-only external database table
  (`apps/knowledge/db_source.py` — single pre-validated table, no
  AI-generated SQL, dedicated read-only credentials expected).
- Every tenant-owned model inherits `apps.core.models.TenantOwnedModel` and
  every viewset uses `apps.core.permissions.TenantScopedQuerySetMixin` +
  `IsBusinessMember` — `request.business` is resolved server-side from the
  authenticated user's membership, never from client input.
