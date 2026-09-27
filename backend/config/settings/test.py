"""Settings for automated tests — SQLite in-memory, no external services
required (MySQL/Redis/OpenAI). Never used in production."""
from .base import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Never make real network calls to the AI provider from the test suite —
# embedding generation should just be skipped (falls back to keyword
# retrieval), and tests that need to exercise chat generation mock
# apps.ai.orchestrator.get_provider_for_agent directly.
OPENAI_API_KEY = ""
