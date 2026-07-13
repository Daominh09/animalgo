from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id

router = APIRouter(prefix="/wallet", tags=["wallet"])

# Owner: Person D — Economy, Shop & Shared Infra


@router.get("")
async def get_wallet(user_id: str = Depends(get_current_user_id)):
    # TODO: query users.wallet_balance
    return {"balance": 0}


async def credit_wallet(user_id: str, amount: int, reason: str):
    """Internal helper — called by rarity scoring (B) and battle resolution (C), not exposed as a route."""
    # TODO: write a transactions row + increment users.wallet_balance
    pass
