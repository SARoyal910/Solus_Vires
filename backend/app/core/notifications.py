import json
import logging

import httpx
from pywebpush import WebPushException, webpush

from ..models.checkin import PushSubscription
from .config import get_settings

logger = logging.getLogger("solusvires.notifications")


def push_configured() -> bool:
    settings = get_settings()
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def email_configured() -> bool:
    return bool(get_settings().brevo_api_key)


def send_push(subscription: PushSubscription, title: str, body: str, url: str) -> bool:
    """Sends a Web Push notification. Returns True on success.

    Raises PushSubscriptionExpired if the endpoint is gone (404/410) so the
    caller can prune it; any other failure is logged and swallowed as
    best-effort, matching this codebase's "never let notification plumbing
    break the request" pattern.
    """
    settings = get_settings()
    if not push_configured():
        logger.info("push_skipped_not_configured")
        return False

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    payload = json.dumps({"title": title, "body": body, "url": url})

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (404, 410):
            raise PushSubscriptionExpired from exc
        logger.warning("push_send_failed", extra={"status_code": status_code})
        return False


class PushSubscriptionExpired(Exception):
    """Raised when a push endpoint has been unsubscribed/expired (404/410)."""


def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    """Sends a transactional email via Brevo. Returns True on success.

    In development, without BREVO_API_KEY set, this logs and no-ops rather
    than failing the request - matches CONTACT_SINK's console-fallback
    behavior elsewhere in this codebase.
    """
    settings = get_settings()
    if not email_configured():
        logger.info("email_skipped_not_configured", extra={"subject": subject})
        return False

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
                "to": [{"email": to_email, "name": to_name or to_email}],
                "subject": subject,
                "htmlContent": html_content,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("email_send_failed", extra={"error": str(exc)})
        return False


def ping_healthcheck() -> bool:
    """Tells the heartbeat monitor an alert pass completed. Never raises.

    Off when HEALTHCHECK_PING_URL is empty. A missed ping is what pages the
    operator, so failing here only means the monitor may raise a false alarm;
    it must never stop alerts going out.
    """
    url = get_settings().healthcheck_ping_url
    if not url:
        return False
    try:
        httpx.get(url, timeout=10.0).raise_for_status()
        return True
    except Exception as exc:
        logger.warning("healthcheck_ping_failed", extra={"error": type(exc).__name__})
        return False
