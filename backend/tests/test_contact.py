"""P2-C5: the contact form emails the operator's inbox, stores nothing, and never pretends."""

import logging

import pytest
from sqlalchemy import func, select

from app.core.db import Base, SessionLocal
from app.services import contact as contact_service

SECRET_TEXT = "my partner reads my texts <script>x</script>"


@pytest.fixture
def sent(monkeypatch):
    """Captures what would have gone to Brevo. No real email is ever sent."""
    captured = []
    monkeypatch.setattr(contact_service, "send_email", lambda **kw: captured.append(kw) or True)
    return captured


@pytest.fixture
def inbox_on(settings_env):
    settings_env(CONTACT_INBOX_EMAIL="inbox@example.org", BREVO_API_KEY="test-key", CONTACT_RESPONSE_DAYS="7")


def _post(client, **fields):
    body = {"safe_name": "", "safe_contact": "", "message": SECRET_TEXT, **fields}
    return client.post("/api/contact", json=body)


def test_status_is_off_without_an_inbox(client, settings_env):
    settings_env(CONTACT_INBOX_EMAIL=None, BREVO_API_KEY="test-key")
    assert client.get("/api/contact/status").json() == {"enabled": False, "response_days": 7}


def test_status_is_off_without_an_email_provider(client, settings_env):
    settings_env(CONTACT_INBOX_EMAIL="inbox@example.org", BREVO_API_KEY=None)
    assert client.get("/api/contact/status").json()["enabled"] is False


def test_status_is_on_with_inbox_and_provider(client, inbox_on):
    assert client.get("/api/contact/status").json() == {"enabled": True, "response_days": 7}


def test_without_an_inbox_the_form_refuses_plainly_and_sends_nothing(client, settings_env, sent):
    settings_env(CONTACT_INBOX_EMAIL=None)
    response = _post(client)
    assert response.status_code == 503
    assert "not sent" in response.json()["detail"]
    assert "1-800-799-7233" in response.json()["detail"]
    assert sent == []


def test_a_message_is_sent_once_to_the_inbox(client, inbox_on, sent):
    response = _post(client, safe_name="R", safe_contact="call my work phone")

    assert response.status_code == 200
    assert len(sent) == 1
    email = sent[0]
    assert email["to_email"] == "inbox@example.org"
    assert SECRET_TEXT not in email["subject"]
    assert "my partner reads my texts &lt;script&gt;" in email["html_content"]  # escaped, never raw HTML
    assert "call my work phone" in email["html_content"]
    reply = response.json()["message"]
    assert "within 7 days" in reply
    assert "911" in reply and "88788" in reply


def test_nothing_is_stored(client, inbox_on, sent):
    assert _post(client).status_code == 200
    with SessionLocal() as db:
        for table in Base.metadata.sorted_tables:
            assert db.execute(select(func.count()).select_from(table)).scalar() == 0, table.name


def test_message_text_never_reaches_the_logs(client, inbox_on, sent, caplog):
    with caplog.at_level(logging.DEBUG):
        _post(client, safe_name="Rowan", safe_contact="rowan@example.com")
    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "partner reads" not in logged
    assert "Rowan" not in logged and "rowan@example.com" not in logged


def test_a_failed_send_says_so(client, inbox_on, monkeypatch):
    monkeypatch.setattr(contact_service, "send_email", lambda **kw: False)
    response = _post(client)
    assert response.status_code == 503
    assert "could not be sent" in response.json()["detail"]


def test_empty_and_oversized_messages_are_rejected(client, inbox_on, sent):
    assert _post(client, message="   ").status_code == 400
    assert _post(client, message="x" * 3001).status_code == 413
    assert sent == []


def test_form_encoded_posts_are_refused(client, inbox_on, sent):
    """JSON only, so another site can't submit the form cross-site without a CORS preflight."""
    response = client.post("/api/contact", data={"message": "hello"})
    assert response.status_code == 422
    assert sent == []


def test_response_window_wording():
    assert contact_service.response_window(1) == "within a day"
    assert contact_service.response_window(3) == "within 3 days"
