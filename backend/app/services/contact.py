"""Contact form: each message is emailed to the operator's inbox and nothing is kept.

Decision D3 (PHASE2_PLAN): wire the form to a monitored inbox through the
existing Brevo client, with a stated response window and a plain
"not for emergencies" line. No message is stored in the database or written
to the logs; only whether it was sent.
"""

import html
import logging
from dataclasses import dataclass

from fastapi import HTTPException, status

from ..core.config import get_settings
from ..core.notifications import email_configured, send_email
from ..schemas.contact import ContactSubmission

logger = logging.getLogger("solusvires.contact")

NOT_CONNECTED = (
    "This form isn't connected to an inbox yet, so your message was not sent. "
    "If you need support, the National Domestic Violence Hotline is available 24/7: "
    "call 1-800-799-7233 or text START to 88788. In danger now? Call 911."
)
SEND_FAILED = (
    "Your message could not be sent just now and nothing was saved. Please try again later. "
    "If you need support now, call 1-800-799-7233 or text START to 88788. In danger now? Call 911."
)


def contact_form_enabled() -> bool:
    return bool(get_settings().contact_inbox_email) and email_configured()


def response_window(days: int) -> str:
    return "within a day" if days == 1 else f"within {days} days"


def sent_message(days: int) -> str:
    return (
        f"Your message was sent. We aim to reply {response_window(days)} if you left a way to reach you. "
        "This isn't monitored around the clock and can't help in an emergency: if you need support now, "
        "call 1-800-799-7233 or text START to 88788. In danger now? Call 911."
    )


def _email_html(submission: ContactSubmission) -> str:
    name = html.escape(submission.safe_name) or "<em>not given</em>"
    reach = html.escape(submission.safe_contact) or "<em>not given</em>"
    body = html.escape(submission.message).replace("\n", "<br>")
    return f"""
    <p><strong>New message from the Solus Vires contact form.</strong></p>
    <p>Name they gave: {name}<br>
    Safe way to reach them: {reach}</p>
    <p>{body}</p>
    <hr>
    <p>This message is not stored on the site. Before replying, use only the contact method they
    said is safe; someone else may read their email or texts.</p>
    """.strip()


@dataclass(frozen=True)
class ContactReceipt:
    accepted: bool
    public_message: str


class ContactService:
    """Sends contact submissions to the operator. Never logs or stores what was written."""

    def submit(self, submission: ContactSubmission) -> ContactReceipt:
        settings = get_settings()
        if not contact_form_enabled():
            logger.info("contact_submission_refused_not_configured")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_CONNECTED)

        sent = send_email(
            to_email=settings.contact_inbox_email,
            to_name="Solus Vires contact form",
            subject="Solus Vires: new contact form message",
            html_content=_email_html(submission),
        )
        if not sent:
            logger.warning("contact_submission_send_failed")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SEND_FAILED)

        logger.info("contact_submission_sent")
        return ContactReceipt(accepted=True, public_message=sent_message(settings.contact_response_days))
