from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id

router = APIRouter(prefix="/battles", tags=["battles"])

# Owner: Person C — Battle System


@router.post("/challenge")
async def create_challenge(opponent_id: str, my_capture_id: str, user_id: str = Depends(get_current_user_id)):
    # TODO: create a battles row, status "pending"
    return {"battle_id": "mock-battle-id", "status": "pending"}


@router.get("/{battle_id}")
async def get_battle(battle_id: str):
    # TODO: fetch battle, run resolution logic (rarity + random stat roll) once both sides are in
    return {"battle_id": battle_id, "status": "pending"}
