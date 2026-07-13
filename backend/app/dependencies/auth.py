from fastapi import Header, HTTPException
from jose import jwt, JWTError

from app.config import settings


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Verifies the Supabase-issued JWT sent by the mobile app and returns the user id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]
