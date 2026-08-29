import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.db import SessionLocal
from ..core.notifications import PushSubscriptionExpired, send_email, send_push
from ..models.auth import User
from ..models.checkin import CheckinSchedule, PushSubscription, TrustedContact
from ..schemas.checkin import PushSubscriptionRequest, ScheduleUpdateRequest, TrustedContactCreate

logger = logging.getLogger("solusvires.checkin")


def _sign(contact_id: uuid.UUID) -> str:
    """HMACs a contact id with the server's signing secret.

    The invite/manage link is a capability URL the server itself must be able
    to re-embed in emails sent long after the contact row was created (e.g.
    a missed-check-in alert), so it can't be a one-way-hashed, verify-only
    secret like a session token. Deriving it deterministically from
    (contact_id, server secret) means nothing extra needs to be stored, and
    the exact same link can be regenerated forever.
    """
    settings = get_settings()
    return hmac.new(settings.checkin_token_secret.encode("utf-8"), contact_id.bytes, sha256).hexdigest()


def make_contact_token(contact_id: uuid.UUID) -> str:
    return f"{contact_id}.{_sign(contact_id)}"


def _parse_contact_token(token: str) -> uuid.UUID:
    try:
        id_part, signature = token.rsplit(".", 1)
        contact_id = uuid.UUID(id_part)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.") from exc
    if not hmac.compare_digest(_sign(contact_id), signature):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    return contact_id


def _invite_email_html(username: str, accept_url: str) -> str:
    return f"""
    <p>{username} has added you as a <strong>safety check-in contact</strong> on Solus Vires,
    a private safety resource site.</p>
    <p>This means: if {username} sets up a check-in schedule and misses it, you'll get an alert
    so you can check on them. You'll only receive anything if that happens.</p>
    <p><a href="{accept_url}">View this invite and choose whether to accept</a></p>
    <p>If you don't know why you're receiving this, you can safely ignore it or decline on that page.</p>
    """.strip()


def _alert_email_html(username: str, manage_url: str) -> str:
    return f"""
    <p><strong>{username} hasn't checked in on Solus Vires as expected.</strong></p>
    <p>This is an automated safety check-in alert. It does not necessarily mean something is
    wrong, but {username} set this up to reach you if they miss a scheduled check-in.
    Consider reaching out to them directly.</p>
    <p><a href="{manage_url}">Manage or stop these alerts</a></p>
    """.strip()


class CheckinService:
    # ---------- Trusted contacts (survivor-authenticated) ----------

    def list_contacts(self, db: Session, user: User) -> list[TrustedContact]:
        return (
            db.query(TrustedContact)
            .filter(TrustedContact.user_id == user.id)
            .order_by(TrustedContact.created_at.asc())
            .all()
        )

    def _send_invite_email(self, user: User, contact: TrustedContact) -> None:
        settings = get_settings()
        accept_url = f"{settings.public_base_url}/checkin-invite.html?token={make_contact_token(contact.id)}"
        send_email(
            to_email=contact.contact_email,
            to_name=contact.nickname,
            subject=f"{user.username} added you as a safety check-in contact",
            html_content=_invite_email_html(user.username, accept_url),
        )

    def add_contact(self, db: Session, user: User, payload: TrustedContactCreate) -> TrustedContact:
        contact = TrustedContact(
            user_id=user.id,
            nickname=payload.nickname.strip(),
            contact_email=str(payload.contact_email).strip(),
            status="pending",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

        self._send_invite_email(user, contact)
        logger.info("trusted_contact_invited")
        return contact

    def _get_owned_contact(self, db: Session, user: User, contact_id: uuid.UUID) -> TrustedContact:
        contact = (
            db.query(TrustedContact)
            .filter(TrustedContact.id == contact_id, TrustedContact.user_id == user.id)
            .first()
        )
        if contact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
        return contact

    def remove_contact(self, db: Session, user: User, contact_id: uuid.UUID) -> None:
        contact = self._get_owned_contact(db, user, contact_id)
        db.delete(contact)
        db.commit()
        logger.info("trusted_contact_removed")

    def resend_invite(self, db: Session, user: User, contact_id: uuid.UUID) -> TrustedContact:
        contact = self._get_owned_contact(db, user, contact_id)
        if contact.status not in ("pending", "declined"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="This contact already responded."
            )
        contact.status = "pending"
        contact.responded_at = None
        db.commit()
        db.refresh(contact)

        self._send_invite_email(user, contact)
        logger.info("trusted_contact_invite_resent")
        return contact

    def subscribed_device_count(self, db: Session, contact_id: uuid.UUID) -> int:
        return db.query(PushSubscription).filter(PushSubscription.trusted_contact_id == contact_id).count()

    # ---------- Public invite endpoints (token-authenticated, no account) ----------

    def _get_contact_by_token(self, db: Session, token: str) -> TrustedContact:
        contact_id = _parse_contact_token(token)
        contact = db.get(TrustedContact, contact_id)
        if contact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
        return contact

    def get_invite(self, db: Session, token: str) -> tuple[TrustedContact, User]:
        contact = self._get_contact_by_token(db, token)
        user = db.get(User, contact.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
        return contact, user

    def accept_invite(self, db: Session, token: str) -> TrustedContact:
        contact = self._get_contact_by_token(db, token)
        contact.status = "accepted"
        contact.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(contact)
        logger.info("trusted_contact_accepted")
        return contact

    def decline_invite(self, db: Session, token: str) -> TrustedContact:
        contact = self._get_contact_by_token(db, token)
        contact.status = "declined"
        contact.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(contact)
        logger.info("trusted_contact_declined")
        return contact

    def stop_invite(self, db: Session, token: str) -> TrustedContact:
        contact = self._get_contact_by_token(db, token)
        contact.status = "revoked"
        db.query(PushSubscription).filter(PushSubscription.trusted_contact_id == contact.id).delete()
        db.commit()
        db.refresh(contact)
        logger.info("trusted_contact_revoked_by_contact")
        return contact

    def add_subscription(self, db: Session, token: str, payload: PushSubscriptionRequest) -> None:
        contact = self._get_contact_by_token(db, token)
        if contact.status != "accepted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Accept the invite before subscribing."
            )
        existing = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
        if existing is not None:
            existing.trusted_contact_id = contact.id
            existing.p256dh = payload.keys.p256dh
            existing.auth = payload.keys.auth
            existing.last_seen_at = datetime.now(timezone.utc)
        else:
            db.add(
                PushSubscription(
                    trusted_contact_id=contact.id,
                    endpoint=payload.endpoint,
                    p256dh=payload.keys.p256dh,
                    auth=payload.keys.auth,
                )
            )
        db.commit()
        logger.info("push_subscription_added")

    # ---------- Schedule + check-in (survivor-authenticated) ----------

    def _get_or_create_schedule(self, db: Session, user: User) -> CheckinSchedule:
        schedule = db.query(CheckinSchedule).filter(CheckinSchedule.user_id == user.id).first()
        if schedule is None:
            schedule = CheckinSchedule(user_id=user.id)
            db.add(schedule)
            db.commit()
            db.refresh(schedule)
        return schedule

    def get_schedule(self, db: Session, user: User) -> CheckinSchedule:
        return self._get_or_create_schedule(db, user)

    def update_schedule(self, db: Session, user: User, payload: ScheduleUpdateRequest) -> CheckinSchedule:
        schedule = self._get_or_create_schedule(db, user)
        was_active = schedule.active
        schedule.active = payload.active
        schedule.interval_hours = payload.interval_hours
        schedule.grace_hours = payload.grace_hours

        if payload.active and (not was_active or schedule.next_deadline_at is None):
            now = datetime.now(timezone.utc)
            schedule.last_checkin_at = now
            schedule.next_deadline_at = now + timedelta(hours=payload.interval_hours)
            schedule.last_alert_sent_at = None

        db.commit()
        db.refresh(schedule)
        logger.info("checkin_schedule_updated")
        return schedule

    def checkin(self, db: Session, user: User) -> CheckinSchedule:
        schedule = self._get_or_create_schedule(db, user)
        now = datetime.now(timezone.utc)
        schedule.last_checkin_at = now
        schedule.next_deadline_at = now + timedelta(hours=schedule.interval_hours)
        schedule.last_alert_sent_at = None
        db.commit()
        db.refresh(schedule)
        logger.info("checkin_recorded")
        return schedule

    @staticmethod
    def is_overdue(schedule: CheckinSchedule) -> bool:
        if not schedule.active or schedule.next_deadline_at is None:
            return False
        deadline_with_grace = schedule.next_deadline_at + timedelta(hours=schedule.grace_hours)
        return datetime.now(timezone.utc) > deadline_with_grace

    # ---------- Background alert loop ----------

    def _alert_contacts_for(self, db: Session, user: User, schedule: CheckinSchedule) -> None:
        settings = get_settings()
        contacts = (
            db.query(TrustedContact)
            .filter(TrustedContact.user_id == user.id, TrustedContact.status == "accepted")
            .all()
        )

        for contact in contacts:
            for sub in list(contact.subscriptions):
                try:
                    send_push(
                        sub,
                        title="Solus Vires check-in alert",
                        body=f"{user.username} missed a scheduled check-in.",
                        url=settings.public_base_url,
                    )
                except PushSubscriptionExpired:
                    db.delete(sub)
                    db.commit()

            manage_url = f"{settings.public_base_url}/checkin-invite.html?token={make_contact_token(contact.id)}"
            send_email(
                to_email=contact.contact_email,
                to_name=contact.nickname,
                subject=f"Check-in alert: {user.username} missed a check-in",
                html_content=_alert_email_html(user.username, manage_url),
            )

        schedule.last_alert_sent_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("checkin_alerts_sent")

    def run_due_alerts_once(self) -> None:
        """Runs one pass over all active schedules, alerting contacts for any overdue survivor.

        Uses its own DB session since this runs outside any HTTP request.
        """
        settings = get_settings()
        db = SessionLocal()
        try:
            schedules = db.query(CheckinSchedule).filter(CheckinSchedule.active.is_(True)).all()
            now = datetime.now(timezone.utc)
            for schedule in schedules:
                try:
                    if not self.is_overdue(schedule):
                        continue
                    repeat_delta = timedelta(hours=settings.checkin_alert_repeat_hours)
                    if (
                        schedule.last_alert_sent_at is not None
                        and now - schedule.last_alert_sent_at < repeat_delta
                    ):
                        continue
                    user = db.get(User, schedule.user_id)
                    if user is None:
                        continue
                    self._alert_contacts_for(db, user, schedule)
                except Exception:
                    logger.exception("checkin_alert_pass_failed")
        finally:
            db.close()

    async def run_alert_loop(self) -> None:
        settings = get_settings()
        while True:
            await asyncio.sleep(settings.checkin_alert_check_seconds)
            await asyncio.to_thread(self.run_due_alerts_once)
