from fastapi import APIRouter

from app.services import rarity
from app.services.gbif_iucn import get_gbif_occurrence_count, get_iucn_status

router = APIRouter(prefix="/rarity", tags=["rarity"])

# Owner: Person B — Rarity Engine & Collection
#
# Dev/test endpoint: runs a species+region straight through the two fetch functions
# (GBIF occurrence count + IUCN status, both Redis-cached) and the scoring function,
# so the whole rarity path can be exercised without the capture pipeline. Not part of
# the real capture flow — that's wired in Week 2. No auth so it's easy to curl.
#
#   GET /rarity/lookup?species=Panthera%20tigris&region=US


@router.get("/lookup")
async def lookup(species: str, region: str = "US"):
    occurrence_count = await get_gbif_occurrence_count(species, region)
    iucn_status = await get_iucn_status(species)
    tier, coins = rarity.score_rarity(occurrence_count, iucn_status)
    return {
        "species": species,
        "region": region,
        "gbif_occurrence_count": occurrence_count,
        "iucn_status": iucn_status,
        "rarity_tier": tier,
        "coin_value": coins,
    }
