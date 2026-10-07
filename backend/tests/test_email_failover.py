"""SCALE.md Stage 1 item 2: a second email provider, and the history says who carried each alert."""

import uuid

import httpx
from test_checkin import _make_everyone_overdue

from app.core import notifications
from app.services import checkin as checkin_service
from app.services.checkin import CheckinService, make_contact_token
from conftest import register_and_login

BREVO = "https://api.brevo.com/v3/smtp/email"
POSTMARK = "https://api.postmarkapp.com/email"


def _fake_post(monkeypatch, statuses: dict[str, int | Exception]):
    """Each provider URL answers with the given status, or raises the given exception."""
    calls: list[tuple[str, dict]] = []

    def fake(url, headers, json, timeout):
        calls.append((url, json))
        outcome = statuses[url]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, request=httpx.Request("POST", url))

    monkeypatch.setattr(notifications.httpx, "post", fake)
    return calls


def _send():
    return notifications.send_email(
        to_email="jo@example.com", to_name="Jo", subject="Alert", html_content="<p>hi</p>"
    )


def test_brevo_alone_when_it_works(settings_env, monkeypatch):
    settings_env(BREVO_API_KEY="b", POSTMARK_SERVER_TOKEN="p")
    calls = _fake_post(monkeypatch, {BREVO: 201, POSTMARK: 200})
    assert _send() == "brevo"
    assert [url for url, _ in calls] == [BREVO]


def test_quota_or_error_at_brevo_fails_over_to_postmark(settings_env, monkeypatch):
    settings_env(BREVO_API_KEY="b", POSTMARK_SERVER_TOKEN="p")
    for brevo_outcome in (429, 402, 500, httpx.ConnectError("down"), httpx.ReadTimeout("slow")):
        calls = _fake_post(monkeypatch, {BREVO: brevo_outcome, POSTMARK: 200})
        assert _send() == "postmark", brevo_outcome
        assert [url for url, _ in calls] == [BREVO, POSTMARK]


def test_postmark_gets_a_verified_sender_and_the_stream(settings_env, monkeypatch):
    settings_env(
        BREVO_API_KEY="b",
        BREVO_SENDER_EMAIL="alerts@solusvires.example",
        BREVO_SENDER_NAME="Solus Vires",
        POSTMARK_SERVER_TOKEN="p",
        POSTMARK_SENDER_EMAIL=None,
    )
    calls = _fake_post(monkeypatch, {BREVO: 500, POSTMARK: 200})
    _send()
    body = calls[1][1]
    assert body["From"] == "Solus Vires <alerts@solusvires.example>"
    assert body["To"] == "Jo <jo@example.com>"
    assert body["MessageStream"] == "outbound"

    settings_env(POSTMARK_SENDER_EMAIL="verified@other.example")
    calls = _fake_post(monkeypatch, {BREVO: 500, POSTMARK: 200})
    _send()
    assert calls[1][1]["From"] == "Solus Vires <verified@other.example>"


def test_both_down_is_a_failure_not_an_exception(settings_env, monkeypatch):
    settings_env(BREVO_API_KEY="b", POSTMARK_SERVER_TOKEN="p")
    _fake_post(monkeypatch, {BREVO: 500, POSTMARK: httpx.ConnectError("down")})
    assert _send() == ""


def test_only_the_configured_providers_are_tried(settings_env, monkeypatch):
    settings_env(BREVO_API_KEY=None, POSTMARK_SERVER_TOKEN="p")
    calls = _fake_post(monkeypatch, {BREVO: 500, POSTMARK: 200})
    assert _send() == "postmark"
    assert [url for url, _ in calls] == [POSTMARK]

    settings_env(BREVO_API_KEY="b", POSTMARK_SERVER_TOKEN=None)
    calls = _fake_post(monkeypatch, {BREVO: 500, POSTMARK: 200})
    assert _send() == ""
    assert [url for url, _ in calls] == [BREVO]

    settings_env(BREVO_API_KEY=None, POSTMARK_SERVER_TOKEN=None)
    calls = _fake_post(monkeypatch, {BREVO: 200, POSTMARK: 200})
    assert notifications.email_configured() is False
    assert _send() == ""
    assert calls == []


def test_alert_history_counts_emails_the_fallback_carried(monkeypatch):
    survivor = register_and_login("survivor_failover")
    for name in ("Jo", "Sam"):
        contact = survivor.post(
            "/api/checkin/contacts", json={"nickname": name, "contact_email": f"{name.lower()}@example.com"}
        ).json()
        survivor.post(f"/api/checkin/invite/{make_contact_token(uuid.UUID(contact['id']))}/accept")
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()

    carried = iter(["brevo", "postmark"])
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: next(carried))
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: True)
    assert CheckinService().run_due_alerts_once() is True

    entries = survivor.get("/api/checkin/alerts").json()
    assert len(entries) == 1
    assert entries[0]["emails_sent"] == 2
    assert entries[0]["emails_via_fallback"] == 1
