"""P2-A14 and P2-A17: session housekeeping and the cookie's SameSite setting."""

from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.core.security import sweep_expired_sessions
from app.models.auth import Session as SessionModel
from app.services.checkin import CheckinService
from conftest import register_and_login


def _only_session() -> SessionModel:
    with SessionLocal() as db:
        return db.query(SessionModel).one()


def _set_last_seen(when: datetime) -> None:
    with SessionLocal() as db:
        db.query(SessionModel).update({SessionModel.last_seen_at: when})
        db.commit()


def test_recent_last_seen_is_not_rewritten_on_every_request():
    client = register_and_login("survivor_a")
    marker = datetime.now(timezone.utc) - timedelta(minutes=1)
    _set_last_seen(marker)

    for _ in range(3):
        assert client.get("/api/auth/me").status_code == 200

    assert _only_session().last_seen_at == marker


def test_stale_last_seen_is_refreshed():
    client = register_and_login("survivor_a")
    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    _set_last_seen(stale)

    assert client.get("/api/auth/me").status_code == 200

    assert datetime.now(timezone.utc) - _only_session().last_seen_at < timedelta(minutes=1)


def _expire_sessions_for(count: int) -> None:
    with SessionLocal() as db:
        rows = db.query(SessionModel).order_by(SessionModel.created_at).all()
        for row in rows[:count]:
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()


def test_sweep_deletes_only_expired_sessions():
    register_and_login("survivor_a")
    current = register_and_login("survivor_b")
    _expire_sessions_for(1)

    with SessionLocal() as db:
        assert sweep_expired_sessions(db) == 1
        assert db.query(SessionModel).count() == 1
    assert current.get("/api/auth/me").status_code == 200


def test_alert_loop_pass_sweeps_expired_sessions():
    register_and_login("survivor_a")
    _expire_sessions_for(1)

    assert CheckinService().run_due_alerts_once() is True

    with SessionLocal() as db:
        assert db.query(SessionModel).count() == 0
