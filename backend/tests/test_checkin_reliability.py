"""P2-E5: stand-downs, numbered repeats, push health, alert history, re-invites."""

from datetime import datetime, timedelta, timezone

import pytest
from test_checkin import SUBSCRIPTION, _accepted_contact, _make_everyone_overdue

from app.core.db import SessionLocal
from app.core.notifications import PushSubscriptionExpired
from app.models.checkin import CheckinAlertLog, CheckinSchedule
from app.services import checkin as checkin_service
from app.services.checkin import CheckinService
from conftest import register_and_login

SCHEDULE = {"active": True, "interval_hours": 24, "grace_hours": 6}


@pytest.fixture
def outbox(monkeypatch):
    """Records every email and push instead of sending it."""
    box = {"emails": [], "pushes": []}
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: box["emails"].append(kw) or True)
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: box["pushes"].append(kw) or True)
    return box


def _subscribed_overdue(name="survivor_a"):
    survivor, token = _accepted_contact(name)
    survivor.post(f"/api/checkin/invite/{token}/subscribe", json=SUBSCRIPTION)
    survivor.put("/api/checkin/schedule", json=SCHEDULE)
    _make_everyone_overdue()
    return survivor, token


def _allow_repeat():
    with SessionLocal() as db:
        db.query(CheckinSchedule).update(
            {CheckinSchedule.last_alert_sent_at: datetime.now(timezone.utc) - timedelta(hours=7)}
        )
        db.commit()


def test_checking_in_after_an_alert_stands_contacts_down(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    outbox["emails"].clear()
    outbox["pushes"].clear()

    assert survivor.post("/api/checkin/schedule/checkin").status_code == 200

    assert len(outbox["emails"]) == 1 and len(outbox["pushes"]) == 1
    assert outbox["emails"][0]["subject"] == "survivor_a checked in"
    assert "alerts have stopped" in outbox["emails"][0]["html_content"]
    assert "only tells you that someone signed in" in outbox["emails"][0]["html_content"]
    assert "Alerts have stopped" in outbox["pushes"][0]["body"]


def test_a_routine_checkin_sends_nothing(outbox):
    survivor, _ = _accepted_contact("survivor_a")
    survivor.put("/api/checkin/schedule", json=SCHEDULE)
    outbox["emails"].clear()
    survivor.post("/api/checkin/schedule/checkin")
    survivor.post("/api/checkin/schedule/checkin")
    assert outbox["emails"] == [] and outbox["pushes"] == []


def test_only_the_first_checkin_after_an_alert_stands_down(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    survivor.post("/api/checkin/schedule/checkin")
    outbox["emails"].clear()
    survivor.post("/api/checkin/schedule/checkin")
    assert outbox["emails"] == []


def test_turning_check_ins_off_mid_alert_tells_contacts(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    outbox["emails"].clear()

    survivor.put("/api/checkin/schedule", json={**SCHEDULE, "active": False})

    assert [e["subject"] for e in outbox["emails"]] == ["survivor_a turned off check-ins"]


def test_repeat_alerts_are_numbered(outbox):
    _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    _allow_repeat()
    CheckinService().run_due_alerts_once()

    first, second = outbox["emails"][-2:]
    assert first["subject"] == "Check-in alert: survivor_a missed a check-in"
    assert "alert number" not in first["html_content"]
    assert second["subject"] == "Check-in alert 2: survivor_a missed a check-in"
    assert "This is alert number 2" in second["html_content"]
    assert outbox["pushes"][-1]["title"] == "Solus Vires check-in alert 2"


def test_numbering_restarts_after_a_checkin(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    survivor.post("/api/checkin/schedule/checkin")
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    assert outbox["emails"][-1]["subject"].startswith("Check-in alert:")


def test_contacts_show_when_push_was_last_confirmed(outbox):
    survivor, _ = _subscribed_overdue()
    assert survivor.get("/api/checkin/contacts").json()[0]["push_last_confirmed_at"] is None

    CheckinService().run_due_alerts_once()

    confirmed = survivor.get("/api/checkin/contacts").json()[0]["push_last_confirmed_at"]
    assert datetime.now(timezone.utc) - datetime.fromisoformat(confirmed) < timedelta(minutes=1)


def test_a_dead_push_device_is_flagged_for_every_survivor_and_cleared_on_resubscribe(monkeypatch, outbox):
    def expired(sub, **kw):
        raise PushSubscriptionExpired()

    survivor_a, token_a = _accepted_contact("survivor_a")
    survivor_b, token_b = _accepted_contact("survivor_b")
    survivor_a.post(f"/api/checkin/invite/{token_a}/subscribe", json=SUBSCRIPTION)
    survivor_b.post(f"/api/checkin/invite/{token_b}/subscribe", json=SUBSCRIPTION)
    survivor_a.put("/api/checkin/schedule", json=SCHEDULE)
    _make_everyone_overdue()
    monkeypatch.setattr(checkin_service, "send_push", expired)

    CheckinService().run_due_alerts_once()

    for survivor in (survivor_a, survivor_b):
        contact = survivor.get("/api/checkin/contacts").json()[0]
        assert contact["subscribed_devices"] == 0
        assert contact["push_lost_at"] is not None
    assert len(outbox["emails"]) >= 1  # email still went

    survivor_b.post(f"/api/checkin/invite/{token_b}/subscribe", json=SUBSCRIPTION)
    assert survivor_b.get("/api/checkin/contacts").json()[0]["push_lost_at"] is None
    assert survivor_a.get("/api/checkin/contacts").json()[0]["push_lost_at"] is not None


def test_alert_history_records_alerts_and_stand_downs(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    _allow_repeat()
    CheckinService().run_due_alerts_once()
    survivor.post("/api/checkin/schedule/checkin")

    history = survivor.get("/api/checkin/alerts").json()
    assert [(h["kind"], h["alert_number"]) for h in history] == [
        ("stand_down", None),
        ("alert", 2),
        ("alert", 1),
    ]
    assert history[-1] | {"created_at": None} == {
        "kind": "alert",
        "alert_number": 1,
        "contacts_notified": 1,
        "emails_sent": 1,
        "pushes_sent": 1,
        "pushes_failed": 0,
        "created_at": None,
    }


def test_alert_history_is_private_and_clearable(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    other = register_and_login("survivor_b")
    assert other.get("/api/checkin/alerts").json() == []

    assert survivor.delete("/api/checkin/alerts").status_code == 200
    assert survivor.get("/api/checkin/alerts").json() == []


def test_old_alert_history_is_swept(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    with SessionLocal() as db:
        db.query(CheckinAlertLog).update(
            {CheckinAlertLog.created_at: datetime.now(timezone.utc) - timedelta(days=91)}
        )
        db.commit()
    CheckinService().run_due_alerts_once()  # maintenance runs at the end of each pass
    assert survivor.get("/api/checkin/alerts").json() == []


def test_a_contact_who_stopped_can_be_invited_again(outbox):
    survivor, token = _accepted_contact("survivor_a")
    contact_id = survivor.get("/api/checkin/contacts").json()[0]["id"]
    survivor.post(f"/api/checkin/invite/{token}/stop")
    # The old link alone can't bring them back: that takes a new invite.
    assert survivor.post(f"/api/checkin/invite/{token}/accept").status_code == 409
    outbox["emails"].clear()

    response = survivor.post(f"/api/checkin/contacts/{contact_id}/resend")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert len(outbox["emails"]) == 1 and "added you" in outbox["emails"][0]["subject"]
    assert survivor.post(f"/api/checkin/invite/{token}/accept").status_code == 200
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "accepted"


def test_an_accepted_contact_is_not_re_invited(outbox):
    survivor, _ = _accepted_contact("survivor_a")
    contact_id = survivor.get("/api/checkin/contacts").json()[0]["id"]
    assert survivor.post(f"/api/checkin/contacts/{contact_id}/resend").status_code == 409


def test_only_the_owner_can_re_invite(outbox):
    survivor, token = _accepted_contact("survivor_a")
    contact_id = survivor.get("/api/checkin/contacts").json()[0]["id"]
    survivor.post(f"/api/checkin/invite/{token}/stop")
    other = register_and_login("survivor_b")
    assert other.post(f"/api/checkin/contacts/{contact_id}/resend").status_code == 404
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "revoked"


def test_schedule_reports_alerts_sent_until_checkin(outbox):
    survivor, _ = _subscribed_overdue()
    CheckinService().run_due_alerts_once()
    assert survivor.get("/api/checkin/schedule").json()["alerts_sent"] == 1
    assert survivor.post("/api/checkin/schedule/checkin").json()["alerts_sent"] == 0
