from fastapi import APIRouter

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

# Owner: Person D — Economy, Shop & Shared Infra


@router.get("")
async def get_leaderboard():
    # TODO: Redis-cached aggregate of top players by coins/rarity
    return []
