import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..core import at_rest
from ..core.config import get_settings
from ..core.db import get_db
from ..core.rate_limit import RateLimiter
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.checkin import (
    AlertContext,
    AlertLogEntryResponse,
    ContactNoteRequest,
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

# Tokens are HMAC-SHA256 (infeasible to brute force outright), but these
# routes are unauthenticated by design - this is defense-in-depth against
# scripted probing, not the primary protection.
invite_limiter = RateLimiter(max_requests=30, window_seconds=300)


def _contact_response(db: Session, contact) -> TrustedContactResponse:
    return TrustedContactResponse(
        id=contact.id,
        nickname=contact.nickname,
        contact_email=contact.contact_email,
        status=contact.status,
        invited_at=contact.invited_at,
        responded_at=contact.responded_at,
        subscribed_devices=service.subscribed_device_count(db, contact.id),
        push_last_confirmed_at=service.push_last_confirmed(db, contact.id),
        push_lost_at=contact.push_lost_at,
    )


def _schedule_response(schedule) -> ScheduleResponse:
    return ScheduleResponse(
        active=schedule.active,
        interval_hours=schedule.interval_hours,
        grace_hours=schedule.grace_hours,
        last_checkin_at=schedule.last_checkin_at,
        next_deadline_at=schedule.next_deadline_at,
        overdue=CheckinService.is_overdue(schedule),
        alerts_sent=schedule.alerts_sent_count or 0,
        acknowledged_by=schedule.ack_count or 0,
        contact_note=CheckinService.read_contact_note(schedule),
        contact_note_available=at_rest.enabled(),
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleResponse:
    schedule, stand_down = service.update_schedule(db, user, payload)
    if stand_down:
        background_tasks.add_task(service.send_stand_down, user.id, stand_down)
    return _schedule_response(schedule)


@router.post("/schedule/checkin", response_model=ScheduleResponse)
async def checkin(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleResponse:
    schedule, needs_stand_down = service.checkin(db, user)
    if needs_stand_down:
        # Sent after the response, so "I'm OK" never waits on email or push.
        background_tasks.add_task(service.send_stand_down, user.id, "checked_in")
    return _schedule_response(schedule)


@router.put("/schedule/contact-note", response_model=ScheduleResponse)
async def set_contact_note(
    payload: ContactNoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduleResponse:
    """The survivor's message to contacts, shown only when an alert goes out (P3-I2)."""
    return _schedule_response(service.set_contact_note(db, user, payload.note))


# ---------- Survivor-authenticated: alert history ----------


@router.get("/alerts", response_model=list[AlertLogEntryResponse])
async def list_alerts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AlertLogEntryResponse]:
    return [AlertLogEntryResponse.model_validate(e, from_attributes=True) for e in service.list_alert_log(db, user)]


@router.delete("/alerts")
async def clear_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, bool]:
    service.clear_alert_log(db, user)
    return {"ok": True}


# ---------- Public: config ----------


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, str]:
    return {"public_key": get_settings().vapid_public_key}


# ---------- Public: invite (token-authenticated, no account) ----------


@router.get("/invite/{token}", response_model=InviteInfoResponse, dependencies=[Depends(invite_limiter)])
async def get_invite(token: str, db: Session = Depends(get_db)) -> InviteInfoResponse:
    contact, user = service.get_invite(db, token)
    alert = service.alert_context(db, contact)
    return InviteInfoResponse(
        survivor_username=user.username,
        status=contact.status,
        subscribed_devices=service.subscribed_device_count(db, contact.id),
        alert=AlertContext(**alert) if alert else None,
    )


@router.post("/invite/{token}/ack", dependencies=[Depends(invite_limiter)])
async def acknowledge_alert(token: str, db: Session = Depends(get_db)) -> dict[str, int]:
    """"I've got this": tells the survivor's other contacts someone is on it (P3-I3)."""
    return {"acknowledged_by": service.acknowledge_alert(db, token)}


@router.post("/invite/{token}/accept", dependencies=[Depends(invite_limiter)])
async def accept_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.accept_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/decline", dependencies=[Depends(invite_limiter)])
async def decline_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.decline_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/stop", dependencies=[Depends(invite_limiter)])
async def stop_invite(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    contact = service.stop_invite(db, token)
    return {"status": contact.status}


@router.post("/invite/{token}/subscribe", dependencies=[Depends(invite_limiter)])
async def subscribe(
    token: str, payload: PushSubscriptionRequest, db: Session = Depends(get_db)
) -> dict[str, bool]:
    service.add_subscription(db, token, payload)
    return {"ok": True}
