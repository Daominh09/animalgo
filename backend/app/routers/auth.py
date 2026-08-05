import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import ratelimit

router = APIRouter(prefix="/auth", tags=["auth"])

# Owner: Person B — built ahead of Person D's shared-infra slot, because the team needed
# their own logins instead of sharing one set of credentials.
#
# The app signs in through here rather than calling Supabase directly. That keeps one
# API surface for the client and means auth rules (throttling, lockouts, audit) live in
# one place we control.
#
# The trade-off, stated so nobody has to rediscover it: passwords transit our server.
# We never store or log them, but we are now on the path of every sign-in, and Supabase's
# per-IP throttling sees our server's IP for every user rather than each user's own. The
# limiter in app/services/ratelimit.py is what replaces that protection -- without it
# password guessing against this endpoint would be unmetered.
#
# The anon key is what identifies our project to Supabase's auth server. It is not a
# secret (it ships in every client build elsewhere) but it is not the user's credential
# either, and it never appears in a response.

_TIMEOUT = httpx.Timeout(10.0)

# Five attempts per email per fifteen minutes. Enough headroom for a person mistyping a
# password, far too little for guessing one. Keyed on email rather than IP so a shared
# network doesn't lock out a whole classroom, and so an attacker rotating IPs gains
# nothing against a single account.
LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60

# Registration needs the same treatment for the same reason: it reaches Supabase from
# our single IP, so their per-IP signup limit is a shared bucket here too. Unlimited
# signups would also make this an account-existence oracle -- "already registered" tells
# an attacker which addresses have accounts. Keyed on email so one address cannot be
# probed repeatedly; a higher allowance than login because retrying a signup after a
# validation error is normal and costs nothing.
REGISTER_LIMIT = 10
REGISTER_WINDOW_SECONDS = 60 * 60


class Credentials(BaseModel):
    email: str
    # Supabase's own minimum is 6; stating it here turns a confusing upstream 422 into a
    # clear message before the request ever leaves our server.
    password: str = Field(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


async def _supabase_auth(path: str, payload: dict, params: dict | None = None) -> dict:
    """POST to Supabase's auth API and return the parsed body, translating its failures
    into ours. Raises HTTPException; never returns an error body."""
    if not settings.supabase_anon_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Auth is not configured: set SUPABASE_ANON_KEY in backend/.env "
                "(Supabase -> Project Settings -> API Keys -> anon public)."
            ),
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.supabase_url}/auth/v1/{path}",
                params=params,
                headers={"apikey": settings.supabase_anon_key},
                json=payload,
            )
    except httpx.HTTPError as exc:
        # Our network failing is not the caller's bad password. Reporting it as 401 would
        # send them off to retype a password that was correct all along.
        raise HTTPException(status_code=502, detail=f"Could not reach Supabase auth: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Unexpected response from Supabase auth") from exc

    if resp.status_code >= 400:
        # Supabase's own wording is passed through: "Invalid login credentials" and
        # "Email not confirmed" need different fixes from the person reading them.
        detail = data.get("error_description") or data.get("msg") or data.get("message") or "Authentication failed"
        # 4xx from Supabase is about the credentials; 5xx is Supabase having a bad day.
        raise HTTPException(status_code=401 if resp.status_code < 500 else 502, detail=detail)

    return data


def _session(data: dict) -> dict:
    """The session fields the app needs, and nothing else."""
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 3600),
        "user_id": (data.get("user") or {}).get("id"),
    }


@router.post("/register", status_code=201)
async def register(body: Credentials) -> dict:
    """Create an account.

    Returns a session when the project has email confirmation switched off, so a new
    player is signed in immediately. With confirmation on, Supabase returns no session
    and `confirmation_required` is true — the account exists but cannot sign in until the
    emailed link is followed.
    """
    email = body.email.strip().lower()

    if not await ratelimit.check_and_count("register", email, REGISTER_LIMIT, REGISTER_WINDOW_SECONDS):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-up attempts for this email. Try again later.",
        )

    data = await _supabase_auth("signup", {"email": email, "password": body.password})

    if not data.get("access_token"):
        return {"confirmation_required": True, "user_id": (data.get("user") or {}).get("id")}

    return {"confirmation_required": False, **_session(data)}


@router.post("/login")
async def login(body: Credentials) -> dict:
    """Exchange an email and password for a session.

    `access_token` goes in the `Authorization: Bearer` header of every other request. It
    expires in about an hour; use `refresh_token` against `/auth/refresh` rather than
    asking the player to sign in again.
    """
    email = body.email.strip().lower()

    if not await ratelimit.check_and_count("login", email, LOGIN_LIMIT, LOGIN_WINDOW_SECONDS):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts for this email. Wait 15 minutes and try again.",
        )

    data = await _supabase_auth("token", {"email": email, "password": body.password}, {"grant_type": "password"})

    # Only a success clears the counter, so failures keep accumulating toward the limit.
    await ratelimit.reset("login", email)
    return _session(data)


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict:
    """Trade a refresh token for a fresh session.

    Not rate limited: a refresh token is already a credential the caller had to obtain by
    signing in, so there is nothing to guess. Throttling it would only break long
    sessions on flaky networks.
    """
    data = await _supabase_auth(
        "token", {"refresh_token": body.refresh_token}, {"grant_type": "refresh_token"}
    )
    return _session(data)
