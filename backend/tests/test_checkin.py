import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.db import SessionLocal
from app.core.notifications import PushSubscriptionExpired
from app.models.checkin import CheckinSchedule, PushSubscription
from app.services import checkin as checkin_service
from app.services.checkin import CheckinService, _parse_contact_token, make_contact_token
from conftest import register_and_login


def test_contact_token_round_trips():
    contact_id = uuid.uuid4()
    assert _parse_contact_token(make_contact_token(contact_id)) == contact_id


@pytest.mark.parametrize(
    "mangle",
    [
        lambda t: t[:-1] + ("0" if t[-1] != "0" else "1"),  # flipped signature
        lambda t: f"{uuid.uuid4()}.{t.rsplit('.', 1)[1]}",  # signature from another contact
        lambda t: t.split(".")[0],  # no signature
        lambda t: "not-a-token",
    ],
)
def test_tampered_contact_tokens_are_rejected(mangle):
    token = make_contact_token(uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        _parse_contact_token(mangle(token))
    assert exc.value.status_code == 404


def _schedule(active=True, deadline_offset_hours=0.0, grace_hours=6):
    now = datetime.now(timezone.utc)
    return CheckinSchedule(
        active=active,
        interval_hours=24,
        grace_hours=grace_hours,
        next_deadline_at=now + timedelta(hours=deadline_offset_hours),
    )


def test_not_overdue_before_deadline():
    assert not CheckinService.is_overdue(_schedule(deadline_offset_hours=1))


def test_not_overdue_inside_grace_period():
    assert not CheckinService.is_overdue(_schedule(deadline_offset_hours=-5, grace_hours=6))


def test_overdue_after_grace_period():
    assert CheckinService.is_overdue(_schedule(deadline_offset_hours=-7, grace_hours=6))


def test_inactive_schedule_is_never_overdue():
    assert not CheckinService.is_overdue(_schedule(active=False, deadline_offset_hours=-100))


def test_invite_link_flow():
    survivor = register_and_login("survivor_a")
    contact = survivor.post(
        "/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"}
    ).json()
    assert contact["status"] == "pending"

    token = make_contact_token(uuid.UUID(contact["id"]))
    info = survivor.get(f"/api/checkin/invite/{token}").json()
    assert info["survivor_username"] == "survivor_a"

    assert survivor.post(f"/api/checkin/invite/{token}/accept").status_code == 200
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "accepted"


def test_checkin_moves_the_deadline_forward():
    survivor = register_and_login("survivor_a")
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    first = survivor.get("/api/checkin/schedule").json()["next_deadline_at"]
    after = survivor.post("/api/checkin/schedule/checkin").json()["next_deadline_at"]
    assert after >= first


SUBSCRIPTION = {"endpoint": "https://push.example/device-1", "keys": {"p256dh": "key-1", "auth": "auth-1"}}


def _accepted_contact(survivor_name: str):
    survivor = register_and_login(survivor_name)
    contact = survivor.post(
        "/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"}
    ).json()
    token = make_contact_token(uuid.UUID(contact["id"]))
    survivor.post(f"/api/checkin/invite/{token}/accept")
    return survivor, token


def _make_everyone_overdue():
    with SessionLocal() as db:
        db.query(CheckinSchedule).update(
            {
                CheckinSchedule.active: True,
                CheckinSchedule.next_deadline_at: datetime.now(timezone.utc) - timedelta(days=2),
                CheckinSchedule.last_alert_sent_at: None,
            }
        )
        db.commit()


def test_one_phone_can_be_the_contact_for_two_survivors(monkeypatch):
    """H4: subscribing under a second invite must not steal the device from the first."""
    sent = []
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: sent.append((sub.endpoint, kw["body"])))
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: None)

    survivor_a, token_a = _accepted_contact("survivor_a")
    survivor_b, token_b = _accepted_contact("survivor_b")
    assert survivor_a.post(f"/api/checkin/invite/{token_a}/subscribe", json=SUBSCRIPTION).status_code == 200
    assert survivor_b.post(f"/api/checkin/invite/{token_b}/subscribe", json=SUBSCRIPTION).status_code == 200

    assert survivor_a.get("/api/checkin/contacts").json()[0]["subscribed_devices"] == 1
    assert survivor_b.get("/api/checkin/contacts").json()[0]["subscribed_devices"] == 1

    for survivor in (survivor_a, survivor_b):
        survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()

    assert sorted(body for _, body in sent) == [
        "survivor_a missed a scheduled check-in.",
        "survivor_b missed a scheduled check-in.",
    ]


def test_resubscribing_is_idempotent_and_refreshes_keys_everywhere():
    survivor_a, token_a = _accepted_contact("survivor_a")
    survivor_b, token_b = _accepted_contact("survivor_b")
    survivor_a.post(f"/api/checkin/invite/{token_a}/subscribe", json=SUBSCRIPTION)
    survivor_b.post(f"/api/checkin/invite/{token_b}/subscribe", json=SUBSCRIPTION)

    rotated = {**SUBSCRIPTION, "keys": {"p256dh": "key-2", "auth": "auth-2"}}
    survivor_a.post(f"/api/checkin/invite/{token_a}/subscribe", json=rotated)

    with SessionLocal() as db:
        rows = db.query(PushSubscription).all()
        assert len(rows) == 2
        assert {(r.p256dh, r.auth) for r in rows} == {("key-2", "auth-2")}


def test_expired_device_is_removed_for_every_contact(monkeypatch):
    def expired(sub, **kw):
        raise PushSubscriptionExpired()

    monkeypatch.setattr(checkin_service, "send_push", expired)
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: None)
    survivor_a, token_a = _accepted_contact("survivor_a")
    survivor_b, token_b = _accepted_contact("survivor_b")
    survivor_a.post(f"/api/checkin/invite/{token_a}/subscribe", json=SUBSCRIPTION)
    survivor_b.post(f"/api/checkin/invite/{token_b}/subscribe", json=SUBSCRIPTION)
    survivor_a.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()

    CheckinService().run_due_alerts_once()

    assert survivor_b.get("/api/checkin/contacts").json()[0]["subscribed_devices"] == 0


def test_alerts_point_contacts_to_guidance(monkeypatch):
    pushes, emails = [], []
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: pushes.append(kw))
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: emails.append(kw))
    survivor, token = _accepted_contact("survivor_a")
    survivor.post(f"/api/checkin/invite/{token}/subscribe", json=SUBSCRIPTION)
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()

    CheckinService().run_due_alerts_once()

    assert pushes[0]["url"].endswith("/if-you-get-an-alert.html")
    alert = emails[-1]["html_content"]
    assert "/if-you-get-an-alert.html" in alert
    assert "every 6 hours" in alert
