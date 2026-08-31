from fastapi import APIRouter, Depends, Form, HTTPException, status

from ..core.config import get_settings
from ..core.rate_limit import RateLimiter
from ..schemas.contact import ContactResponse, ContactSubmission
from ..services.contact import ContactService

router = APIRouter(prefix="/api", tags=["contact"])
service = ContactService()
contact_limiter = RateLimiter(max_requests=5, window_seconds=600)


@router.post("/contact", response_model=ContactResponse, dependencies=[Depends(contact_limiter)])
async def contact(
    safe_name: str = Form(default=""),
    safe_contact: str = Form(default=""),
    message: str = Form(default=""),
) -> ContactResponse:
    settings = get_settings()
    clean_message = message.strip()

    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required.",
        )

    if len(clean_message) > settings.max_contact_message_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Message is too long.",
        )

    receipt = service.submit(
        ContactSubmission(
            safe_name=safe_name.strip(),
            safe_contact=safe_contact.strip(),
            message=clean_message,
        )
    )
    return ContactResponse(ok=receipt.accepted, message=receipt.public_message)
