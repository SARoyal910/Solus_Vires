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


class InviteInfoResponse(BaseModel):
    survivor_username: str
    status: str
    subscribed_devices: int


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeys
