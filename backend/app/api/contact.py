from fastapi import APIRouter, Depends, HTTPException, status

from ..core.config import get_settings
from ..core.rate_limit import RateLimiter
from ..schemas.contact import ContactResponse, ContactStatusResponse, ContactSubmission
from ..services.contact import ContactService, contact_form_enabled

router = APIRouter(prefix="/api", tags=["contact"])
service = ContactService()
contact_limiter = RateLimiter(max_requests=5, window_seconds=600)


@router.get("/contact/status", response_model=ContactStatusResponse)
async def contact_status() -> ContactStatusResponse:
    """Lets the contact page show the form only when messages really reach someone."""
    return ContactStatusResponse(
        enabled=contact_form_enabled(), response_days=get_settings().contact_response_days
    )


# JSON only: a cross-site page can't send it without a CORS preflight, which
# this app never grants, so the form can't be used to spam the inbox via CSRF.
@router.post("/contact", response_model=ContactResponse, dependencies=[Depends(contact_limiter)])
def contact(payload: ContactSubmission) -> ContactResponse:
    settings = get_settings()
    clean = ContactSubmission(
        safe_name=payload.safe_name.strip(),
        safe_contact=payload.safe_contact.strip(),
        message=payload.message.strip(),
    )

    if not clean.message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required.")

    if len(clean.message) > settings.max_contact_message_length:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Message is too long.")

    receipt = service.submit(clean)
    return ContactResponse(ok=receipt.accepted, message=receipt.public_message)
