import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.cache import get_or_fetch

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

# Owner: Person D — Economy, Shop & Shared Infra

RESULT_LIMIT = 50
CACHE_TTL_SECONDS = 30  # short — balances/captures change often, unlike species reference data

# Must stay in sync with app/services/rarity.COIN_VALUES. Duplicated as a SQL
# CASE rather than imported, since these two need the same numbers expressed in
# two different languages (a raw query here vs. a Python function there) --
# exported so profile.py (also D's) shares this one instead of a third copy.
RARITY_WEIGHT_CASE_SQL = """
    case rarity_tier
        when 'legendary' then 500
        when 'rare' then 200
        when 'uncommon' then 75
        when 'common' then 25
        else 0
    end
"""

_QUERIES = {
    "coins": f"""
        select u.id::text as user_id, u.display_name, u.wallet_balance as value
        from users u
        order by u.wallet_balance desc
        limit {RESULT_LIMIT}
    """,
    "captures": f"""
        select u.id::text as user_id, u.display_name, count(c.id) as value
        from users u
        join captures c on c.owner_id = u.id
        group by u.id, u.display_name
        order by value desc
        limit {RESULT_LIMIT}
    """,
    "rarity": f"""
        select u.id::text as user_id, u.display_name, max({RARITY_WEIGHT_CASE_SQL}) as value
        from users u
        join captures c on c.owner_id = u.id
        group by u.id, u.display_name
        order by value desc
        limit {RESULT_LIMIT}
    """,
    "wins": f"""
        select u.id::text as user_id, u.display_name, count(b.id) as value
        from users u
        join battles b on b.winner_id = u.id
        group by u.id, u.display_name
        order by value desc
        limit {RESULT_LIMIT}
    """,
}


@router.get("")
async def get_leaderboard(
    rank_by: str = Query("coins", pattern="^(coins|captures|rarity|wins)$"),
    db: AsyncSession = Depends(get_db),
):
    async def fetch() -> str:
        rows = (await db.execute(text(_QUERIES[rank_by]))).mappings().all()
        return json.dumps([dict(row) for row in rows])

    cached = await get_or_fetch(f"leaderboard:{rank_by}", fetch, ttl=CACHE_TTL_SECONDS)
    return json.loads(cached)
