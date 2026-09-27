# AI Sales & Support Agent — Backend (Phase 1)

Django + DRF backend for the multi-tenant AI sales/support agent SaaS.

## Setup

```bash
cd backend
py -m venv venv                    # or: python -m venv venv
./venv/Scripts/activate             # Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env: set MYSQL_PASSWORD to match what you used in scripts/setup_mysql.sql,
# and OPENAI_API_KEY if you want the playground to produce real AI responses.
```

### Database

Provision MySQL once (requires a MySQL admin/root login):

```bash
mysql -u root -p < scripts/setup_mysql.sql
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

Without a worker running, file/URL knowledge uploads stay in `pending`
status forever — manual/FAQ text entries don't need it (they're ingested
synchronously).

API docs (Swagger UI): http://localhost:8000/api/docs/
Django admin: http://localhost:8000/admin/

### Tests

Tests run against an in-memory SQLite database — no MySQL/Redis/OpenAI
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
- `apps/knowledge` — `KnowledgeRetriever` abstraction; `MySQLKeywordRetriever`
  is the Phase 1 implementation, swappable for a vector store later via
  `apps/knowledge/retrieval.py::get_retriever()`.
- Every tenant-owned model inherits `apps.core.models.TenantOwnedModel` and
  every viewset uses `apps.core.permissions.TenantScopedQuerySetMixin` +
  `IsBusinessMember` — `request.business` is resolved server-side from the
  authenticated user's membership, never from client input.
