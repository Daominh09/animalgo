import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth

# Owner: Person B — dev auth helper.
# Supabase's auth server is faked, so no network and no real credentials are needed.
# A bare app with only this router is mounted, to keep the DB/storage imports out.


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


class _FakeResponse:
    def __init__(self, status_code, payload, valid_json=True):
        self.status_code = status_code
        self._payload = payload
        self._valid_json = valid_json

    def json(self):
        if not self._valid_json:
            raise ValueError("not json")
        return self._payload


def _fake_supabase(monkeypatch, response=None, error=None):
    """Replace httpx.AsyncClient inside the router. Returns a dict that captures the
    outgoing request so tests can assert what we actually sent."""
    sent = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, params=None, headers=None, json=None):
            sent.update(url=url, params=params, headers=headers, json=json)
            if error:
                raise error
            return response

    monkeypatch.setattr(auth.httpx, "AsyncClient", _FakeClient)
    return sent


def _ok_payload(**overrides):
    payload = {
        "access_token": "header.payload.signature",
        "refresh_token": "long-lived-secret",
        "expires_in": 3600,
        "user_id_ignored": True,
        "user": {"id": "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f", "email": "a@b.com"},
    }
    payload.update(overrides)
    return payload


def test_returns_access_token_and_user_id(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    _fake_supabase(monkeypatch, response=_FakeResponse(200, _ok_payload()))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert resp.status_code == 200
    assert resp.json() == {
        "access_token": "header.payload.signature",
        "expires_in": 3600,
        "user_id": "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f",
    }


def test_refresh_token_is_not_returned(monkeypatch):
    # It is long-lived; a dev helper has no reason to hand it out.
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    _fake_supabase(monkeypatch, response=_FakeResponse(200, _ok_payload()))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert "refresh_token" not in resp.json()


def test_sends_password_grant_with_anon_key(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(auth.settings, "supabase_url", "https://proj.supabase.co")
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, _ok_payload()))

    _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert sent["url"] == "https://proj.supabase.co/auth/v1/token"
    assert sent["params"] == {"grant_type": "password"}
    assert sent["headers"] == {"apikey": "anon-key"}  # project key, not the user's
    assert sent["json"] == {"email": "a@b.com", "password": "pw"}


def test_disabled_when_anon_key_missing(monkeypatch):
    # This blank-key path is the production off switch, so it must never reach Supabase.
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "")
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, _ok_payload()))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert resp.status_code == 503
    assert "SUPABASE_ANON_KEY" in resp.json()["detail"]
    assert sent == {}  # no outbound call at all


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"error_description": "Invalid login credentials"}, "Invalid login credentials"),
        ({"msg": "Email not confirmed"}, "Email not confirmed"),
        ({}, "Sign-in failed"),
    ],
)
def test_bad_credentials_pass_supabase_message_through(monkeypatch, payload, expected):
    # "wrong password" and "unconfirmed user" need different fixes, so the wording matters.
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    _fake_supabase(monkeypatch, response=_FakeResponse(400, payload))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "wrong"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == expected


def test_unreachable_supabase_is_502_not_401(monkeypatch):
    # Our infrastructure failing must not read as "your password is wrong".
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    _fake_supabase(monkeypatch, error=httpx.ConnectError("dns failure"))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert resp.status_code == 502
    assert "Could not reach Supabase auth" in resp.json()["detail"]


def test_non_json_response_is_502(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    _fake_supabase(monkeypatch, response=_FakeResponse(502, None, valid_json=False))

    resp = _client().post("/auth/token", json={"email": "a@b.com", "password": "pw"})

    assert resp.status_code == 502
