"""P2-F2: a heartbeat ping after each completed alert pass; never breaks the pass."""

import httpx
import pytest
from sqlalchemy import text

from app.core import notifications
from app.core.db import engine
from app.services.checkin import ALERT_PASS_LOCK_KEY, CheckinService

PING = "https://hc-ping.example/abc-123"


@pytest.fixture
def pings(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(notifications.httpx, "get", fake_get)
    return calls


def test_each_completed_pass_pings(settings_env, pings):
    settings_env(HEALTHCHECK_PING_URL=PING)
    assert CheckinService().run_due_alerts_once() is True
    assert CheckinService().run_due_alerts_once() is True
    assert pings == [PING, PING]


def test_off_when_no_url(settings_env, pings):
    settings_env(HEALTHCHECK_PING_URL=None)
    CheckinService().run_due_alerts_once()
    assert pings == []


def test_a_failing_ping_never_breaks_the_pass(settings_env, monkeypatch):
    settings_env(HEALTHCHECK_PING_URL=PING)

    def down(url, timeout):
        raise httpx.ConnectError("monitor unreachable")

    monkeypatch.setattr(notifications.httpx, "get", down)
    assert CheckinService().run_due_alerts_once() is True

    def server_error(url, timeout):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(notifications.httpx, "get", server_error)
    assert CheckinService().run_due_alerts_once() is True


def test_a_skipped_or_failed_pass_does_not_ping(settings_env, pings, monkeypatch):
    settings_env(HEALTHCHECK_PING_URL=PING)
    with engine.connect() as other_process:
        other_process.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": ALERT_PASS_LOCK_KEY})
        try:
            assert CheckinService().run_due_alerts_once() is False
        finally:
            other_process.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ALERT_PASS_LOCK_KEY})
            other_process.commit()

    def boom(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr(CheckinService, "_run_pass", boom)
    with pytest.raises(RuntimeError):
        CheckinService().run_due_alerts_once()
    assert pings == []
