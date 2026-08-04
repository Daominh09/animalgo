import logging

from app.services import rarity
from app.services.gbif_iucn import get_gbif_occurrence_count, get_iucn_status

logger = logging.getLogger(__name__)

# Owner: Person B — Rarity Engine & Collection
#
# The A -> B hand-off. Once the vision step has a species, this resolves its rarity:
# GBIF occurrence count + IUCN Red List status (both Redis-cached in app/services/
# cache.py), scored into a tier and coin value.
#
# No database writes. Redis is the only cache: the species_cache table was removed
# because nothing read it. Per-capture display data (species name, rarity, image) is
# denormalised onto the capture row instead, which is also what keeps a player's card
# matching the rarity they were actually paid for — species facts can change later, the
# capture must not.
#
# Keyed on the SCIENTIFIC name, deliberately. GBIF is built on scientific names, and
# common names do not resolve reliably -- verified against the live API:
#
#   /species/match?name=House Sparrow          -> matchType=NONE   (occurrence count 0)
#   vernacular search "Red Fox"                -> Passerella iliaca (a Fox Sparrow)
#   vernacular search "Grey Squirrel"          -> Orchopeas howardi (a flea)
#
# That matters more than it looks: an unresolved name yields occurrence_count = 0, and
# score_rarity(0, ...) returns "legendary". Guessing at the scientific name would hand
# out 500 coins for every house sparrow. So when we cannot resolve a species
# confidently we return None -- "unknown rarity" -- rather than scoring it.

# Vision returns this when it sees no animal at all.
NO_ANIMAL = "none"


async def resolve_species_rarity(
    scientific_name: str | None,
    common_name: str | None = None,
) -> dict | None:
    """Look up and score a species' rarity.

    Returns None when rarity cannot be determined (no scientific name, no animal in
    frame, or the upstream lookup failed). Callers must treat None as "unknown", not as
    a rarity of zero -- see the module comment on why that distinction matters.
    """
    if not scientific_name or scientific_name.strip().lower() == NO_ANIMAL:
        return None

    species_id = scientific_name.strip()

    try:
        occurrence_count = await get_gbif_occurrence_count(species_id)
        iucn_status = await get_iucn_status(species_id)
    except Exception:
        # A capture should still succeed if GBIF is down or rate-limiting; the species
        # just has no rarity yet. Nothing is cached, so the next capture retries.
        logger.exception("rarity lookup failed for %s", species_id)
        return None

    tier, coin_value = rarity.score_rarity(occurrence_count, iucn_status)

    return {
        "species_id": species_id,
        "common_name": common_name,
        "gbif_occurrence_count": occurrence_count,
        "iucn_status": iucn_status,
        "rarity_tier": tier,
        "coin_value": coin_value,
    }
