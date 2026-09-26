from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.checkin import TrustedContact
from app.models.evidence import EvidenceEntry
from conftest import PASSWORD, register_and_login

BLOB = {"ciphertext": "b3BhcXVl", "iv": "aXYxMjM0NTY3ODkw"}


def test_evidence_requires_login(client):
    assert client.get("/api/evidence/entries").status_code == 401


def test_salt_can_only_be_set_once():
    a = register_and_login("survivor_a")
    assert a.get("/api/evidence/salt").json() == {"salt": None}
    assert a.put("/api/evidence/salt", json={"salt": "c2FsdA"}).status_code == 200
    assert a.put("/api/evidence/salt", json={"salt": "b3RoZXI"}).status_code == 409
    assert a.get("/api/auth/me").json()["evidence_pin_set"] is True


def test_entries_are_invisible_and_untouchable_to_other_users():
    a = register_and_login("survivor_a")
    b = register_and_login("survivor_b")

    entry_id = a.post("/api/evidence/entries", json=BLOB).json()["id"]

    assert b.get("/api/evidence/entries").json() == []
    assert b.put(f"/api/evidence/entries/{entry_id}", json=BLOB).status_code == 404
    assert b.delete(f"/api/evidence/entries/{entry_id}").status_code == 404
    assert len(a.get("/api/evidence/entries").json()) == 1


def test_case_profile_is_per_user():
    a = register_and_login("survivor_a")
    b = register_and_login("survivor_b")
    a.put("/api/evidence/case-profile", json=BLOB)
    assert b.get("/api/evidence/case-profile").json() is None
    assert a.get("/api/evidence/case-profile").json()["ciphertext"] == BLOB["ciphertext"]


def test_account_deletion_removes_everything():
    a = register_and_login("survivor_a")
    a.post("/api/evidence/entries", json=BLOB)
    a.post("/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"})

    assert a.post("/api/auth/delete-account", json={"password": PASSWORD}).status_code == 200

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EvidenceEntry)) == 0
        assert db.scalar(select(func.count()).select_from(TrustedContact)) == 0
