import hashlib
import hmac
import json
import logging

import requests
from celery import shared_task

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 5
# Exponential backoff: 30s, 2min, 8min, 32min, 128min between attempts —
# gives a flaky receiving endpoint real time to recover without hammering it.
RETRY_BACKOFF_SECONDS = 30


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@shared_task(bind=True, max_retries=MAX_ATTEMPTS - 1)
def deliver_webhook_task(self, delivery_id):
    from apps.knowledge.net_safety import UnsafeURLError, validate_url_is_safe
    from apps.webhooks.models import OutboundWebhookDelivery

    delivery = OutboundWebhookDelivery.objects.select_related("subscription").get(id=delivery_id)
    subscription = delivery.subscription
    delivery.attempt_count += 1

    body = json.dumps(
        {"event": delivery.event_type, "data": delivery.payload, "delivery_id": str(delivery.id)}
    ).encode()

    try:
        validate_url_is_safe(subscription.url)
        signature = sign_payload(subscription.secret, body)
        response = requests.post(
            subscription.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Ectama-Signature": f"sha256={signature}",
                "X-Ectama-Event": delivery.event_type,
                "User-Agent": "Ectama-Webhooks/1.0",
            },
            timeout=TIMEOUT_SECONDS,
        )
        delivery.response_status_code = response.status_code
        if 200 <= response.status_code < 300:
            from django.utils import timezone

            delivery.status = OutboundWebhookDelivery.Status.SUCCEEDED
            delivery.delivered_at = timezone.now()
            delivery.last_error = ""
            delivery.save(update_fields=["attempt_count", "status", "response_status_code", "delivered_at", "last_error", "updated_at"])
            return
        raise RuntimeError(f"Endpoint returned {response.status_code}.")
    except UnsafeURLError as exc:
        # Never retry an unsafe URL — retrying won't make it safe, and
        # it means the subscription itself is misconfigured/malicious.
        delivery.status = OutboundWebhookDelivery.Status.FAILED
        delivery.last_error = str(exc)
        delivery.save(update_fields=["attempt_count", "status", "last_error", "updated_at"])
        logger.warning("Webhook delivery %s rejected: unsafe URL (%s).", delivery_id, exc)
        return
    except Exception as exc:  # noqa: BLE001 — network errors, timeouts, non-2xx
        delivery.last_error = str(exc)
        if self.request.retries >= MAX_ATTEMPTS - 1:
            delivery.status = OutboundWebhookDelivery.Status.FAILED
            delivery.save(update_fields=["attempt_count", "status", "last_error", "updated_at"])
            logger.warning("Webhook delivery %s permanently failed after %d attempts: %s", delivery_id, delivery.attempt_count, exc)
            return
        delivery.save(update_fields=["attempt_count", "last_error", "updated_at"])
        raise self.retry(countdown=RETRY_BACKOFF_SECONDS * (4**self.request.retries))
