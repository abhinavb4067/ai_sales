"""SSRF-safe outbound HTTP fetch for knowledge ingestion (website URL
sources and external REST API sources — apps.knowledge.extractors).

Both source types let a business supply an arbitrary URL that the
platform's own servers then fetch. Without the checks here, that's a
textbook SSRF vector: a malicious/compromised tenant could point a
"knowledge source" at http://169.254.169.254/ (cloud metadata),
http://localhost:6379/ (internal Redis), or any other internal service
reachable from the Django/Celery host and have the platform fetch it on
their behalf, then read the result back through the AI's answers.

Every outbound ingestion fetch must go through safe_get() below instead
of calling requests.get() directly.
"""
import ipaddress
import socket
from urllib.parse import urlparse

import requests

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 15


class UnsafeURLError(ValueError):
    pass


def _is_private_or_reserved(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        # Cloud metadata endpoints (AWS/GCP/Azure/OCI all use 169.254.169.254)
        or ip_str == "169.254.169.254"
    )


def validate_url_is_safe(url: str) -> None:
    """Public entry point for callers that need the SSRF checks (scheme/
    port/DNS-resolves-to-public-address) without going through safe_get's
    GET-with-redirects flow — e.g. apps.webhooks, which does its own POST
    with a JSON body. Raises UnsafeURLError if the URL isn't safe to
    reach; does not follow redirects (the caller owns that if it needs
    to, re-validating each hop the same way safe_get does)."""
    _validate_url(url)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"URL scheme {parsed.scheme!r} is not allowed.")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no hostname.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f"Port {port} is not allowed.")

    try:
        resolved = socket.getaddrinfo(parsed.hostname, port)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host {parsed.hostname!r}.") from exc

    for family, _, _, _, sockaddr in resolved:
        ip_str = sockaddr[0]
        if _is_private_or_reserved(ip_str):
            raise UnsafeURLError(f"Host {parsed.hostname!r} resolves to a disallowed address ({ip_str}).")


def safe_get(url: str, *, headers: dict | None = None) -> requests.Response:
    """Validates scheme/port/DNS resolution before every hop, follows at
    most MAX_REDIRECTS redirects (re-validating each target), and caps the
    response body at MAX_RESPONSE_BYTES. Raises UnsafeURLError if the URL
    or any redirect target resolves to an internal/private/reserved
    address."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_url(current_url)
        response = requests.get(
            current_url,
            headers=headers or {"User-Agent": "Ectama-KnowledgeIngestion/1.0"},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect or response.is_permanent_redirect:
            next_url = response.headers.get("Location")
            response.close()
            if not next_url:
                raise UnsafeURLError("Redirect with no Location header.")
            current_url = next_url
            continue

        content = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        if len(content) > MAX_RESPONSE_BYTES:
            response.close()
            raise UnsafeURLError(f"Response exceeds the {MAX_RESPONSE_BYTES} byte limit.")
        response._content = content
        response._content_consumed = True
        return response

    raise UnsafeURLError("Too many redirects.")
