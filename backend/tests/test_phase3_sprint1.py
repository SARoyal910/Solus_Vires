"""Phase 3 Sprint 1: where you're signed in (P3-J1), the invite cap (P3-J4), and the
tests the threat model asked for (P3-J7)."""

import uuid

from sqlalchemy import text
from test_checkin import _make_everyone_overdue

from app.core.db import engine
from app.core.security import device_label
from app.services import checkin as checkin_service
from app.services.checkin import CheckinService, make_contact_token
from conftest import PASSWORD, login, make_client, register, register_and_login

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


# ---------- P3-J1 ----------


def test_device_label_is_browser_and_os_family_only():
    assert device_label(IPHONE) == "Safari on iPhone"
    assert device_label(WINDOWS) == "Chrome on Windows"
    assert device_label("Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0") == "Firefox on Linux"
    assert device_label("curl/8.4") == "Browser on a device"
    assert device_label(None) is None
    assert len(device_label(IPHONE)) <= 40


def test_sessions_list_shows_devices_and_marks_the_current_one():
    phone = make_client()
    register(phone, "sessions_user")
    assert login(phone, "sessions_user").status_code == 200  # the test client's own UA: generic label
    laptop = make_client()
    assert laptop.post(
        "/api/auth/login",
        json={"username": "sessions_user", "password": PASSWORD},
        headers={"User-Agent": WINDOWS},
    ).status_code == 200

    rows = laptop.get("/api/auth/sessions").json()
    assert len(rows) == 2
    assert sorted(r["device"] for r in rows) == ["Browser on a device", "Chrome on Windows"]
    current = [r for r in rows if r["current"]]
    assert len(current) == 1 and current[0]["device"] == "Chrome on Windows"
    # Nothing that could identify a network or be replayed.
    for row in rows:
        assert set(row) == {"current", "device", "created_at", "last_seen_at"}


def test_sign_out_everywhere_else_keeps_this_device():
    phone = make_client()
    register(phone, "others_user")
    assert login(phone, "others_user").status_code == 200
    laptop = make_client()
    assert login(laptop, "others_user").status_code == 200
    tablet = make_client()
    assert login(tablet, "others_user").status_code == 200

    result = laptop.post("/api/auth/logout-others").json()
    assert result == {"ok": True, "signed_out": 2}
    assert laptop.get("/api/auth/me").status_code == 200
    assert phone.get("/api/auth/me").status_code == 401
    assert tablet.get("/api/auth/me").status_code == 401
    assert len(laptop.get("/api/auth/sessions").json()) == 1


def test_raw_session_token_never_reaches_the_database():
    """THREAT_MODEL §6.4: the cookie value is the token; the database holds only its hash."""
    client = make_client()
    register(client, "token_user")
    response = login(client, "token_user")
    raw = response.cookies.get("sv_session")
    assert raw and len(raw) > 20
    with engine.connect() as conn:
        ids = [row[0] for row in conn.execute(text("SELECT id FROM sessions"))]
    assert ids and raw not in ids
    assert all(len(i) == 64 for i in ids)  # sha256 hex


# ---------- P3-J4 ----------


def _invite(survivor, n):
    return survivor.post(
        "/api/checkin/contacts", json={"nickname": f"c{n}", "contact_email": f"c{n}@example.com"}
    )


def test_invite_emails_are_capped_per_account_per_day(settings_env, monkeypatch):
    settings_env(INVITE_EMAILS_PER_DAY="3")
    sent = []
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: sent.append(kw) or "brevo")
    survivor = register_and_login("capped_user")
    for n in range(3):
        assert _invite(survivor, n).status_code == 200
    refused = _invite(survivor, 3)
    assert refused.status_code == 429
    assert "3 invites" in refused.json()["detail"]
    assert len(sent) == 3
    # Resends count against the same cap.
    contact_id = survivor.get("/api/checkin/contacts").json()[0]["id"]
    assert survivor.post(f"/api/checkin/contacts/{contact_id}/resend").status_code == 429
    # Another account is unaffected.
    other = register_and_login("uncapped_user")
    assert _invite(other, 0).status_code == 200


def test_invite_cap_window_rolls_over(settings_env, monkeypatch):
    settings_env(INVITE_EMAILS_PER_DAY="1")
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: "brevo")
    survivor = register_and_login("rollover_user")
    assert _invite(survivor, 0).status_code == 200
    assert _invite(survivor, 1).status_code == 429
    with engine.begin() as conn:
        conn.execute(text("UPDATE invite_emails SET sent_at = now() - interval '25 hours'"))
    assert _invite(survivor, 2).status_code == 200
    # The maintenance pass sweeps the old rows.
    CheckinService()._run_maintenance()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM invite_emails")).scalar() == 1


# ---------- P3-J7 ----------


def _accepted_contact(survivor):
    contact = survivor.post(
        "/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"}
    ).json()
    token = make_contact_token(uuid.UUID(contact["id"]))
    assert survivor.post(f"/api/checkin/invite/{token}/accept").status_code == 200
    return contact, token


def test_a_contact_who_stops_gets_no_more_alerts(monkeypatch):
    emails = []
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: emails.append(kw["to_email"]) or "brevo")
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: True)
    survivor = register_and_login("stop_user")
    contact, token = _accepted_contact(survivor)
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})

    assert survivor.post(f"/api/checkin/invite/{token}/stop").status_code == 200
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "revoked"
    _make_everyone_overdue()
    emails.clear()
    CheckinService().run_due_alerts_once()
    assert "jo@example.com" not in emails
    # The stopped contact can't be re-alerted by the survivor without a fresh accepted invite.
    assert survivor.post(f"/api/checkin/contacts/{contact['id']}/resend").status_code == 200
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "pending"
    emails.clear()
    CheckinService().run_due_alerts_once()
    assert "jo@example.com" not in emails


def test_removing_a_contact_removes_them_for_good(monkeypatch):
    emails = []
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: emails.append(kw["to_email"]) or "brevo")
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: True)
    survivor = register_and_login("remove_user")
    contact, token = _accepted_contact(survivor)
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})

    assert survivor.delete(f"/api/checkin/contacts/{contact['id']}").status_code == 200
    assert survivor.get("/api/checkin/contacts").json() == []
    # The old invite link is dead for the contact too.
    assert survivor.get(f"/api/checkin/invite/{token}").status_code == 404
    _make_everyone_overdue()
    emails.clear()
    CheckinService().run_due_alerts_once()
    assert emails == []
