"""Phase 3 Sprint 3: ciphertext attestation (P3-H1), what the export can verify (P3-H2), retention (P3-H4)."""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from app.core import attestation
from app.core.db import engine
from app.services.checkin import CheckinService
from conftest import register_and_login

SEED = base64.urlsafe_b64encode(b"\x42" * 32).decode()
BLOB = {"ciphertext": "b3BhcXVl", "iv": "aXYxMjM0NTY3ODkw"}
KEY_CHECK = {"ciphertext": "a2V5Y2hlY2s", "iv": "aXYzMjM0NTY3ODkw"}


def _on(settings_env):
    settings_env(ATTESTATION_PRIVATE_KEY=SEED)
    attestation._private_key.cache_clear()


# ---------- P3-H1 ----------


def test_every_save_is_attested_and_verifies_against_the_published_key(settings_env):
    _on(settings_env)
    c = register_and_login("attested")
    key = c.get("/api/evidence/attestation-key").json()
    assert key["enabled"] and key["algorithm"] == "Ed25519" and len(base64.b64decode(key["public_key"])) == 32

    entry = c.post("/api/evidence/entries", json=BLOB).json()
    c.put("/api/evidence/case-profile", json=BLOB)
    c.put("/api/evidence/safety-plan", json=BLOB)
    photo = c.post(
        "/api/evidence/attachments",
        json={"entry_id": entry["id"], "ciphertext": base64.b64encode(b"\x01" * 50).decode(), "iv": BLOB["iv"],
              "meta_ciphertext": "bWV0YQ", "meta_iv": BLOB["iv"]},
    ).json()

    rows = c.get("/api/evidence/attestations").json()
    assert sorted(r["kind"] for r in rows) == ["attachment", "entry", "plan", "profile"]
    assert all(r["reason"] == "saved" and r["supersedes"] is None and r["key_id"] == key["key_id"] for r in rows)
    by_kind = {r["kind"]: r for r in rows}
    assert by_kind["entry"]["ciphertext_sha256"] == hashlib.sha256(BLOB["ciphertext"].encode()).hexdigest()
    assert by_kind["attachment"]["ciphertext_sha256"] == hashlib.sha256(b"\x01" * 50).hexdigest()
    assert by_kind["attachment"]["item_id"] == photo["id"]
    for r in rows:
        at = datetime.fromisoformat(r["attested_at"].replace("Z", "+00:00"))
        assert attestation.verify(
            key["public_key"], r["kind"], r["item_id"], r["ciphertext_sha256"], at, r["signature"]
        )
        # Any change to the statement breaks the signature.
        assert not attestation.verify(key["public_key"], r["kind"], r["item_id"], "0" * 64, at, r["signature"])
        assert not attestation.verify(
            key["public_key"], r["kind"], r["item_id"], r["ciphertext_sha256"],
            at + timedelta(seconds=1), r["signature"],
        )


def test_edits_and_pin_changes_chain_to_the_first_attestation(settings_env):
    _on(settings_env)
    c = register_and_login("chained")
    c.put("/api/evidence/salt", json={"salt": "c2FsdA", "key_check": KEY_CHECK})
    entry = c.post("/api/evidence/entries", json=BLOB).json()
    c.put(f"/api/evidence/entries/{entry['id']}", json={**BLOB, "ciphertext": "ZWRpdGVk"})
    rekey_id = uuid.uuid4()
    r = c.post(
        "/api/evidence/rekey",
        json={"rekey_id": str(rekey_id), "salt": "bmV3", "key_check": KEY_CHECK,
              "entries": [{"id": entry["id"], "ciphertext": "cmVrZXllZA", "iv": BLOB["iv"]}], "attachments": []},
    )
    assert r.status_code == 200, r.text
    rows = [r for r in c.get("/api/evidence/attestations").json() if r["kind"] == "entry"]
    assert [r["reason"] for r in rows] == ["saved", "edited", "rekeyed"]
    assert rows[1]["supersedes"] == rows[0]["id"] and rows[2]["supersedes"] == rows[1]["id"]
    assert rows[2]["ciphertext_sha256"] == hashlib.sha256(b"cmVrZXllZA").hexdigest()
    assert rows[0]["attested_at"] <= rows[1]["attested_at"] <= rows[2]["attested_at"]


def test_attestations_are_per_account_and_off_without_a_key(settings_env):
    settings_env(ATTESTATION_PRIVATE_KEY=None)
    attestation._private_key.cache_clear()
    a = register_and_login("survivor_a")
    assert a.get("/api/evidence/attestation-key").json() == {
        "enabled": False, "key_id": None, "public_key": None, "algorithm": "Ed25519",
        "message_format": "solusvires-attest-v1|<kind>|<item id>|<sha256 hex of ciphertext>|<attested_at ISO 8601>",
    }
    a.post("/api/evidence/entries", json=BLOB)
    assert a.get("/api/evidence/attestations").json() == []
    _on(settings_env)
    a.post("/api/evidence/entries", json=BLOB)
    b = register_and_login("survivor_b")
    b.post("/api/evidence/entries", json=BLOB)
    assert len(a.get("/api/evidence/attestations").json()) == 1
    assert len(b.get("/api/evidence/attestations").json()) == 1
    assert a.get("/api/evidence/attestations").headers["cache-control"] == "no-store"


def test_attestation_rows_hold_hashes_only_and_die_with_the_account(settings_env):
    _on(settings_env)
    c = register_and_login("hashed")
    c.post("/api/evidence/entries", json={"ciphertext": "c2VjcmV0", "iv": BLOB["iv"]})
    with engine.connect() as conn:
        dump = str(conn.execute(text("SELECT * FROM evidence_attestations")).fetchall())
    assert "c2VjcmV0" not in dump
    c.post("/api/auth/delete-account", json={"password": "correct horse battery"})
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM evidence_attestations")).scalar() == 0


# ---------- P3-H4 ----------


def test_retention_is_off_by_default_and_spares_active_schedules(settings_env):
    settings_env(INACTIVE_ACCOUNT_RETENTION_DAYS=None)
    old = register_and_login("old_user")
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET last_login_at = now() - interval '400 days'"))
    CheckinService()._run_maintenance()
    assert old.get("/api/auth/me").status_code == 200

    settings_env(INACTIVE_ACCOUNT_RETENTION_DAYS="365")
    watched = register_and_login("watched_user")
    watched.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    fresh = register_and_login("fresh_user")
    never = register_and_login("never_user")
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE users SET last_login_at = now() - interval '400 days' "
            "WHERE username IN ('old_user', 'watched_user')"
        ))
        conn.execute(text(
            "UPDATE users SET last_login_at = NULL, created_at = now() - interval '400 days' "
            "WHERE username = 'never_user'"
        ))
    CheckinService()._run_maintenance()
    with engine.connect() as conn:
        left = sorted(r[0] for r in conn.execute(text("SELECT username FROM users")))
    assert left == ["fresh_user", "watched_user"]
    assert fresh.get("/api/auth/me").status_code == 200
    assert never.get("/api/auth/me").status_code == 401
