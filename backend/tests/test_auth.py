from conftest import PASSWORD, login, make_client, register


def test_register_returns_ten_single_use_recovery_codes(client):
    codes = register(client, "survivor_a")
    assert len(codes) == 10
    assert len(set(codes)) == 10


def test_duplicate_username_is_rejected(client):
    register(client, "survivor_a")
    response = client.post("/api/auth/register", json={"username": "survivor_a", "password": PASSWORD})
    assert response.status_code == 409


def test_login_sets_httponly_session_cookie_and_me_works(client):
    register(client, "survivor_a")
    response = login(client, "survivor_a")
    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"].lower()
    assert "sv_session=" in cookie_header
    assert "httponly" in cookie_header

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"username": "survivor_a", "evidence_pin_set": False}


def test_wrong_password_and_unknown_user_get_the_same_error(client):
    register(client, "survivor_a")
    wrong = login(client, "survivor_a", "not the password")
    unknown = login(client, "nobody_here")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_logout_ends_the_session(client):
    register(client, "survivor_a")
    login(client, "survivor_a")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_logout_all_ends_every_session():
    first, second = make_client(), make_client()
    register(first, "survivor_a")
    login(first, "survivor_a")
    login(second, "survivor_a")

    assert first.post("/api/auth/logout-all").status_code == 200
    assert second.get("/api/auth/me").status_code == 401


def test_recovery_code_resets_password_once_and_ends_sessions():
    device = make_client()
    codes = register(device, "survivor_a")
    login(device, "survivor_a")

    recovering = make_client()
    body = {"username": "survivor_a", "recovery_code": codes[0], "new_password": "a brand new password"}
    assert recovering.post("/api/auth/recover", json=body).status_code == 200

    assert device.get("/api/auth/me").status_code == 401
    assert login(recovering, "survivor_a").status_code == 401
    assert login(recovering, "survivor_a", "a brand new password").status_code == 200

    reused = recovering.post("/api/auth/recover", json={**body, "new_password": "yet another password"})
    assert reused.status_code == 400


def test_account_lockout_baseline(client):
    """Documents CURRENT behaviour: 8 failures lock the account even for the right password.

    This is engineering finding H5 (an abuser who knows the username can lock the
    survivor out). P2-A5 replaces this test with per-(IP, username) delays.
    """
    register(client, "survivor_a")
    for _ in range(8):
        assert login(client, "survivor_a", "wrong password").status_code == 401
    assert login(client, "survivor_a").status_code == 429


def test_register_is_rate_limited_per_ip(client):
    for i in range(5):
        register(client, f"survivor_{i}")
    response = client.post("/api/auth/register", json={"username": "survivor_x", "password": PASSWORD})
    assert response.status_code == 429


def test_delete_account_requires_password(client):
    register(client, "survivor_a")
    login(client, "survivor_a")
    assert client.post("/api/auth/delete-account", json={"password": "wrong"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 200

    assert client.post("/api/auth/delete-account", json={"password": PASSWORD}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, "survivor_a").status_code == 401
