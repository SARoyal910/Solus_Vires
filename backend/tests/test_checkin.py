import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.checkin import CheckinSchedule
from app.services.checkin import CheckinService, _parse_contact_token, make_contact_token
from conftest import register_and_login


def test_contact_token_round_trips():
    contact_id = uuid.uuid4()
    assert _parse_contact_token(make_contact_token(contact_id)) == contact_id


@pytest.mark.parametrize(
    "mangle",
    [
        lambda t: t[:-1] + ("0" if t[-1] != "0" else "1"),  # flipped signature
        lambda t: f"{uuid.uuid4()}.{t.rsplit('.', 1)[1]}",  # signature from another contact
        lambda t: t.split(".")[0],  # no signature
        lambda t: "not-a-token",
    ],
)
def test_tampered_contact_tokens_are_rejected(mangle):
    token = make_contact_token(uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        _parse_contact_token(mangle(token))
    assert exc.value.status_code == 404


def _schedule(active=True, deadline_offset_hours=0.0, grace_hours=6):
    now = datetime.now(timezone.utc)
    return CheckinSchedule(
        active=active,
        interval_hours=24,
        grace_hours=grace_hours,
        next_deadline_at=now + timedelta(hours=deadline_offset_hours),
    )


def test_not_overdue_before_deadline():
    assert not CheckinService.is_overdue(_schedule(deadline_offset_hours=1))


def test_not_overdue_inside_grace_period():
    assert not CheckinService.is_overdue(_schedule(deadline_offset_hours=-5, grace_hours=6))


def test_overdue_after_grace_period():
    assert CheckinService.is_overdue(_schedule(deadline_offset_hours=-7, grace_hours=6))


def test_inactive_schedule_is_never_overdue():
    assert not CheckinService.is_overdue(_schedule(active=False, deadline_offset_hours=-100))


def test_invite_link_flow():
    survivor = register_and_login("survivor_a")
    contact = survivor.post(
        "/api/checkin/contacts", json={"nickname": "Jo", "contact_email": "jo@example.com"}
    ).json()
    assert contact["status"] == "pending"

    token = make_contact_token(uuid.UUID(contact["id"]))
    info = survivor.get(f"/api/checkin/invite/{token}").json()
    assert info["survivor_username"] == "survivor_a"

    assert survivor.post(f"/api/checkin/invite/{token}/accept").status_code == 200
    assert survivor.get("/api/checkin/contacts").json()[0]["status"] == "accepted"


def test_checkin_moves_the_deadline_forward():
    survivor = register_and_login("survivor_a")
    survivor.put("/api/checkin/schedule", json={"active": True, "interval_hours": 24, "grace_hours": 6})
    first = survivor.get("/api/checkin/schedule").json()["next_deadline_at"]
    after = survivor.post("/api/checkin/schedule/checkin").json()["next_deadline_at"]
    assert after >= first
