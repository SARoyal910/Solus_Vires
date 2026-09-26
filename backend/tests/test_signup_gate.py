import pytest

from app.core.config import get_settings
from app.services import auth as auth_service
from conftest import PASSWORD


@pytest.fixture
def gate(monkeypatch):
    def configure(open_signups: bool, codes: tuple[str, ...]):
        settings = get_settings()
        patched = settings.__class__(
            **{**settings.__dict__, "beta_signups_open": open_signups, "beta_invite_codes": codes}
        )
        monkeypatch.setattr(auth_service, "get_settings", lambda: patched)

    return configure


def _register(client, **extra):
    return client.post("/api/auth/register", json={"username": "survivor_a", "password": PASSWORD, **extra})


def test_no_code_is_refused_when_invite_only(client, gate):
    gate(False, ("friend-7q2k",))
    response = _register(client)
    assert response.status_code == 403
    assert "invite code" in response.json()["detail"]


def test_wrong_code_is_refused(client, gate):
    gate(False, ("friend-7q2k",))
    assert _register(client, invite_code="friend-0000").status_code == 403


def test_valid_code_creates_the_account(client, gate):
    gate(False, ("friend-7q2k", "advocate-3m9x"))
    assert _register(client, invite_code=" advocate-3m9x ").status_code == 200


def test_no_codes_configured_pauses_signups_with_a_clear_message(client, gate):
    gate(False, ())
    response = _register(client, invite_code="anything")
    assert response.status_code == 403
    assert "paused" in response.json()["detail"]


def test_open_signups_need_no_code(client, gate):
    gate(True, ())
    assert _register(client).status_code == 200


def test_resource_pages_and_login_stay_open_when_gated(client, gate):
    gate(False, ())
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code == 401
