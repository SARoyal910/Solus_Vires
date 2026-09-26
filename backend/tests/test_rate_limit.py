from starlette.requests import Request

from app.core import rate_limit
from app.core.config import get_settings


def _request(headers: dict[str, str], client_host: str = "10.0.0.5") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 1234),
    }
    return Request(scope)


def _with_trust(monkeypatch, trusted: bool) -> None:
    settings = get_settings()
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings.__class__(
        **{**settings.__dict__, "trust_proxy_headers": trusted}
    ))


def test_spoofed_real_ip_is_ignored_without_trusted_proxy(monkeypatch):
    _with_trust(monkeypatch, False)
    assert rate_limit.client_ip(_request({"X-Real-IP": "1.2.3.4"})) == "10.0.0.5"


def test_real_ip_is_used_behind_trusted_proxy(monkeypatch):
    _with_trust(monkeypatch, True)
    assert rate_limit.client_ip(_request({"X-Real-IP": "1.2.3.4"})) == "1.2.3.4"


def test_falls_back_to_socket_address_when_header_absent(monkeypatch):
    _with_trust(monkeypatch, True)
    assert rate_limit.client_ip(_request({})) == "10.0.0.5"


def test_visitors_behind_the_proxy_get_separate_buckets(monkeypatch, client):
    _with_trust(monkeypatch, True)
    for _ in range(5):
        client.post("/api/contact", headers={"X-Real-IP": "1.1.1.1"}, data={})
    blocked = client.post("/api/contact", headers={"X-Real-IP": "1.1.1.1"}, data={})
    other = client.post("/api/contact", headers={"X-Real-IP": "2.2.2.2"}, data={})
    assert blocked.status_code == 429
    assert other.status_code != 429
