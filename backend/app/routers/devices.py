import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import User

router = APIRouter(prefix="/devices", tags=["devices"])

# Owner: Person D — Economy, Shop & Shared Infra
#
# Persistence added by Person C (battle vertical): the stub acknowledged the token
# without storing it, so users.push_token was always null and every battle notification
# had nowhere to go. Kept minimal and in D's file rather than moved -- the sending half
# lives in app/services/push.py, which is C's.


@router.post("/register")
async def register_device(
    push_token: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Stores the device's Expo push token against the signed-in user.

    Called on every app start, so it's an upsert rather than an insert: the token is
    reissued when the app is reinstalled or restored onto a new device, and the row must
    follow the current device rather than keep pushing at a dead one.
    """
    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        # Same situation GET /wallet handles: a Supabase-authenticated user who has not
        # yet touched the app's own users table.
        user = User(id=uuid.UUID(user_id))
        db.add(user)

    user.push_token = push_token
    await db.commit()
    return {"registered": True}
