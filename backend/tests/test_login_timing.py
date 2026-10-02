"""P2-A9: an unknown username costs the same Argon2 work as a wrong password."""

import statistics
import time

import pytest
from fastapi import HTTPException, Response

from app.core.db import SessionLocal
from app.core.login_throttle import login_throttle
from app.schemas.auth import LoginRequest
from app.services import auth as auth_service
from app.services.auth import AuthService
from conftest import PASSWORD, make_client, register


def test_unknown_username_runs_a_dummy_verify(monkeypatch):
    calls = []
    real_verify = auth_service.verify_secret

    def recording_verify(hashed, value):
        calls.append(hashed)
        return real_verify(hashed, value)

    monkeypatch.setattr(auth_service, "verify_secret", recording_verify)
    response = make_client().post("/api/auth/login", json={"username": "nobody_here", "password": PASSWORD})

    assert response.status_code == 401
    assert calls == [auth_service._DUMMY_PASSWORD_HASH]


def _time_login(username: str, password: str) -> float:
    with SessionLocal() as db:
        login_throttle.reset()  # this test is about Argon2 cost, not the guessing slowdown
        start = time.perf_counter()
        with pytest.raises(HTTPException) as exc:
            AuthService().login(db, Response(), LoginRequest(username=username, password=password), "10.0.0.1")
        elapsed = time.perf_counter() - start
    assert exc.value.status_code == 401
    return elapsed


def test_unknown_and_wrong_password_take_comparable_time():
    register(make_client(), "survivor_a")
    unknown = [_time_login("nobody_here", "not the password") for _ in range(20)]
    wrong = [_time_login("survivor_a", "not the password") for _ in range(20)]
    wrong_median, unknown_median = statistics.median(wrong), statistics.median(unknown)
    assert 0.5 < wrong_median / unknown_median < 2.0, f"wrong {wrong_median:.4f}s vs unknown {unknown_median:.4f}s"
