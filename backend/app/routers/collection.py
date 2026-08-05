import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Capture

router = APIRouter(prefix="/collection", tags=["collection"])

# Owner: Person B — Rarity Engine & Collection

# rarity_tier is a string on the capture row, so "order by rarity" needs an explicit
# ranking -- alphabetical would put common before legendary. Sorting in Python rather
# than SQL: a player's collection is small, and a CASE expression here would have to be
# kept in step with rarity.py by hand.
TIER_ORDER = {"legendary": 0, "rare": 1, "uncommon": 2, "common": 3}
UNRANKED = len(TIER_ORDER)  # unknown rarity sorts last, not first


@router.get("")
async def get_collection(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Every capture this player owns, rarest first, newest first within a tier.

    Coordinates are already fuzzed -- they were generalised before the row was written
    (see app/services/geoprivacy.py), so there is nothing to filter out here.
    """
    rows = (
        await db.execute(select(Capture).where(Capture.owner_id == uuid.UUID(user_id)))
    ).scalars().all()

    rows = sorted(
        rows,
        key=lambda c: (TIER_ORDER.get(c.rarity_tier, UNRANKED), -c.captured_at.timestamp()),
    )

    return [
        {
            "id": str(c.id),
            # What the card shows. Null for rows written before common_name existed, and
            # for identifications that only reached a family -- the app falls back to
            # species_id then.
            "common_name": c.common_name,
            "species_id": c.species_id,  # scientific name
            "image_url": c.image_url,
            "rarity_tier": c.rarity_tier,
            "lat": c.lat,
            "lng": c.lng,
            "confidence_score": c.confidence_score,
            "confirmed_by_user": c.confirmed_by_user,
            "captured_at": c.captured_at.isoformat(),
        }
        for c in rows
    ]
