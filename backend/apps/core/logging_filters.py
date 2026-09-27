import logging
import re

_SECRET_PATTERNS = [
    re.compile(r"(ak_live_[A-Za-z0-9]+)"),
    re.compile(r"(sk-[A-Za-z0-9]{10,})"),
    re.compile(r'("?password"?\s*[:=]\s*")([^"]+)(")', re.IGNORECASE),
    re.compile(r'("?token"?\s*[:=]\s*")([^"]+)(")', re.IGNORECASE),
]


class RedactSecretsFilter(logging.Filter):
    """Best-effort redaction of obvious secret-shaped substrings from log
    records. This is a safety net, not a substitute for simply never
    logging secrets in the first place — application code must not pass
    raw API keys / passwords / provider tokens to logging calls."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(lambda m: "[REDACTED]", redacted)
        record.msg = redacted
        record.args = ()
        return True
