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
    """True when at least one email provider has credentials."""
    settings = get_settings()
    return bool(settings.brevo_api_key or settings.postmark_server_token)


def email_fallback_configured() -> bool:
    return bool(get_settings().postmark_server_token)


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


class EmailProviderError(Exception):
    """One provider failed to accept a message. Carries no address or content."""

    def __init__(self, provider: str, status_code: int | None, reason: str) -> None:
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.status_code = status_code
        self.reason = reason


def _post_json(url: str, headers: dict[str, str], body: dict, provider: str) -> None:
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=10.0)
    except httpx.HTTPError as exc:
        raise EmailProviderError(provider, None, type(exc).__name__) from exc
    if response.status_code >= 400:
        # The body may echo the recipient; keep only the status.
        raise EmailProviderError(provider, response.status_code, f"HTTP {response.status_code}")


def _send_via_brevo(to_email: str, to_name: str, subject: str, html_content: str) -> None:
    settings = get_settings()
    _post_json(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": settings.brevo_api_key, "Content-Type": "application/json"},
        body={
            "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
            "to": [{"email": to_email, "name": to_name or to_email}],
            "subject": subject,
            "htmlContent": html_content,
        },
        provider="brevo",
    )


def _send_via_postmark(to_email: str, to_name: str, subject: str, html_content: str) -> None:
    settings = get_settings()
    sender = settings.postmark_sender_email or settings.brevo_sender_email
    _post_json(
        "https://api.postmarkapp.com/email",
        headers={
            "X-Postmark-Server-Token": settings.postmark_server_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        body={
            "From": f"{settings.brevo_sender_name} <{sender}>",
            "To": f"{to_name} <{to_email}>" if to_name else to_email,
            "Subject": subject,
            "HtmlBody": html_content,
            "MessageStream": settings.postmark_message_stream,
        },
        provider="postmark",
    )


# In the order they are tried. Brevo is primary because it is what production
# has used so far; Postmark takes over when Brevo errors, is rate limited, or
# is out of quota (SCALE.md Stage 1 item 2).
_PROVIDERS = (
    ("brevo", lambda: bool(get_settings().brevo_api_key), _send_via_brevo),
    ("postmark", lambda: bool(get_settings().postmark_server_token), _send_via_postmark),
)


def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> str:
    """Sends a transactional email, failing over between providers.

    Returns the name of the provider that accepted the message ("brevo" or
    "postmark"), or "" when none did; callers treat the string as a boolean.
    Every configured provider is tried in order, so a Brevo outage or a
    quota wall never loses an alert while Postmark is configured.

    In development, with no provider configured, this logs and no-ops rather
    than failing the request - matches CONTACT_SINK's console-fallback
    behavior elsewhere in this codebase.
    """
    if not email_configured():
        logger.info("email_skipped_not_configured", extra={"subject": subject})
        return ""

    failures: list[EmailProviderError] = []
    for name, configured, send in _PROVIDERS:
        if not configured():
            continue
        try:
            send(to_email, to_name, subject, html_content)
        except EmailProviderError as exc:
            failures.append(exc)
            logger.warning(
                "email_provider_failed",
                extra={"provider": name, "status_code": exc.status_code, "reason": exc.reason},
            )
            continue
        if failures:
            # Worth a line of its own: a run of these means the primary's
            # quota is gone (SCALE.md §5.1) and the operator should look.
            logger.warning(
                "email_failed_over",
                extra={"provider": name, "after": [f.provider for f in failures]},
            )
        return name
    logger.error("email_send_failed_all_providers", extra={"providers": [f.provider for f in failures]})
    return ""


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
