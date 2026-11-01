from .base import *  # noqa

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Fail fast rather than silently run production with a known, publicly
# committed placeholder secret — SECRET_KEY underpins session/password-
# reset-token/CSRF signing, so a weak default there is a real
# authentication bypass risk, not just a style nit.
if SECRET_KEY == "insecure-dev-key-change-me":  # noqa: F405
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a real secret in production — "
        "refusing to start with the insecure default from config.settings.base."
    )
if not FIELD_ENCRYPTION_KEY or FIELD_ENCRYPTION_KEY == "change-me-generate-with-fernet":  # noqa: F405
    raise RuntimeError(
        "FIELD_ENCRYPTION_KEY must be set to a real Fernet key in production — "
        "integration credentials (e.g. WhatsApp access tokens) would otherwise "
        "be unencryptable/unrecoverable."
    )
