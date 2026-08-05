import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth (dev)"])

# Owner: Person B — added as shared dev tooling.
#
# Convenience endpoint so nobody has to hand-craft a curl call to Supabase every time
# they want to try an authenticated endpoint in /docs. It exchanges an email + password
# for a Supabase user access token — exactly what `POST {SUPABASE_URL}/auth/v1/token
# ?grant_type=password` does, just reachable from the docs page.
#
# DEV ONLY. The mobile app does NOT use this: it talks to Supabase directly with
# EXPO_PUBLIC_SUPABASE_ANON_KEY (see mobile/.env.example), which is the right design —
# passwords should never transit our API. Proxying them here turns the backend into a
# credential-stuffing target with none of Supabase's own rate limiting in front of it.
# That is an acceptable trade for a local dev tool and NOT acceptable in production.
#
# The off switch is SUPABASE_ANON_KEY: leave it unset in any deployed environment and
# this endpoint returns 503 instead of working. No separate feature flag to remember,
# because the key is the one thing the endpoint cannot function without.

_TIMEOUT = httpx.Timeout(10.0)


class TokenRequest(BaseModel):
    email: str
    password: str


@router.post("/token")
async def get_access_token(body: TokenRequest) -> dict:
    """Exchange a Supabase email + password for an access token. **Dev helper.**

    Copy the returned `access_token` into the **Authorize** button at the top of this
    page to call the authenticated endpoints. It expires in about an hour — just call
    this again. See `backend/docs/dev-auth.md`.
    """
    if not settings.supabase_anon_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Dev auth is not configured. Set SUPABASE_ANON_KEY in backend/.env "
                "(Supabase dashboard -> Project Settings -> API Keys -> anon public)."
            ),
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                # The anon key identifies the *project* to Supabase's auth server. It is
                # not the user's credential and is not what the caller gets back.
                headers={"apikey": settings.supabase_anon_key},
                json={"email": body.email, "password": body.password},
            )
    except httpx.HTTPError as exc:
        # Our own network/DNS problem, not the caller's bad password — don't report it
        # as 401 or people will waste time retyping a correct password.
        raise HTTPException(status_code=502, detail=f"Could not reach Supabase auth: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Unexpected response from Supabase auth") from exc

    if resp.status_code != 200:
        # Pass Supabase's own wording through: "Invalid login credentials" and "Email not
        # confirmed" are different problems and the fix differs.
        detail = data.get("error_description") or data.get("msg") or "Sign-in failed"
        raise HTTPException(status_code=401, detail=detail)

    # Deliberately narrow: no refresh_token in the response. It is long-lived, and for a
    # dev helper calling this endpoint again is easier than a refresh round-trip anyway.
    return {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in"),
        "user_id": (data.get("user") or {}).get("id"),
    }
