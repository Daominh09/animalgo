from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# Owner: Person B — added with the auth endpoints.
#
# The web build is served from a different port than the API, so every request it makes
# is cross-origin. When this was missing, sign-in failed with a bare "NetworkError when
# attempting to fetch resource" — no status code, no hint the server had been reached.
# These assert the preflight the browser actually sends, not just that middleware exists.

WEB_ORIGIN = "http://localhost:8081"  # Expo's Metro web dev server
client = TestClient(app)


def _preflight(origin: str, method: str = "POST", path: str = "/auth/login"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_preflight_from_the_web_dev_server_is_allowed():
    resp = _preflight(WEB_ORIGIN)

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == WEB_ORIGIN


def test_preflight_allows_the_content_type_header():
    # The app POSTs JSON, so without content-type being allowed the preflight fails even
    # though the origin is fine.
    resp = _preflight(WEB_ORIGIN)

    assert "content-type" in resp.headers["access-control-allow-headers"].lower()


def test_actual_response_carries_the_origin_header():
    # Passing the preflight is not enough — the real response needs the header too, or
    # the browser discards a reply the server successfully sent.
    resp = client.get("/health", headers={"Origin": WEB_ORIGIN})

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == WEB_ORIGIN


def test_unknown_origin_is_not_allowed():
    # Explicit origins, not "*": a page on some other site must not be able to call the
    # API from a signed-in player's browser.
    resp = _preflight("https://evil.example.com")

    assert "access-control-allow-origin" not in resp.headers


def test_authorization_header_is_permitted():
    # Every authenticated call sends a bearer token; a preflight that rejected the
    # Authorization header would break all of them.
    resp = client.options(
        "/collection",
        headers={
            "Origin": WEB_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert resp.status_code == 200
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


def test_credentials_are_not_allowed():
    # We authenticate with a bearer token, not a cookie. Allowing credentials would let
    # a browser attach cookies to cross-site requests automatically, which is the
    # ingredient CSRF needs.
    resp = _preflight(WEB_ORIGIN)

    assert resp.headers.get("access-control-allow-credentials") != "true"


def test_configured_origins_include_the_expo_web_port():
    assert WEB_ORIGIN in settings.cors_origins_list
