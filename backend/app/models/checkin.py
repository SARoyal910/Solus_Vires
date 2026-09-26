import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class TrustedContact(Base):
    """A person a survivor has invited to receive a missed-check-in alert.

    ``nickname`` is the survivor's own private label for this contact and is
    never shown to the contact. The contact only ever sees the survivor's
    username (already chosen to be non-identifying) via the invite link.
    """

    __tablename__ = "trusted_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nickname: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    invited_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class PushSubscription(Base):
    """One browser/device Web Push endpoint belonging to a trusted contact.

    The same endpoint can appear under several contacts: one person may be the
    trusted contact for more than one survivor, from the same phone.
    """

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("trusted_contact_id", "endpoint", name="uq_push_subscriptions_contact_endpoint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trusted_contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trusted_contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    contact: Mapped["TrustedContact"] = relationship(back_populates="subscriptions")


class CheckinSchedule(Base):
    """A survivor's opt-in "I'm OK" schedule. At most one row per user."""

    __tablename__ = "checkin_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    grace_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    last_checkin_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_deadline_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_alert_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
