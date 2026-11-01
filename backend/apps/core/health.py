"""Health check endpoint for load balancers/uptime monitoring (master
spec section 19: "health checks"). Deliberately public/unauthenticated
(it's an infra signal, not tenant data) and cheap — a connectivity probe
per dependency, never a business query.
"""
from django.db import connections
from django.http import JsonResponse


def healthcheck(request):
    checks = {}
    healthy = True

    try:
        connections["default"].cursor()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        from django.core.cache import cache

        cache.set("healthcheck_probe", "1", timeout=5)
        checks["cache"] = "ok" if cache.get("healthcheck_probe") == "1" else "error: cache read/write mismatch"
    except Exception as exc:  # noqa: BLE001
        checks["cache"] = f"error: {exc}"
        # Redis being down degrades rate limiting/caching but shouldn't
        # flip the whole service to unhealthy on its own in dev, where
        # cache may be LocMem — only treat it as fatal if configured.
        from django.conf import settings

        if settings.CACHES.get("default", {}).get("BACKEND", "").endswith("RedisCache"):
            healthy = False

    return JsonResponse({"status": "ok" if healthy else "unhealthy", "checks": checks}, status=200 if healthy else 503)
