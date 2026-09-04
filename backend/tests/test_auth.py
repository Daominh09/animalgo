import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth

# Owner: Person B — the /auth endpoints.
# Supabase's auth API and the rate limiter's Redis are both faked, so no network, no
# Redis and no real credentials are involved.

CREDS = {"email": "Player@Example.com ", "password": "hunter2!"}


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
    """Replace httpx.AsyncClient inside the router; returns a dict capturing what we sent."""
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
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(auth.settings, "supabase_url", "https://proj.supabase.co")
    return sent


def _allow_all(monkeypatch, allowed=True):
    calls = []

    async def check(action, key, limit, window):
        calls.append((action, key))
        return allowed

    async def reset(action, key):
        calls.append(("reset", key))

    monkeypatch.setattr(auth.ratelimit, "check_and_count", check)
    monkeypatch.setattr(auth.ratelimit, "reset", reset)
    return calls


SESSION = {
    "access_token": "header.payload.sig",
    "refresh_token": "refresh-me",
    "expires_in": 3600,
    "user": {"id": "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f", "email": "player@example.com"},
}


# --- login ----------------------------------------------------------------------------


def test_login_returns_a_session(monkeypatch):
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    body = _client().post("/auth/login", json=CREDS).json()

    assert body == {
        "access_token": "header.payload.sig",
        "refresh_token": "refresh-me",
        "expires_in": 3600,
        "user_id": "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f",
    }


def test_login_sends_the_password_grant_with_the_anon_key(monkeypatch):
    _allow_all(monkeypatch)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/login", json=CREDS)

    assert sent["url"] == "https://proj.supabase.co/auth/v1/token"
    assert sent["params"] == {"grant_type": "password"}
    assert sent["headers"] == {"apikey": "anon-key"}  # project key, not the user's
    # Email normalised before it leaves us, so "Player@Example.com " and
    # "player@example.com" are one account and one rate-limit bucket.
    assert sent["json"] == {"email": "player@example.com", "password": "hunter2!"}


def test_bad_credentials_pass_supabase_wording_through(monkeypatch):
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(400, {"error_description": "Invalid login credentials"}))

    resp = _client().post("/auth/login", json=CREDS)

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid login credentials"


def test_unreachable_supabase_is_502_not_401(monkeypatch):
    # Our infrastructure failing must not read as "your password is wrong".
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, error=httpx.ConnectError("dns failure"))

    resp = _client().post("/auth/login", json=CREDS)

    assert resp.status_code == 502


def test_supabase_5xx_is_502_not_401(monkeypatch):
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(500, {"msg": "internal error"}))

    assert _client().post("/auth/login", json=CREDS).status_code == 502


def test_short_password_is_rejected_before_leaving_the_server(monkeypatch):
    _allow_all(monkeypatch)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    resp = _client().post("/auth/login", json={"email": "a@b.com", "password": "12345"})

    assert resp.status_code == 422
    assert sent == {}  # never reached Supabase


# --- rate limiting ---------------------------------------------------------------------


def test_too_many_attempts_are_blocked(monkeypatch):
    _allow_all(monkeypatch, allowed=False)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    resp = _client().post("/auth/login", json=CREDS)

    assert resp.status_code == 429
    # The point of the limiter: a blocked attempt must not be replayed upstream, or it
    # burns Supabase's shared per-IP quota anyway.
    assert sent == {}


def test_limit_is_keyed_on_the_normalised_email(monkeypatch):
    calls = _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/login", json=CREDS)

    assert ("login", "player@example.com") in calls


def test_success_clears_the_counter(monkeypatch):
    # So someone who mistyped twice then got it right isn't left throttled.
    calls = _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/login", json=CREDS)

    assert ("reset", "player@example.com") in calls


def test_failure_does_not_clear_the_counter(monkeypatch):
    calls = _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(400, {"msg": "Invalid login credentials"}))

    _client().post("/auth/login", json=CREDS)

    assert not any(c[0] == "reset" for c in calls)  # failures must accumulate


def test_refresh_is_not_rate_limited(monkeypatch):
    calls = _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/refresh", json={"refresh_token": "refresh-me"})

    assert not any(c[0] == "login" for c in calls)


# --- register ---------------------------------------------------------------------------


def test_register_signs_the_player_in_when_confirmation_is_off(monkeypatch):
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    resp = _client().post("/auth/register", json=CREDS)

    assert resp.status_code == 201
    assert resp.json()["confirmation_required"] is False
    assert resp.json()["access_token"] == "header.payload.sig"


def test_register_reports_when_confirmation_is_required(monkeypatch):
    # Supabase returns a user but no session. Saying so is the difference between
    # "nothing happened" and "go and check your inbox".
    _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, {"user": {"id": "abc"}}))

    body = _client().post("/auth/register", json=CREDS).json()

    assert body == {"confirmation_required": True, "user_id": "abc"}


def test_register_is_rate_limited(monkeypatch):
    # Same shared-bucket problem as login, plus unlimited signups turn "already
    # registered" into an account-existence oracle.
    _allow_all(monkeypatch, allowed=False)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    resp = _client().post("/auth/register", json=CREDS)

    assert resp.status_code == 429
    assert sent == {}  # blocked attempts must not be replayed upstream


def test_register_limit_is_keyed_on_the_normalised_email(monkeypatch):
    calls = _allow_all(monkeypatch)
    _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/register", json=CREDS)

    assert ("register", "player@example.com") in calls


def test_register_hits_the_signup_endpoint(monkeypatch):
    _allow_all(monkeypatch)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))

    _client().post("/auth/register", json=CREDS)

    assert sent["url"] == "https://proj.supabase.co/auth/v1/signup"


# --- configuration -----------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/auth/login", "/auth/register"])
def test_missing_anon_key_is_503(monkeypatch, path):
    _allow_all(monkeypatch)
    sent = _fake_supabase(monkeypatch, response=_FakeResponse(200, SESSION))
    monkeypatch.setattr(auth.settings, "supabase_anon_key", "")

    resp = _client().post(path, json=CREDS)

    assert resp.status_code == 503
    assert "SUPABASE_ANON_KEY" in resp.json()["detail"]
    assert sent == {}
