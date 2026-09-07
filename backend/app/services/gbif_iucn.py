import httpx

from app.services.cache import get_or_fetch

# Owner: Person B — Rarity Engine & Collection
# GBIF occurrence count + IUCN Red List status. Fetching (the GBIF HTTP calls) is kept
# separate from caching: the public functions wrap a private `_fetch_*` in get_or_fetch
# (Redis-first, write-back on a miss — see app/services/cache.py).
#
# Why the IUCN status comes from GBIF and not the IUCN API directly: the IUCN Red List
# API (v4) requires an approved token and its terms of use explicitly discourage mobile
# apps / course projects and forbid commercial use. GBIF re-publishes the Red List
# category per species, needs no token, and we already integrate GBIF — so the whole
# rarity path runs on one credential-free API. Tradeoff: GBIF's category tracks its own
# ingest of each Red List release, so it can lag IUCN's very latest version slightly —
# fine for game rarity tiers.
#
# The app targets US-based players only, so occurrence counts always use country=US.
# `region` is an ISO 3166-1 alpha-2 country code and defaults to "US"; it's kept as a
# parameter (not hardcoded) so the region dimension can come back if the app ever
# expands beyond the US.

GBIF_BASE = "https://api.gbif.org/v1"
_TIMEOUT = httpx.Timeout(10.0)


def _normalize_species_name(species_name: str) -> str:
    """Collapse harmless whitespace differences before lookup and caching."""
    return " ".join(species_name.split())


async def _fetch_gbif_occurrence_count(species_name: str, region: str) -> int:
    """Live GBIF occurrence count. limit=0 returns only the aggregate `count` for the
    scientificName + country filter — no result rows are transferred."""
    params = {"scientificName": species_name, "country": region, "limit": 0}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{GBIF_BASE}/occurrence/search", params=params)
        resp.raise_for_status()
        return int(resp.json()["count"])


async def get_gbif_occurrence_count(species_name: str, region: str = "US") -> int:
    """US occurrence count for a species (region defaults to US), Redis-cached for 7 days."""
    species_name = _normalize_species_name(species_name)
    region = region.strip().upper()
    key = f"gbif:{species_name.casefold()}:{region}"
    return int(await get_or_fetch(key, lambda: _fetch_gbif_occurrence_count(species_name, region)))


async def _fetch_iucn_status(species_name: str) -> str:
    """Live IUCN Red List status via GBIF: match the name to a backbone `usageKey`, then
    read that taxon's Red List category. Falls back to "NE" (Not Evaluated) when the name
    doesn't match or the taxon has no Red List assessment in GBIF."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        match = await client.get(f"{GBIF_BASE}/species/match", params={"name": species_name})
        match.raise_for_status()
        usage_key = match.json().get("usageKey")
        if not usage_key:
            return "NE"
        cat = await client.get(f"{GBIF_BASE}/species/{usage_key}/iucnRedListCategory")
        if cat.status_code == 200 and cat.content:
            # GBIF returns e.g. {"category": "ENDANGERED", "code": "EN", ...};
            # `code` is the short form the rarity engine keys on.
            return cat.json().get("code") or "NE"
        return "NE"


async def get_iucn_status(species_name: str) -> str:
    """IUCN Red List threat-status code (LC/NT/VU/EN/CR/...) for a species, Redis-cached
    for 7 days."""
    species_name = _normalize_species_name(species_name)
    key = f"iucn:{species_name.casefold()}"
    return await get_or_fetch(key, lambda: _fetch_iucn_status(species_name))
