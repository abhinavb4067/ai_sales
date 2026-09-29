from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set — required to store integration credentials. "
            "Generate one with Fernet.generate_key()."
        )
    return Fernet(key)


class EncryptedTextField(models.TextField):
    """At-rest encryption for secrets that must live in the database
    (integration credentials — WhatsApp access tokens, etc.) — the raw
    value never touches the database, only the Fernet-encrypted
    ciphertext does. Built lazily off settings.FIELD_ENCRYPTION_KEY (a
    module-level Fernet() would freeze the key at import time, before
    Django settings/env are fully loaded in some contexts, and would make
    it impossible to override in tests)."""

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Data encrypted under a since-rotated key — surface as empty
            # rather than crashing every query that touches this row.
            return ""
