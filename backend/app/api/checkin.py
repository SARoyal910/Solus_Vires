import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.db import get_db
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.checkin import (
    InviteInfoResponse,
    PushSubscriptionRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
    TrustedContactCreate,
    TrustedContactResponse,
)
from ..services.checkin import CheckinService

router = APIRouter(prefix="/api/checkin", tags=["checkin"])
service = CheckinService()


def _contact_response(db: Session, contact) -> TrustedContactResponse:
    return TrustedContactResponse(
        id=contact.id,
        nickname=contact.nickname,
        contact_email=contact.contact_email,
        status=contact.status,
        invited_at=contact.invited_at,
        responded_at=contact.responded_at,
        subscribed_devices=service.subscribed_device_count(db, contact.id),
    )


def _schedule_response(schedule) -> ScheduleResponse:
    return ScheduleResponse(
        active=schedule.active,
        interval_hours=schedule.interval_hours,
        grace_hours=schedule.grace_hours,
        last_checkin_at=schedule.last_checkin_at,
        next_deadline_at=schedule.next_deadline_at,
        overdue=CheckinService.is_overdue(schedule),
    )


# ---------- Survivor-authenticated: trusted contacts ----------


@router.get("/contacts", response_model=list[TrustedContactResponse])
async def list_contacts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[TrustedContactResponse]:
    return [_contact_response(db, c) for c in service.list_contacts(db, user)]


@router.post("/contacts", response_model=TrustedContactResponse)
async def add_contact(
    payload: TrustedContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrustedContactResponse:
    contact = service.add_contact(db, user, payload)
    return _contact_response(db, contact)


@router.delete("/contacts/{contact_id}")
async def remove_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    service.remove_contact(db, user, contact_id)
    return {"ok": True}


@router.post("/contacts/{contact_id}/resend", response_model=TrustedContactResponse)
async def resend_invite(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrustedContactResponse:
    contact = service.resend_invite(db, user, contact_id)
    return _contact_response(db, contact)


# ---------- Survivor-authenticated: schedule ----------


@router.get("/schedule", response_model=ScheduleResponse)
async def get_schedule(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ScheduleResponse:
    return _schedule_response(service.get_schedule(db, user))


@router.put("/schedule", response_model=ScheduleResponse)
async def update_schedule(
    payload: ScheduleUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleResponse:
    return _schedule_response(service.update_schedule(db, user, payload))


@router.post("/schedule/checkin", response_model=ScheduleResponse)
async def checkin(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ScheduleResponse:
    return _schedule_response(service.checkin(db, user))


# ---------- Public: config ----------


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, str]:
    return {"public_key": get_settings().vapid_public_key}


# ---------- Public: invite (token-authenticated, no account) ----------


@router.get("/invite/{token}", response_model=InviteInfoResponse)
async def get_invite(token: str, db: Session = Depends(get_db)) -> InviteInfoResponse:
    contact, user = service.get_invite(db, token)
    return InviteInfoResponse(
        survivor_username=user.username,
        status=contact.status,
        subscribed_devices=service.subscribed_device_count(db, contact.id),
    )


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.accept_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/decline")
async def decline_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.decline_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/stop")
async def stop_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.stop_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/subscribe")
async def subscribe(
    token: str, payload: PushSubscriptionRequest, db: Session = Depends(get_db)
) -> dict[str, bool]:
    service.add_subscription(db, token, payload)
    return {"ok": True}
