"""P3-J2: changing the Notes PIN re-encrypts the whole vault, all or nothing."""

import base64
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.vault import EvidenceAttachment
from app.services.checkin import CheckinService
from conftest import register_and_login

OLD = {"ciphertext": "b2xk", "iv": "aXYxMjM0NTY3ODkw"}
NEW_IV = "aXYyMjM0NTY3ODkw"
KEY_CHECK = {"ciphertext": "a2V5Y2hlY2s", "iv": "aXYzMjM0NTY3ODkw"}


def _vault(name="survivor_a", photos=2):
    """An account with a PIN, two notes, a profile, a plan and `photos` attachments on the first note."""
    c = register_and_login(name)
    assert c.put("/api/evidence/salt", json={"salt": "c2FsdA", "key_check": KEY_CHECK}).status_code == 200
    e1 = c.post("/api/evidence/entries", json=OLD).json()["id"]
    e2 = c.post("/api/evidence/entries", json=OLD).json()["id"]
    c.put("/api/evidence/case-profile", json=OLD)
    c.put("/api/evidence/safety-plan", json=OLD)
    ids = []
    for i in range(photos):
        ids.append(
            c.post(
                "/api/evidence/attachments",
                json={
                    "entry_id": e1,
                    "ciphertext": base64.b64encode(bytes([i]) * 64).decode(),
                    "iv": OLD["iv"],
                    "meta_ciphertext": "bWV0YQ",
                    "meta_iv": OLD["iv"],
                },
            ).json()["id"]
        )
    return c, [e1, e2], ids


def _new(label: str) -> dict:
    return {"ciphertext": base64.b64encode(f"new-{label}".encode()).decode(), "iv": NEW_IV}


def _request(entries, attachments, rekey_id, **overrides) -> dict:
    body = {
        "rekey_id": str(rekey_id),
        "salt": "bmV3c2FsdA",
        "key_check": {"ciphertext": "bmV3Y2hlY2s", "iv": NEW_IV},
        "profile": _new("profile"),
        "plan": _new("plan"),
        "entries": [{"id": e, **_new(f"entry-{e}")} for e in entries],
        "attachments": [{"id": a, "meta_ciphertext": "bmV3bWV0YQ", "meta_iv": NEW_IV} for a in attachments],
    }
    body.update(overrides)
    return body


def _stage(c, attachments, rekey_id):
    for a in attachments:
        r = c.post(
            f"/api/evidence/attachments/{a}/rekey",
            json={"rekey_id": str(rekey_id), "ciphertext": base64.b64encode(b"\x99" * 80).decode(), "iv": NEW_IV},
        )
        assert r.status_code == 200, r.text


def test_rekey_swaps_everything_at_once():
    c, entries, attachments = _vault()
    rekey_id = uuid.uuid4()
    _stage(c, attachments, rekey_id)
    r = c.post("/api/evidence/rekey", json=_request(entries, attachments, rekey_id))
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "entries": 2, "attachments": 2}

    salt = c.get("/api/evidence/salt").json()
    assert salt["salt"] == "bmV3c2FsdA" and salt["key_check"]["ciphertext"] == "bmV3Y2hlY2s"
    for entry in c.get("/api/evidence/entries").json():
        assert entry["ciphertext"] == _new(f"entry-{entry['id']}")["ciphertext"]
    assert c.get("/api/evidence/case-profile").json()["ciphertext"] == _new("profile")["ciphertext"]
    assert c.get("/api/evidence/safety-plan").json()["ciphertext"] == _new("plan")["ciphertext"]
    for a in attachments:
        data = c.get(f"/api/evidence/attachments/{a}").json()
        assert base64.b64decode(data["ciphertext"]) == b"\x99" * 80 and data["iv"] == NEW_IV
    infos = c.get("/api/evidence/attachments").json()
    assert all(i["meta_ciphertext"] == "bmV3bWV0YQ" and i["size_bytes"] == 80 for i in infos)
    with SessionLocal() as db:
        rows = db.scalars(select(EvidenceAttachment)).all()
        assert all(a.pending_ciphertext is None and a.pending_rekey_id is None for a in rows)


def test_nothing_changes_when_a_photo_was_not_staged():
    c, entries, attachments = _vault()
    rekey_id = uuid.uuid4()
    _stage(c, attachments[:1], rekey_id)  # one of two
    r = c.post("/api/evidence/rekey", json=_request(entries, attachments, rekey_id))
    assert r.status_code == 409
    assert "Nothing was changed" in r.json()["detail"]
    assert c.get("/api/evidence/salt").json()["salt"] == "c2FsdA"
    assert all(e["ciphertext"] == OLD["ciphertext"] for e in c.get("/api/evidence/entries").json())
    assert c.get("/api/evidence/safety-plan").json()["ciphertext"] == OLD["ciphertext"]


def test_a_photo_staged_for_a_different_change_does_not_count():
    c, entries, attachments = _vault(photos=1)
    _stage(c, attachments, uuid.uuid4())
    r = c.post("/api/evidence/rekey", json=_request(entries, attachments, uuid.uuid4()))
    assert r.status_code == 409


def test_the_request_must_cover_exactly_the_current_vault():
    c, entries, attachments = _vault(photos=0)
    rekey_id = uuid.uuid4()
    # A note missing.
    assert c.post("/api/evidence/rekey", json=_request(entries[:1], [], rekey_id)).status_code == 409
    # A note that isn't ours.
    other = register_and_login("survivor_b")
    other.put("/api/evidence/salt", json={"salt": "c2FsdA", "key_check": KEY_CHECK})
    foreign = other.post("/api/evidence/entries", json=OLD).json()["id"]
    assert c.post("/api/evidence/rekey", json=_request(entries + [foreign], [], rekey_id)).status_code == 409
    # A note added from another device after the client read the list.
    late = c.post("/api/evidence/entries", json=OLD).json()["id"]
    assert c.post("/api/evidence/rekey", json=_request(entries, [], rekey_id)).status_code == 409
    # Plan present on the server, absent in the request.
    assert c.post("/api/evidence/rekey", json=_request(entries + [late], [], rekey_id, plan=None)).status_code == 409
    # Everything matches: succeeds.
    assert c.post("/api/evidence/rekey", json=_request(entries + [late], [], rekey_id)).status_code == 200
    # The other account was never touched.
    assert other.get("/api/evidence/salt").json()["salt"] == "c2FsdA"


def test_staging_requires_ownership_and_is_swept_when_abandoned():
    c, entries, attachments = _vault(photos=1)
    other = register_and_login("survivor_b")
    r = other.post(
        f"/api/evidence/attachments/{attachments[0]}/rekey",
        json={"rekey_id": str(uuid.uuid4()), "ciphertext": "AAAA", "iv": NEW_IV},
    )
    assert r.status_code == 404
    _stage(c, attachments, uuid.uuid4())
    with SessionLocal() as db:
        assert db.scalars(select(EvidenceAttachment)).first().pending_rekey_id is not None
    CheckinService()._run_maintenance()
    with SessionLocal() as db:
        row = db.scalars(select(EvidenceAttachment)).first()
        assert row.pending_rekey_id is None and row.pending_ciphertext is None
        assert row.ciphertext == bytes([0]) * 64  # the live photo is untouched


def test_rekey_needs_a_pin_first():
    c = register_and_login("no_pin")
    body = _request([], [], uuid.uuid4(), profile=None, plan=None)
    assert c.post("/api/evidence/rekey", json=body).status_code == 409
