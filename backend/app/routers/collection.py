from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id

router = APIRouter(prefix="/collection", tags=["collection"])

# Owner: Person B — Rarity Engine & Collection


@router.get("")
async def get_collection(user_id: str = Depends(get_current_user_id)):
    # TODO: query captures table for this user, ordered by rarity
    return []
