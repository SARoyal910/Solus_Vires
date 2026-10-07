import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class TrustedContactCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=80)
    contact_email: EmailStr


class TrustedContactResponse(BaseModel):
    id: uuid.UUID
    nickname: str
    contact_email: str
    status: str
    invited_at: datetime
    responded_at: datetime | None
    subscribed_devices: int
    # When the push service last accepted an alert for one of their devices (not proof it was seen).
    push_last_confirmed_at: datetime | None = None
    # Set when their push device stopped working and was removed; they still get email.
    push_lost_at: datetime | None = None


class ScheduleUpdateRequest(BaseModel):
    active: bool
    interval_hours: int = Field(ge=1, le=336)
    grace_hours: int = Field(ge=0, le=168)


class ScheduleResponse(BaseModel):
    active: bool
    interval_hours: int
    grace_hours: int
    last_checkin_at: datetime | None
    next_deadline_at: datetime | None
    overdue: bool
    # Alerts sent since the last check-in (0 when none are going out).
    alerts_sent: int = 0
    # Contacts who said "I've got this" during the current alerts (P3-I3).
    acknowledged_by: int = 0
    # The survivor's note to contacts (P3-I2); None when the feature is off.
    contact_note: str | None = None
    contact_note_available: bool = False


class ContactNoteRequest(BaseModel):
    # Plain text, a few sentences. Empty clears it.
    note: str = Field(max_length=500)


class AlertContext(BaseModel):
    """What a trusted contact may see while alerts are going out (decision D12)."""

    alert_number: int
    hours_overdue: int
    first_alert_at: datetime | None
    note: str | None
    acknowledged_by: int
    repeat_hours: int


class InviteInfoResponse(BaseModel):
    survivor_username: str
    status: str
    subscribed_devices: int
    # Present only while the survivor is overdue and alerts have gone out, and
    # only for an accepted contact (P3-I1).
    alert: AlertContext | None = None


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeys


class AlertLogEntryResponse(BaseModel):
    kind: str
    alert_number: int | None
    contacts_notified: int
    emails_sent: int
    emails_via_fallback: int = 0
    pushes_sent: int
    pushes_failed: int
    created_at: datetime
