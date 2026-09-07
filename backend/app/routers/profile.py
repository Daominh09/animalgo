import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.routers.leaderboard import RARITY_WEIGHT_CASE_SQL

router = APIRouter(prefix="/profile", tags=["profile"])

# Owner: Person D — Economy, Shop & Shared Infra
#
# Deliberately excludes wallet_balance: another player's currency isn't a
# flex-worthy stat, and showing it has no upside (only a mild social-
# engineering/targeting risk) for a public, no-auth endpoint. Also excludes
# raw lat/lng entirely -- not because they're unsafe (every capture's
# coordinates are already fuzzed to an 11km grid before they're ever
# persisted, see app/services/geoprivacy.py), just because a share card has
# no use for a coordinate a Map screen would.
#
# No privacy toggle: the task ("GET /profile/{id}/public") and the plan doc
# both specify this as always-public, so there's no "private profile" state
# to represent. If that's wrong, it's a product conversation, not a bug fix.


@router.get("/{user_id}/public")
async def get_public_profile(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    capture_count = (
        await db.execute(
            text("select count(*) from captures where owner_id = :uid"),
            {"uid": str(user_id)},
        )
    ).scalar_one()

    rarest_row = (
        await db.execute(
            text(f"""
                select common_name, species_id, rarity_tier, image_url
                from captures
                where owner_id = :uid and rarity_tier is not null
                order by {RARITY_WEIGHT_CASE_SQL} desc, captured_at asc
                limit 1
            """),
            {"uid": str(user_id)},
        )
    ).mappings().first()

    battle_wins = (
        await db.execute(
            text("select count(*) from battles where winner_id = :uid"),
            {"uid": str(user_id)},
        )
    ).scalar_one()

    return {
        "user_id": str(user_id),
        "display_name": user.display_name or "Anonymous",
        "capture_count": capture_count,
        "rarest_capture": dict(rarest_row) if rarest_row else None,
        "battle_wins": battle_wins,
    }
