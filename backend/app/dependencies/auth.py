import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import settings

# Supabase projects created since the JWT signing keys migration sign tokens
# with an asymmetric key (ES256 here) instead of a shared HS256 secret, so
# verification goes through the project's JWKS endpoint rather than a secret
# in .env. PyJWKClient caches the fetched key set in-process; the first
# verification after startup (or after a key rotation) pays one blocking
# HTTP fetch, subsequent ones are served from cache.
_jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Verifies the Supabase-issued JWT sent by the mobile app and returns the user id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]
