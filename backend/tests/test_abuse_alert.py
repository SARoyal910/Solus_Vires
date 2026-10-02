"""P2-F3: one email to the operator when one address keeps hitting rate limits."""

import time

import pytest

from app.core import abuse_alert
from app.core.abuse_alert import MAX_ALERTS_PER_DAY, abuse_monitor


@pytest.fixture
def operator_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(abuse_alert, "send_email", lambda **kw: sent.append(kw) or True)
    return sent


def _wait_for(sent, n, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and len(sent) < n:
        time.sleep(0.02)
    return sent


def test_repeated_429s_from_one_address_send_one_email(client, trust_proxy, settings_env, operator_mail):
    settings_env(OPERATOR_ALERT_EMAIL="operator@example.org", ABUSE_ALERT_THRESHOLD="3")
    headers = {"X-Real-IP": "203.0.113.9"}
    statuses = [client.post("/api/contact", json={"message": "x"}, headers=headers).status_code for _ in range(12)]
    assert statuses.count(429) == 7  # the contact limit allows 5 per 10 minutes

    _wait_for(operator_mail, 1)
    time.sleep(0.2)  # give any (wrong) second alert time to show up
    assert len(operator_mail) == 1
    email = operator_mail[0]
    assert email["to_email"] == "operator@example.org"
    assert "/api/contact" in email["html_content"]
    assert "203.0.113.9" not in email["html_content"] + email["subject"]  # no IP history, even in email


def test_below_the_threshold_nothing_is_sent(settings_env, operator_mail):
    settings_env(OPERATOR_ALERT_EMAIL="operator@example.org", ABUSE_ALERT_THRESHOLD="50")
    for _ in range(49):
        assert abuse_monitor.record_429("198.51.100.1", "/api/auth/login") is None


def test_off_when_no_operator_address(settings_env):
    settings_env(OPERATOR_ALERT_EMAIL=None, ABUSE_ALERT_THRESHOLD="1")
    assert abuse_monitor.record_429("198.51.100.1", "/api/auth/login") is None


def test_each_address_alerts_once_and_the_daily_total_is_capped(settings_env):
    settings_env(OPERATOR_ALERT_EMAIL="operator@example.org", ABUSE_ALERT_THRESHOLD="2")
    alerts = 0
    for n in range(MAX_ALERTS_PER_DAY + 3):
        ip = f"198.51.100.{n}"
        for _ in range(5):
            if abuse_monitor.record_429(ip, "/api/auth/login") is not None:
                alerts += 1
    assert alerts == MAX_ALERTS_PER_DAY


def test_hits_older_than_an_hour_do_not_count(settings_env, monkeypatch):
    settings_env(OPERATOR_ALERT_EMAIL="operator@example.org", ABUSE_ALERT_THRESHOLD="3")
    clock = [1000.0]
    monkeypatch.setattr(abuse_alert, "_now", lambda: clock[0])
    abuse_monitor.record_429("198.51.100.7", "/api/auth/login")
    abuse_monitor.record_429("198.51.100.7", "/api/auth/login")
    clock[0] += 3601
    assert abuse_monitor.record_429("198.51.100.7", "/api/auth/login") is None
