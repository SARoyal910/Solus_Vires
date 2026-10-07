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
    # Set when this contact's push device was pruned as expired; cleared when
    # they subscribe again. Shown to the survivor as a warning.
    push_lost_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
    # When the push service last accepted an alert for this device. Accepted is
    # not the same as seen: no browser reports that back.
    last_push_ok_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
    # Alerts sent since the last check-in: numbers repeats, and a check-in
    # with this above zero sends contacts a stand-down.
    alerts_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Contacts who pressed "I've got this" during the current alert episode
    # (P3-I3): a count and the first time, nothing about who. Reset with
    # alerts_sent_count when the survivor checks in.
    ack_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_ack_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # The survivor's note to contacts (P3-I2), AES-GCM at rest under
    # CONTACT_NOTE_KEY, decrypted only when an alert goes out. Up to 500
    # characters of plaintext.
    contact_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CheckinAlertLog(Base):
    """The survivor's own history of alerts and stand-downs sent for them.

    Counts only: never message text, contact addresses, or anything about the
    survivor's device or location. Clearable by the survivor; deleted with the account.
    """

    __tablename__ = "checkin_alert_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # alert | stand_down | turned_off
    alert_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contacts_notified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    emails_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many of emails_sent the fallback provider carried (0 = all primary).
    # Lets a delivery problem be traced to a provider without logging addresses.
    emails_via_fallback: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pushes_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pushes_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class InviteEmail(Base):
    """One row per trusted-contact invite email sent, for the daily cap (P3-J4).

    The alert path depends on the email quota; this stops one account spending
    it. Rows older than a day are swept by the maintenance pass. No addresses.
    """

    __tablename__ = "invite_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sent_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
