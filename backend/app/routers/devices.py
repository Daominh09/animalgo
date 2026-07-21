from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id

router = APIRouter(prefix="/devices", tags=["devices"])

# Owner: Person D — Economy, Shop & Shared Infra
# Week 1: accept and acknowledge an Expo push token
# Week 2: persist to users.push_token, use it to send battle-resolved notifications


@router.post("/register")
async def register_device(push_token: str, user_id: str = Depends(get_current_user_id)):
    # TODO: upsert push_token onto the users row for user_id
    return {"registered": True}
