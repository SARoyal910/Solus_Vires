import logging
from dataclasses import dataclass

from ..schemas.contact import ContactSubmission

logger = logging.getLogger("solusvires.contact")


@dataclass(frozen=True)
class ContactReceipt:
    accepted: bool
    public_message: str


class ContactService:
    """Handles contact submissions without logging survivor-provided content."""

    def submit(self, submission: ContactSubmission) -> ContactReceipt:
        logger.info(
            "contact_submission_received",
            extra={
                "has_safe_name": bool(submission.safe_name.strip()),
                "has_safe_contact": bool(submission.safe_contact.strip()),
                "message_length": len(submission.message.strip()),
            },
        )
        return ContactReceipt(
            accepted=True,
            public_message="Message received. If it is safe, consider clearing your browser history.",
        )
