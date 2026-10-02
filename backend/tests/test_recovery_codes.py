"""P2-A13: recovery codes are a peppered HMAC looked up directly, not ten Argon2 checks."""

import hashlib
import time
import uuid

import pytest
from fastapi import HTTPException, Response

from app.core.db import SessionLocal
from app.core.security import hash_secret, recovery_code_digest
from app.models.auth import RecoveryCode, User
from app.schemas.auth import RecoverRequest
from app.services import auth as auth_service
from app.services.auth import AuthService
from conftest import login, make_client, register

NEW_PASSWORD = "a brand new password"


def _recover(client, code: str, username: str = "survivor_a"):
    body = {"username": username, "recovery_code": code, "new_password": NEW_PASSWORD}
    return client.post("/api/auth/recover", json=body)


def test_new_codes_are_stored_as_peppered_hmac_only():
    codes = register(make_client(), "survivor_a")
    with SessionLocal() as db:
        user = db.query(User).filter_by(username="survivor_a").one()
        rows = db.query(RecoveryCode).filter_by(user_id=user.id).all()
        assert len(rows) == 10
        assert all(row.code_hash is None for row in rows)
        stored = {row.code_sha256 for row in rows}
        assert stored == {recovery_code_digest(user.id, code) for code in codes}
        # Not a bare SHA-256: without the pepper a database dump can't test guesses.
        assert hashlib.sha256(codes[0].encode()).hexdigest() not in stored


def test_digest_depends_on_pepper_and_account(settings_env):
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    first = recovery_code_digest(user_a, "abcde12345-abcde12345")
    assert first != recovery_code_digest(user_b, "abcde12345-abcde12345")
    settings_env(RECOVERY_CODE_PEPPER="a-different-pepper")
    assert first != recovery_code_digest(user_a, "abcde12345-abcde12345")


def test_recovery_with_a_new_code_runs_no_argon2_check(monkeypatch):
    client = make_client()
    codes = register(client, "survivor_a")

    def no_argon2(hashed, value):
        raise AssertionError("a new-style code must not need an Argon2 verify")

    monkeypatch.setattr(auth_service, "verify_secret", no_argon2)
    assert _recover(client, codes[3]).status_code == 200
    assert _recover(client, codes[3]).status_code == 400  # single use
    monkeypatch.undo()
    assert login(client, "survivor_a", NEW_PASSWORD).status_code == 200


def test_typed_codes_tolerate_case_and_spaces():
    client = make_client()
    codes = register(client, "survivor_a")
    assert _recover(client, f"  {codes[0].upper()} ").status_code == 200


def test_codes_issued_before_the_migration_still_work_once():
    client = make_client()
    register(client, "survivor_a")
    legacy_code = "0123456789-abcdefabcd"
    with SessionLocal() as db:
        user = db.query(User).filter_by(username="survivor_a").one()
        db.add(RecoveryCode(user_id=user.id, code_hash=hash_secret(legacy_code)))
        db.commit()

    assert _recover(client, legacy_code).status_code == 200
    assert _recover(client, legacy_code).status_code == 400


def test_a_code_from_another_account_is_rejected():
    client = make_client()
    other_codes = register(client, "survivor_b")
    register(client, "survivor_a")
    assert _recover(client, other_codes[0], username="survivor_a").status_code == 400


def test_wrong_code_costs_little_cpu():
    """DESIGN2: a recovery request completes in under 50 ms of CPU."""
    register(make_client(), "survivor_a")
    with SessionLocal() as db:
        start = time.thread_time()
        with pytest.raises(HTTPException) as exc:
            AuthService().recover(
                db,
                Response(),
                RecoverRequest(username="survivor_a", recovery_code="ffffffffff-ffffffffff", new_password=NEW_PASSWORD),
            )
        cpu = time.thread_time() - start
    assert exc.value.status_code == 400
    assert cpu < 0.05, f"{cpu:.3f}s of CPU"
