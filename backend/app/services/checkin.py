import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape as html_escape

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..core import at_rest
from ..core.config import get_settings
from ..core.db import SessionLocal, engine
from ..core.notifications import PushSubscriptionExpired, ping_healthcheck, send_email, send_push
from ..core.security import sweep_expired_sessions
from ..models.auth import User
from ..models.checkin import CheckinAlertLog, CheckinSchedule, InviteEmail, PushSubscription, TrustedContact
from ..schemas.checkin import PushSubscriptionRequest, ScheduleUpdateRequest, TrustedContactCreate
from .vault import VaultService

logger = logging.getLogger("solusvires.checkin")

# Postgres advisory lock id for the alert pass ("SVALERT1" as ASCII). Any
# process running a pass must hold it; see run_due_alerts_once().
ALERT_PASS_LOCK_KEY = 0x5356414C45525431


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


def _invite_email_html(username: str, accept_url: str, base_url: str) -> str:
    return f"""
    <p>{username} has added you as a <strong>safety check-in contact</strong> on Solus Vires,
    a private safety resource site.</p>
    <p>This means: if {username} sets up a check-in schedule and misses it, you'll get an alert
    so you can check on them. You'll only receive anything if that happens.</p>
    <p><a href="{accept_url}">View this invite and choose whether to accept</a></p>
    <p>If you don't know why you're receiving this, you can safely ignore it or decline on that page.</p>
    <p>Not sure this email is real? You can see who runs the site at
    <a href="{base_url}/about.html">{base_url}/about.html</a>. We will never ask for a password.</p>
    <p>Want to know how to support someone?
    <a href="{base_url}/help-someone.html">How to help someone you care about</a></p>
    """.strip()


def _repeat_phrase(repeat_hours: int) -> str:
    return "every hour" if repeat_hours == 1 else f"every {repeat_hours} hours"


def _alert_label(number: int) -> str:
    return "Check-in alert" if number <= 1 else f"Check-in alert {number}"


def _alert_email_html(
    username: str, manage_url: str, base_url: str, repeat_hours: int, number: int = 1, note: str | None = None
) -> str:
    repeat_line = (
        "" if number <= 1 else f"<p>This is alert number {number}: {username} still hasn't checked in.</p>"
    )
    note_block = (
        f"<p><strong>{username} left this message for their contacts:</strong><br>{html_escape(note)}</p>"
        if note
        else ""
    )
    return f"""
    <p><strong>{username} hasn't checked in on Solus Vires as expected.</strong></p>
    {repeat_line}
    {note_block}
    <p>This is an automated safety check-in alert. It does not necessarily mean something is
    wrong, but {username} set this up to reach you if they miss a scheduled check-in.
    Consider reaching out to them the way you normally would. Don't contact the person they may
    be afraid of. If you believe they are in danger right now, call 911.</p>
    <p><a href="{base_url}/if-you-get-an-alert.html">What to do when you get this alert</a></p>
    <p>You'll get this alert again {_repeat_phrase(repeat_hours)} until {username} checks in.</p>
    <p><a href="{manage_url}">What to do now, and how to tell other contacts you're on it</a></p>
    """.strip()


def _stand_down_email_html(username: str, manage_url: str, base_url: str, reason: str) -> str:
    if reason == "turned_off":
        what = f"{username} has turned off their check-in schedule, so the missed check-in alerts have stopped."
    else:
        what = f"{username} has checked in on Solus Vires, so the missed check-in alerts have stopped."
    return f"""
    <p><strong>{what}</strong></p>
    <p>This only tells you that someone signed in to their account. If you were already worried about
    {username}, it's still fine to reach out the way you normally would. Don't contact the person they
    may be afraid of.</p>
    <p><a href="{base_url}/if-you-get-an-alert.html">What to do when you get an alert</a></p>
    <p><a href="{manage_url}">Manage or stop these alerts</a></p>
    """.strip()


# Alert history older than this is deleted by the maintenance sweep.
ALERT_LOG_RETENTION = timedelta(days=90)


class CheckinService:
    # ---------- Trusted contacts (survivor-authenticated) ----------

    def list_contacts(self, db: Session, user: User) -> list[TrustedContact]:
        return (
            db.query(TrustedContact)
            .filter(TrustedContact.user_id == user.id)
            .order_by(TrustedContact.created_at.asc())
            .all()
        )

    def _check_invite_cap(self, db: Session, user: User) -> None:
        """Refuses the invite when the account has sent its daily share (P3-J4)."""
        settings = get_settings()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        sent = (
            db.query(func.count(InviteEmail.id))
            .filter(InviteEmail.user_id == user.id, InviteEmail.sent_at > since)
            .scalar()
        )
        if sent >= settings.invite_emails_per_day:
            logger.info("invite_cap_reached")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've sent {settings.invite_emails_per_day} invites in the last day, which is the most "
                    "one account can send. Try again tomorrow."
                ),
            )

    def _send_invite_email(self, db: Session, user: User, contact: TrustedContact) -> None:
        settings = get_settings()
        db.add(InviteEmail(user_id=user.id))
        db.commit()
        accept_url = f"{settings.public_base_url}/checkin-invite.html?token={make_contact_token(contact.id)}"
        send_email(
            to_email=contact.contact_email,
            to_name=contact.nickname,
            subject=f"{user.username} added you as a safety check-in contact",
            html_content=_invite_email_html(user.username, accept_url, settings.public_base_url),
        )

    def add_contact(self, db: Session, user: User, payload: TrustedContactCreate) -> TrustedContact:
        self._check_invite_cap(db, user)
        contact = TrustedContact(
            user_id=user.id,
            nickname=payload.nickname.strip(),
            contact_email=str(payload.contact_email).strip(),
            status="pending",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

        self._send_invite_email(db, user, contact)
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
        self._check_invite_cap(db, user)
        # A contact who stopped alerts can be invited again: they get a fresh
        # invite and nothing reaches them unless they accept it again.
        if contact.status not in ("pending", "declined", "revoked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="This contact has already accepted."
            )
        contact.status = "pending"
        contact.responded_at = None
        contact.invited_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(contact)

        self._send_invite_email(db, user, contact)
        logger.info("trusted_contact_invite_resent")
        return contact

    def subscribed_device_count(self, db: Session, contact_id: uuid.UUID) -> int:
        return db.query(PushSubscription).filter(PushSubscription.trusted_contact_id == contact_id).count()

    def push_last_confirmed(self, db: Session, contact_id: uuid.UUID) -> datetime | None:
        """When the push service last accepted an alert for any of this contact's devices."""
        return (
            db.query(func.max(PushSubscription.last_push_ok_at))
            .filter(PushSubscription.trusted_contact_id == contact_id)
            .scalar()
        )

    # ---------- Alert history (survivor-authenticated) ----------

    def list_alert_log(self, db: Session, user: User, limit: int = 50) -> list[CheckinAlertLog]:
        return (
            db.query(CheckinAlertLog)
            .filter(CheckinAlertLog.user_id == user.id)
            .order_by(CheckinAlertLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def clear_alert_log(self, db: Session, user: User) -> None:
        db.query(CheckinAlertLog).filter(CheckinAlertLog.user_id == user.id).delete()
        db.commit()
        logger.info("checkin_alert_log_cleared")

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

    @staticmethod
    def _require_not_revoked(contact: TrustedContact) -> None:
        # Someone who stopped being a contact only comes back through a new
        # invite from the survivor, never by replaying an old link.
        if contact.status == "revoked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="You stopped these alerts. A new invite is needed."
            )

    def accept_invite(self, db: Session, token: str) -> TrustedContact:
        contact = self._get_contact_by_token(db, token)
        self._require_not_revoked(contact)
        contact.status = "accepted"
        contact.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(contact)
        logger.info("trusted_contact_accepted")
        return contact

    def decline_invite(self, db: Session, token: str) -> TrustedContact:
        contact = self._get_contact_by_token(db, token)
        self._require_not_revoked(contact)
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
        now = datetime.now(timezone.utc)
        # The browser's current keys apply to every contact this device serves;
        # stale keys would make pushes to the other invites silently unreadable.
        same_device = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).all()
        for sub in same_device:
            sub.p256dh = payload.keys.p256dh
            sub.auth = payload.keys.auth
            sub.last_seen_at = now

        contact.push_lost_at = None
        if not any(sub.trusted_contact_id == contact.id for sub in same_device):
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

    def update_schedule(
        self, db: Session, user: User, payload: ScheduleUpdateRequest
    ) -> tuple[CheckinSchedule, str | None]:
        """Saves the schedule. Also returns a stand-down reason when contacts were
        mid-alert and must now be told the alerts have stopped, else None."""
        schedule = self._get_or_create_schedule(db, user)
        was_active = schedule.active
        stand_down = None
        if was_active and not payload.active and schedule.alerts_sent_count > 0:
            stand_down = "turned_off"
            schedule.alerts_sent_count = 0
            schedule.last_alert_sent_at = None
            schedule.ack_count = 0
            schedule.first_ack_at = None
        schedule.active = payload.active
        schedule.interval_hours = payload.interval_hours
        schedule.grace_hours = payload.grace_hours

        now = datetime.now(timezone.utc)
        if payload.active and (not was_active or schedule.last_checkin_at is None):
            # Turning check-ins on counts as checking in.
            schedule.last_checkin_at = now
            schedule.last_alert_sent_at = None
            schedule.alerts_sent_count = 0
        if payload.active:
            # Recomputed on every save, so shortening the interval takes
            # effect now rather than after the old deadline (review M4). A
            # deadline that would already be past lands on "now", so the
            # grace period still runs before anyone is alerted.
            schedule.next_deadline_at = max(
                schedule.last_checkin_at + timedelta(hours=payload.interval_hours), now
            )

        db.commit()
        db.refresh(schedule)
        logger.info("checkin_schedule_updated")
        return schedule, stand_down

    def checkin(self, db: Session, user: User) -> tuple[CheckinSchedule, bool]:
        """Records "I'm OK". Also returns whether contacts were alerted since the
        last check-in and so need a stand-down."""
        schedule = self._get_or_create_schedule(db, user)
        now = datetime.now(timezone.utc)
        needs_stand_down = schedule.alerts_sent_count > 0
        schedule.last_checkin_at = now
        schedule.next_deadline_at = now + timedelta(hours=schedule.interval_hours)
        schedule.last_alert_sent_at = None
        schedule.alerts_sent_count = 0
        schedule.ack_count = 0
        schedule.first_ack_at = None
        db.commit()
        db.refresh(schedule)
        logger.info("checkin_recorded")
        return schedule, needs_stand_down

    # ---------- Note to contacts (P3-I2) ----------

    def set_contact_note(self, db: Session, user: User, note: str) -> CheckinSchedule:
        """Stores the survivor's message to contacts, encrypted at rest; empty clears it."""
        schedule = self._get_or_create_schedule(db, user)
        text_value = " ".join(note.split())
        if not text_value:
            schedule.contact_note = None
        else:
            if not at_rest.enabled():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Notes to contacts aren't available on this server yet.",
                )
            schedule.contact_note = at_rest.encrypt_text(text_value, associated=str(user.id))
        db.commit()
        db.refresh(schedule)
        logger.info("checkin_contact_note_set" if text_value else "checkin_contact_note_cleared")
        return schedule

    @staticmethod
    def read_contact_note(schedule: CheckinSchedule) -> str | None:
        """Decrypts the note for the survivor's own page or an alert. None when unset or unreadable."""
        if not schedule.contact_note or not at_rest.enabled():
            return None
        try:
            return at_rest.decrypt_text(schedule.contact_note, associated=str(schedule.user_id))
        except Exception:
            logger.warning("checkin_contact_note_unreadable")
            return None

    # ---------- What a contact may see during alerts (P3-I1, D12) ----------

    def alert_context(self, db: Session, contact: TrustedContact) -> dict | None:
        """The alert the contact is being asked to act on, or None when there isn't one.

        Only an accepted contact, only while alerts are going out. Username,
        alert number, hours overdue, the survivor's note, and how many
        contacts have acknowledged: nothing about location, schedule or who
        the other contacts are.
        """
        if contact.status != "accepted":
            return None
        schedule = db.query(CheckinSchedule).filter(CheckinSchedule.user_id == contact.user_id).first()
        if schedule is None or not schedule.active or (schedule.alerts_sent_count or 0) == 0:
            return None
        settings = get_settings()
        now = datetime.now(timezone.utc)
        deadline = now
        if schedule.next_deadline_at:
            deadline = schedule.next_deadline_at + timedelta(hours=schedule.grace_hours)
        return {
            "alert_number": schedule.alerts_sent_count,
            "hours_overdue": max(0, int((now - deadline).total_seconds() // 3600)),
            "first_alert_at": (
                schedule.last_alert_sent_at
                - timedelta(hours=settings.checkin_alert_repeat_hours * (schedule.alerts_sent_count - 1))
                if schedule.last_alert_sent_at
                else None
            ),
            "note": self.read_contact_note(schedule),
            "acknowledged_by": schedule.ack_count or 0,
            "repeat_hours": settings.checkin_alert_repeat_hours,
        }

    def acknowledge_alert(self, db: Session, token: str) -> int:
        """A contact says "I've got this" (P3-I3). Returns the acknowledgment count."""
        contact = self._get_contact_by_token(db, token)
        if contact.status != "accepted":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This invite isn't active.")
        schedule = db.query(CheckinSchedule).filter(CheckinSchedule.user_id == contact.user_id).first()
        if schedule is None or (schedule.alerts_sent_count or 0) == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No alert is going out right now.")
        schedule.ack_count = (schedule.ack_count or 0) + 1
        if schedule.first_ack_at is None:
            schedule.first_ack_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("checkin_alert_acknowledged")
        return schedule.ack_count

    @staticmethod
    def is_overdue(schedule: CheckinSchedule) -> bool:
        if not schedule.active or schedule.next_deadline_at is None:
            return False
        deadline_with_grace = schedule.next_deadline_at + timedelta(hours=schedule.grace_hours)
        return datetime.now(timezone.utc) > deadline_with_grace

    # ---------- Background alert loop ----------

    def _notify_contacts(
        self, db: Session, user: User, *, push_title: str, push_body: str, subject: str, html_for
    ) -> CheckinAlertLog:
        """Pushes to every device and emails every accepted contact; returns counts for the log."""
        settings = get_settings()
        contacts = (
            db.query(TrustedContact)
            .filter(TrustedContact.user_id == user.id, TrustedContact.status == "accepted")
            .all()
        )
        entry = CheckinAlertLog(
            user_id=user.id,
            contacts_notified=len(contacts),
            emails_sent=0,
            emails_via_fallback=0,
            pushes_sent=0,
            pushes_failed=0,
        )
        now = datetime.now(timezone.utc)
        dead_endpoints: set[str] = set()
        for contact in contacts:
            for sub in list(contact.subscriptions):
                if sub.endpoint in dead_endpoints:
                    entry.pushes_failed += 1
                    continue
                try:
                    delivered = send_push(
                        sub,
                        title=push_title,
                        body=push_body,
                        url=f"{settings.public_base_url}/if-you-get-an-alert.html",
                    )
                except PushSubscriptionExpired:
                    # The device is gone for every contact it served, not just
                    # this one; flag each of them so the survivor can see it.
                    owners = [
                        row.trusted_contact_id
                        for row in db.query(PushSubscription).filter(PushSubscription.endpoint == sub.endpoint)
                    ]
                    db.query(TrustedContact).filter(TrustedContact.id.in_(owners)).update(
                        {TrustedContact.push_lost_at: now}, synchronize_session=False
                    )
                    dead_endpoints.add(sub.endpoint)
                    db.query(PushSubscription).filter(PushSubscription.endpoint == sub.endpoint).delete()
                    db.commit()
                    entry.pushes_failed += 1
                    continue
                if delivered:
                    sub.last_push_ok_at = now
                    entry.pushes_sent += 1
                else:
                    entry.pushes_failed += 1

            manage_url = f"{settings.public_base_url}/checkin-invite.html?token={make_contact_token(contact.id)}"
            carried_by = send_email(
                to_email=contact.contact_email,
                to_name=contact.nickname,
                subject=subject,
                html_content=html_for(manage_url),
            )
            if carried_by:
                entry.emails_sent += 1
                if carried_by == "postmark":
                    entry.emails_via_fallback += 1
        return entry

    def _alert_contacts_for(self, db: Session, user: User, schedule: CheckinSchedule) -> None:
        settings = get_settings()
        number = (schedule.alerts_sent_count or 0) + 1
        label = _alert_label(number)
        # Email goes out on every alert, not only when push fails: push
        # delivery is never confirmed, and a duplicate alert is safer than a
        # missed one (Phase 2 decision D4).
        entry = self._notify_contacts(
            db,
            user,
            push_title=f"Solus Vires {label.lower()}",
            push_body=(
                f"{user.username} missed a scheduled check-in. This repeats "
                f"{_repeat_phrase(settings.checkin_alert_repeat_hours)} until they check in."
            ),
            subject=f"{label}: {user.username} missed a check-in",
            html_for=lambda manage_url: _alert_email_html(
                user.username,
                manage_url,
                settings.public_base_url,
                settings.checkin_alert_repeat_hours,
                number,
                self.read_contact_note(schedule),
            ),
        )
        entry.kind = "alert"
        entry.alert_number = number
        db.add(entry)
        schedule.alerts_sent_count = number
        schedule.last_alert_sent_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("checkin_alerts_sent")

    def send_stand_down(self, user_id: uuid.UUID, reason: str = "checked_in") -> None:
        """Tells contacts who were alerted that the alerts have stopped.

        Runs after the survivor's request has returned (a FastAPI background
        task), with its own database session. Never raises.
        """
        settings = get_settings()
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user is None:
                    return
                body = (
                    f"{user.username} turned off check-ins. Alerts have stopped."
                    if reason == "turned_off"
                    else f"{user.username} checked in. Alerts have stopped."
                )
                entry = self._notify_contacts(
                    db,
                    user,
                    push_title="Solus Vires: alerts stopped",
                    push_body=body,
                    subject=f"{user.username} " + ("turned off check-ins" if reason == "turned_off" else "checked in"),
                    html_for=lambda manage_url: _stand_down_email_html(
                        user.username, manage_url, settings.public_base_url, reason
                    ),
                )
                entry.kind = "turned_off" if reason == "turned_off" else "stand_down"
                db.add(entry)
                db.commit()
                logger.info("checkin_stand_down_sent")
        except Exception:
            logger.exception("checkin_stand_down_failed")

    def run_due_alerts_once(self) -> bool:
        """Runs one pass over all active schedules, alerting contacts for any overdue survivor.

        Only one process may run a pass at a time: a Postgres advisory lock,
        held on its own connection for the whole pass, makes a second alert
        loop against the same database (say, a local uvicorn next to the
        Docker api) skip instead of sending duplicate alerts (review M1).
        Returns False when another process held the lock and this pass was skipped.
        """
        with engine.connect() as lock_conn:
            acquired = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ALERT_PASS_LOCK_KEY}
            ).scalar()
            lock_conn.commit()
            if not acquired:
                logger.info("checkin_alert_pass_skipped_locked")
                return False
            try:
                self._run_pass()
                self._run_maintenance()
            finally:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ALERT_PASS_LOCK_KEY})
                lock_conn.commit()
        # Only a pass that ran to the end pings: a pass that raised, or a
        # loop that stopped, shows up as a missed heartbeat (P2-F2).
        ping_healthcheck()
        return True

    def _run_pass(self) -> None:
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
                    db.rollback()
                    logger.exception("checkin_alert_pass_failed")
        finally:
            db.close()

    def _run_maintenance(self) -> None:
        """Housekeeping that rides on the alert loop; a failure here never affects alerts."""
        try:
            with SessionLocal() as db:
                deleted = sweep_expired_sessions(db)
                db.query(CheckinAlertLog).filter(
                    CheckinAlertLog.created_at < datetime.now(timezone.utc) - ALERT_LOG_RETENTION
                ).delete()
                db.query(InviteEmail).filter(
                    InviteEmail.sent_at < datetime.now(timezone.utc) - timedelta(hours=25)
                ).delete()
                db.commit()
                # Photos staged by a PIN change that never finished (P3-J2).
                # A change in progress completes within minutes; the pass
                # runs every five, so anything still staged here is abandoned.
                VaultService().discard_stale_rekey_copies(db)
            if deleted:
                logger.info("expired_sessions_swept", extra={"count": deleted})
        except Exception:
            logger.exception("maintenance_failed")

    async def run_alert_loop(self) -> None:
        settings = get_settings()
        while True:
            await asyncio.sleep(settings.checkin_alert_check_seconds)
            try:
                await asyncio.to_thread(self.run_due_alerts_once)
            except Exception:
                # A failed pass (database briefly unreachable, say) must not
                # end the loop: alerts would silently stop until a restart.
                logger.exception("checkin_alert_loop_pass_failed")
