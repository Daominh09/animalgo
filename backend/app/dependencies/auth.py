import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

# Supabase projects created since the JWT signing keys migration sign tokens
# with an asymmetric key (ES256 here) instead of a shared HS256 secret, so
# verification goes through the project's JWKS endpoint rather than a secret
# in .env. PyJWKClient caches the fetched key set in-process; the first
# verification after startup (or after a key rotation) pays one blocking
# HTTP fetch, subsequent ones are served from cache.
_jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")

# Declared as a security scheme rather than a plain `Header(...)` parameter, because
# the OpenAPI spec says a header parameter literally named "Authorization" SHALL be
# ignored. With a raw Header(...) the docs page renders a text box that is silently
# dropped, so requests arrive with no header and fail as "Field required" — confusing,
# and it makes /docs unusable for every authenticated endpoint. A security scheme gives
# the docs page its "Authorize" button and sends the header correctly.
#
# auto_error=False so a missing header is our own 401 "Missing bearer token" rather
# than FastAPI's default 403.
_bearer = HTTPBearer(
    auto_error=False,
    description=(
        "Supabase user access token. Sign in via "
        "POST {SUPABASE_URL}/auth/v1/token?grant_type=password and paste the "
        "`access_token` here. The anon/publishable key will NOT work: it is issued for "
        "audience 'anon', and this API requires 'authenticated'."
    ),
)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Verifies the Supabase-issued JWT sent by the mobile app and returns the user id."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]
