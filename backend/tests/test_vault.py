"""Encrypted safety plan (P2-E8) and photo attachments (P2-E7).

The server only ever holds ciphertext; these tests check storage, the size
cap, ownership (another account gets 404, never data), and that deleting a
note or an account removes its attachments.
"""

import base64

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.vault import EvidenceAttachment, SafetyPlan
from app.schemas.vault import MAX_ATTACHMENT_CIPHERTEXT_BYTES
from app.services import vault as vault_service
from conftest import PASSWORD, register_and_login

BLOB = {"ciphertext": "b3BhcXVl", "iv": "aXYxMjM0NTY3ODkw"}


def attachment(entry_id: str, size: int = 1024) -> dict:
    return {
        "entry_id": entry_id,
        "ciphertext": base64.b64encode(b"\x8f" * size).decode(),
        "iv": "aXYxMjM0NTY3ODkw",
        "meta_ciphertext": "bWV0YQ",
        "meta_iv": "aXYyMjM0NTY3ODkw",
    }


def count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_vault_routes_require_login(client):
    assert client.get("/api/evidence/safety-plan").status_code == 401
    assert client.get("/api/evidence/attachments").status_code == 401
    nobody = "00000000-0000-0000-0000-000000000000"
    assert client.post("/api/evidence/attachments", json=attachment(nobody)).status_code == 401


def test_safety_plan_round_trips_and_is_per_user():
    a = register_and_login("survivor_a")
    b = register_and_login("survivor_b")
    assert a.get("/api/evidence/safety-plan").json() is None
    assert a.put("/api/evidence/safety-plan", json=BLOB).status_code == 200
    assert a.get("/api/evidence/safety-plan").json()["ciphertext"] == BLOB["ciphertext"]
    a.put("/api/evidence/safety-plan", json={**BLOB, "ciphertext": "bmV3ZXI"})
    assert a.get("/api/evidence/safety-plan").json()["ciphertext"] == "bmV3ZXI"
    assert count(SafetyPlan) == 1
    assert b.get("/api/evidence/safety-plan").json() is None
    assert a.delete("/api/evidence/safety-plan").status_code == 200
    assert a.get("/api/evidence/safety-plan").json() is None


def test_vault_responses_are_never_cached():
    a = register_and_login("survivor_a")
    assert a.get("/api/evidence/safety-plan").headers["cache-control"] == "no-store"
    assert a.get("/api/evidence/attachments").headers["cache-control"] == "no-store"


def test_attachment_round_trip_stores_bytes_and_lists_without_the_image():
    a = register_and_login("survivor_a")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    body = attachment(entry_id, size=3000)
    created = a.post("/api/evidence/attachments", json=body)
    assert created.status_code == 200, created.text
    info = created.json()
    assert info["entry_id"] == entry_id and info["size_bytes"] == 3000
    assert "ciphertext" not in info

    listed = a.get("/api/evidence/attachments", params={"entry_id": entry_id}).json()
    assert [x["id"] for x in listed] == [info["id"]]
    data = a.get(f"/api/evidence/attachments/{info['id']}").json()
    assert data["ciphertext"] == body["ciphertext"] and data["iv"] == body["iv"]

    with SessionLocal() as db:
        stored = db.scalar(select(EvidenceAttachment.ciphertext))
    assert stored == b"\x8f" * 3000  # bytea, not base64 text


def test_attachment_size_cap_is_5_mb():
    a = register_and_login("survivor_a")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    at_cap = a.post("/api/evidence/attachments", json=attachment(entry_id, MAX_ATTACHMENT_CIPHERTEXT_BYTES))
    assert at_cap.status_code == 200
    too_big = a.post("/api/evidence/attachments", json=attachment(entry_id, MAX_ATTACHMENT_CIPHERTEXT_BYTES + 1))
    assert too_big.status_code == 422
    assert count(EvidenceAttachment) == 1


def test_attachment_rejects_non_base64():
    a = register_and_login("survivor_a")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    bad = {**attachment(entry_id), "ciphertext": "not base64!"}
    assert a.post("/api/evidence/attachments", json=bad).status_code == 422


def test_attachments_are_invisible_and_untouchable_to_other_users():
    a = register_and_login("survivor_a")
    b = register_and_login("survivor_b")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    att_id = a.post("/api/evidence/attachments", json=attachment(entry_id)).json()["id"]

    assert b.get("/api/evidence/attachments").json() == []
    assert b.get("/api/evidence/attachments", params={"entry_id": entry_id}).json() == []
    assert b.get(f"/api/evidence/attachments/{att_id}").status_code == 404
    assert b.delete(f"/api/evidence/attachments/{att_id}").status_code == 404
    # Nor can B hang a photo off A's note.
    assert b.post("/api/evidence/attachments", json=attachment(entry_id)).status_code == 404
    assert count(EvidenceAttachment) == 1
    assert a.delete(f"/api/evidence/attachments/{att_id}").status_code == 200
    assert count(EvidenceAttachment) == 0


def test_deleting_a_note_deletes_its_attachments():
    a = register_and_login("survivor_a")
    keep = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    gone = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    a.post("/api/evidence/attachments", json=attachment(keep))
    a.post("/api/evidence/attachments", json=attachment(gone))
    a.post("/api/evidence/attachments", json=attachment(gone))
    assert a.delete(f"/api/evidence/entries/{gone}").status_code == 200
    assert [x["entry_id"] for x in a.get("/api/evidence/attachments").json()] == [keep]


def test_account_deletion_removes_plan_and_attachments():
    a = register_and_login("survivor_a")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    a.post("/api/evidence/attachments", json=attachment(entry_id))
    a.put("/api/evidence/safety-plan", json=BLOB)
    assert a.post("/api/auth/delete-account", json={"password": PASSWORD}).status_code == 200
    assert count(EvidenceAttachment) == 0
    assert count(SafetyPlan) == 0


def test_per_account_photo_limit(monkeypatch):
    monkeypatch.setattr(vault_service, "MAX_ATTACHMENTS_PER_USER", 2)
    a = register_and_login("survivor_a")
    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]
    assert a.post("/api/evidence/attachments", json=attachment(entry_id)).status_code == 200
    assert a.post("/api/evidence/attachments", json=attachment(entry_id)).status_code == 200
    assert a.post("/api/evidence/attachments", json=attachment(entry_id)).status_code == 409
