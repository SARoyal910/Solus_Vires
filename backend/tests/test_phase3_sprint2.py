"""Phase 3 Sprint 2: the trusted contact as a user (P3-I1 alert context, P3-I2 note, P3-I3 ack)."""

import base64
import uuid

from sqlalchemy import text
from test_checkin import _make_everyone_overdue

from app.core import at_rest
from app.core.db import engine
from app.services import checkin as checkin_service
from app.services.checkin import CheckinService, make_contact_token
from conftest import register_and_login

KEY = base64.urlsafe_b64encode(b"\x07" * 32).decode()


def _survivor_with_contacts(name, n=2):
    s = register_and_login(name)
    tokens = []
    for i in range(n):
        c = s.post("/api/checkin/contacts", json={"nickname": f"c{i}", "contact_email": f"c{i}@example.com"}).json()
        token = make_contact_token(uuid.UUID(c["id"]))
        assert s.post(f"/api/checkin/invite/{token}/accept").status_code == 200
        tokens.append(token)
    s.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    return s, tokens


def _quiet(monkeypatch):
    emails = []
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: emails.append(kw) or "brevo")
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: True)
    return emails


# ---------- P3-I2: at-rest encryption and the note ----------


def test_at_rest_round_trips_and_is_bound_to_its_row(settings_env):
    settings_env(CONTACT_NOTE_KEY=KEY)
    sealed = at_rest.encrypt_text("call my sister first", associated="user-1")
    assert "sister" not in sealed and sealed.startswith("v1:")
    assert at_rest.decrypt_text(sealed, associated="user-1") == "call my sister first"
    try:
        at_rest.decrypt_text(sealed, associated="user-2")
    except Exception:
        pass
    else:
        raise AssertionError("a note moved to another row must not decrypt")


def test_note_is_off_without_a_key(settings_env):
    settings_env(CONTACT_NOTE_KEY=None)
    s, _ = _survivor_with_contacts("nokey")
    assert s.get("/api/checkin/schedule").json()["contact_note_available"] is False
    assert s.put("/api/checkin/schedule/contact-note", json={"note": "hello"}).status_code == 503
    # Clearing always works.
    assert s.put("/api/checkin/schedule/contact-note", json={"note": ""}).status_code == 200


def test_note_is_stored_encrypted_and_shown_back_to_the_survivor(settings_env):
    settings_env(CONTACT_NOTE_KEY=KEY)
    s, _ = _survivor_with_contacts("noted")
    r = s.put("/api/checkin/schedule/contact-note", json={"note": "  Call my sister Ana first.\nDon't call Mum. "})
    assert r.status_code == 200
    assert r.json()["contact_note"] == "Call my sister Ana first. Don't call Mum."
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT contact_note FROM checkin_schedules")).scalar()
    assert stored.startswith("v1:") and "Ana" not in stored
    assert s.put("/api/checkin/schedule/contact-note", json={"note": "x" * 501}).status_code == 422
    assert s.put("/api/checkin/schedule/contact-note", json={"note": ""}).json()["contact_note"] is None


def test_alert_email_carries_the_note_escaped(settings_env, monkeypatch):
    settings_env(CONTACT_NOTE_KEY=KEY)
    emails = _quiet(monkeypatch)
    s, _ = _survivor_with_contacts("emailed")
    s.put("/api/checkin/schedule/contact-note", json={"note": "Ring Ana <first>"})
    _make_everyone_overdue()
    emails.clear()
    CheckinService().run_due_alerts_once()
    assert len(emails) == 2
    assert "left this message" in emails[0]["html_content"]
    assert "Ring Ana &lt;first&gt;" in emails[0]["html_content"]


# ---------- P3-I1: alert context on the invite link ----------


def test_invite_shows_alert_context_only_while_alerts_go_out(settings_env, monkeypatch):
    settings_env(CONTACT_NOTE_KEY=KEY)
    _quiet(monkeypatch)
    s, (t1, t2) = _survivor_with_contacts("context")
    s.put("/api/checkin/schedule/contact-note", json={"note": "Try my cell first."})
    assert s.get(f"/api/checkin/invite/{t1}").json()["alert"] is None

    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    info = s.get(f"/api/checkin/invite/{t1}").json()
    alert = info["alert"]
    assert alert["alert_number"] == 1
    assert alert["hours_overdue"] >= 0
    assert alert["note"] == "Try my cell first."
    assert alert["acknowledged_by"] == 0
    assert alert["repeat_hours"] == 6
    # D12: nothing beyond the allowed fields.
    assert set(alert) == {"alert_number", "hours_overdue", "first_alert_at", "note", "acknowledged_by", "repeat_hours"}
    assert set(info) == {"survivor_username", "status", "subscribed_devices", "alert"}

    # Checking in ends the episode for every contact.
    s.post("/api/checkin/schedule/checkin")
    assert s.get(f"/api/checkin/invite/{t1}").json()["alert"] is None
    assert s.get(f"/api/checkin/invite/{t2}").json()["alert"] is None


def test_a_contact_who_has_not_accepted_sees_no_context(monkeypatch):
    _quiet(monkeypatch)
    s = register_and_login("pending_ctx")
    c = s.post("/api/checkin/contacts", json={"nickname": "p", "contact_email": "p@example.com"}).json()
    pending_token = make_contact_token(uuid.UUID(c["id"]))
    c2 = s.post("/api/checkin/contacts", json={"nickname": "a", "contact_email": "a@example.com"}).json()
    accepted_token = make_contact_token(uuid.UUID(c2["id"]))
    s.post(f"/api/checkin/invite/{accepted_token}/accept")
    s.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    assert s.get(f"/api/checkin/invite/{pending_token}").json()["alert"] is None
    assert s.get(f"/api/checkin/invite/{accepted_token}").json()["alert"]["alert_number"] == 1


def test_one_contacts_token_never_shows_another_survivors_context(monkeypatch):
    _quiet(monkeypatch)
    a, (ta,) = _survivor_with_contacts("survivor_a", n=1)
    b, (tb,) = _survivor_with_contacts("survivor_b", n=1)
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    # Only a checks in: a's contact sees no alert, b's still does.
    a.post("/api/checkin/schedule/checkin")
    assert a.get(f"/api/checkin/invite/{ta}").json()["alert"] is None
    assert b.get(f"/api/checkin/invite/{tb}").json()["alert"]["alert_number"] == 1


# ---------- P3-I3: acknowledgment ----------


def test_acknowledgment_is_a_count_visible_to_other_contacts(monkeypatch):
    _quiet(monkeypatch)
    s, (t1, t2) = _survivor_with_contacts("acked")
    assert s.post(f"/api/checkin/invite/{t1}/ack").status_code == 409  # nothing going out
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    assert s.post(f"/api/checkin/invite/{t1}/ack").json() == {"acknowledged_by": 1}
    assert s.get(f"/api/checkin/invite/{t2}").json()["alert"]["acknowledged_by"] == 1
    assert s.get("/api/checkin/schedule").json()["acknowledged_by"] == 1
    # Reset by the survivor checking in.
    s.post("/api/checkin/schedule/checkin")
    assert s.get("/api/checkin/schedule").json()["acknowledged_by"] == 0
    assert s.post(f"/api/checkin/invite/{t2}/ack").status_code == 409


def test_a_stopped_contact_cannot_acknowledge(monkeypatch):
    _quiet(monkeypatch)
    s, (t1,) = _survivor_with_contacts("stopped_ack", n=1)
    s.post(f"/api/checkin/invite/{t1}/stop")
    _make_everyone_overdue()
    CheckinService().run_due_alerts_once()
    assert s.post(f"/api/checkin/invite/{t1}/ack").status_code == 409
