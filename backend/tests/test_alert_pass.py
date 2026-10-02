"""P2-A8: only one alert pass at a time, and the loop only where it's wanted."""

import asyncio
import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from test_checkin import _make_everyone_overdue

from app.core.config import get_settings
from app.core.db import engine
from app.main import app
from app.services import checkin as checkin_service
from app.services.checkin import ALERT_PASS_LOCK_KEY, CheckinService, make_contact_token
from conftest import register_and_login


def _overdue_survivor_with_contact(name: str = "survivor_a"):
    survivor = register_and_login(name)
    contact = survivor.post(
        "/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"}
    ).json()
    survivor.post(f"/api/checkin/invite/{make_contact_token(uuid.UUID(contact['id']))}/accept")
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    _make_everyone_overdue()
    return survivor


def test_pass_is_skipped_while_another_process_holds_the_lock(monkeypatch):
    _overdue_survivor_with_contact()
    emails = []
    monkeypatch.setattr(checkin_service, "send_email", lambda **kw: emails.append(kw))

    with engine.connect() as other_process:
        assert other_process.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": ALERT_PASS_LOCK_KEY}).scalar()
        try:
            assert CheckinService().run_due_alerts_once() is False
            assert emails == []
        finally:
            other_process.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ALERT_PASS_LOCK_KEY})
            other_process.commit()

    assert CheckinService().run_due_alerts_once() is True
    assert len(emails) == 1


def test_two_concurrent_passes_send_one_alert(monkeypatch):
    """Without the lock, the second pass would see no alert recorded yet and send again."""
    in_first_pass = threading.Event()
    let_first_pass_finish = threading.Event()
    emails = []

    def slow_send_email(**kw):
        emails.append(kw)
        in_first_pass.set()
        assert let_first_pass_finish.wait(timeout=10)

    _overdue_survivor_with_contact()
    monkeypatch.setattr(checkin_service, "send_email", slow_send_email)
    monkeypatch.setattr(checkin_service, "send_push", lambda sub, **kw: None)

    results = {}
    first = threading.Thread(target=lambda: results.setdefault("first", CheckinService().run_due_alerts_once()))
    first.start()
    try:
        assert in_first_pass.wait(timeout=10)
        results["second"] = CheckinService().run_due_alerts_once()
    finally:
        let_first_pass_finish.set()
        first.join(timeout=10)

    assert results == {"first": True, "second": False}
    assert len(emails) == 1


def test_lock_is_released_after_a_pass_that_raises(monkeypatch):
    def boom(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr(CheckinService, "_run_pass", boom)
    try:
        CheckinService().run_due_alerts_once()
    except RuntimeError:
        pass
    monkeypatch.undo()
    assert CheckinService().run_due_alerts_once() is True


def test_loop_flag_defaults_on_only_in_production(settings_env):
    settings_env(APP_ENV="production", CHECKIN_ALERT_LOOP_ENABLED=None)
    assert get_settings().checkin_alert_loop_enabled is True
    settings_env(APP_ENV="development")
    assert get_settings().checkin_alert_loop_enabled is False
    settings_env(CHECKIN_ALERT_LOOP_ENABLED="true")
    assert get_settings().checkin_alert_loop_enabled is True
    settings_env(APP_ENV="production", CHECKIN_ALERT_LOOP_ENABLED="false")
    assert get_settings().checkin_alert_loop_enabled is False


def _loop_starts(monkeypatch) -> bool:
    started = []

    async def fake_loop(self):
        started.append(True)

    monkeypatch.setattr(CheckinService, "run_alert_loop", fake_loop)
    with TestClient(app) as client:
        client.get("/api/health")
    return bool(started)


def test_lifespan_starts_the_loop_only_when_enabled(monkeypatch, settings_env):
    settings_env(CHECKIN_ALERT_LOOP_ENABLED="false")
    assert _loop_starts(monkeypatch) is False
    settings_env(CHECKIN_ALERT_LOOP_ENABLED="true")
    assert _loop_starts(monkeypatch) is True


def test_loop_keeps_running_after_a_failed_pass(monkeypatch, settings_env):
    settings_env(CHECKIN_ALERT_CHECK_SECONDS="0")
    calls = []

    def flaky_pass(self):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database went away")
        return True

    monkeypatch.setattr(CheckinService, "run_due_alerts_once", flaky_pass)

    async def run_briefly():
        task = asyncio.create_task(CheckinService().run_alert_loop())
        for _ in range(200):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()

    asyncio.run(run_briefly())
    assert len(calls) >= 2
