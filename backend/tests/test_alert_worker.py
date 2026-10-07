"""SCALE.md Stage 1 item 5: the alert loop as its own process."""

import asyncio
import os
import time

from app import alert_worker
from app.services.checkin import CheckinService


def _run_until(service, heartbeat, done, timeout=5.0):
    async def go():
        stop = asyncio.Event()
        task = asyncio.create_task(alert_worker.run_loop(service, heartbeat, stop=stop))
        deadline = time.monotonic() + timeout
        while not done() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        stop.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(go())


def test_heartbeat_is_touched_at_start_and_after_every_pass(tmp_path, settings_env, monkeypatch):
    settings_env(CHECKIN_ALERT_CHECK_SECONDS="0")
    heartbeat = tmp_path / "hb"
    passes = []
    monkeypatch.setattr(CheckinService, "run_due_alerts_once", lambda self: passes.append(1) or True)
    mtimes = []

    original_touch = alert_worker._touch

    def recording_touch(path):
        original_touch(path)
        mtimes.append(os.stat(path).st_mtime_ns)

    monkeypatch.setattr(alert_worker, "_touch", recording_touch)
    _run_until(CheckinService(), heartbeat, lambda: len(passes) >= 3)
    assert heartbeat.exists()
    assert len(passes) >= 3
    assert len(mtimes) >= 4  # start, then one per pass


def test_a_skipped_pass_still_counts_as_alive(tmp_path, settings_env, monkeypatch):
    """Another process holding the lock means the loop is fine; only a stuck loop is unhealthy."""
    settings_env(CHECKIN_ALERT_CHECK_SECONDS="0")
    heartbeat = tmp_path / "hb"
    touched = []
    monkeypatch.setattr(CheckinService, "run_due_alerts_once", lambda self: False)
    monkeypatch.setattr(alert_worker, "_touch", lambda path: touched.append(path))
    _run_until(CheckinService(), heartbeat, lambda: len(touched) >= 3)
    assert len(touched) >= 3


def test_loop_keeps_running_after_a_failed_pass(tmp_path, settings_env, monkeypatch):
    settings_env(CHECKIN_ALERT_CHECK_SECONDS="0")
    calls = []

    def flaky(self):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database went away")
        return True

    monkeypatch.setattr(CheckinService, "run_due_alerts_once", flaky)
    _run_until(CheckinService(), tmp_path / "hb", lambda: len(calls) >= 2)
    assert len(calls) >= 2


def test_stop_ends_the_loop_promptly_even_with_a_long_interval(tmp_path, settings_env, monkeypatch):
    settings_env(CHECKIN_ALERT_CHECK_SECONDS="3600")
    monkeypatch.setattr(CheckinService, "run_due_alerts_once", lambda self: True)

    async def go():
        stop = asyncio.Event()
        task = asyncio.create_task(alert_worker.run_loop(CheckinService(), tmp_path / "hb", stop=stop))
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(go())


def test_refuses_an_unsafe_production_configuration(settings_env, monkeypatch):
    settings_env(APP_ENV="production", CHECKIN_TOKEN_SECRET="replace-with-a-real-secret")
    monkeypatch.setattr(alert_worker.asyncio, "run", lambda coro: coro.close())
    assert alert_worker.main() == 1


def test_heartbeat_file_defaults_and_is_overridable(settings_env):
    settings_env(ALERT_WORKER_HEARTBEAT_FILE=None)
    assert str(alert_worker.heartbeat_file()) == alert_worker.DEFAULT_HEARTBEAT_FILE
    settings_env(ALERT_WORKER_HEARTBEAT_FILE="/tmp/elsewhere")
    assert str(alert_worker.heartbeat_file()) == "/tmp/elsewhere"
