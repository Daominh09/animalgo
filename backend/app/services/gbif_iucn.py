import httpx
import redis.asyncio as redis

from app.config import settings

# Owner: Person B — Rarity Engine & Collection
# GBIF occurrence count + IUCN Red List status, both sourced from GBIF and Redis-cached
# (checks Redis first, writes back on a miss, 7-day TTL). Occurrence counts / threat
# status drift slowly, and GBIF rate-limits bursts of anonymous requests (429 after a
# handful), so caching keeps repeated species lookups off the wire.
#
# Why the IUCN status comes from GBIF and not the IUCN API directly: the IUCN Red List
# API (v4) requires an approved token and its terms of use explicitly discourage mobile
# apps / course projects and forbid commercial use. GBIF re-publishes the Red List
# category per species, needs no token, and we already integrate GBIF — so the whole
# rarity path runs on one credential-free API. Tradeoff: GBIF's category tracks its own
# ingest of each Red List release, so it can lag IUCN's very latest version slightly —
# fine for game rarity tiers.
#
# `region` is an ISO 3166-1 alpha-2 country code (e.g. "US", "VN"); occurrence counts
# are strongly region-dependent, which is the whole point of region-weighted rarity.

r = redis.from_url(settings.redis_dsn)

GBIF_BASE = "https://api.gbif.org/v1"
_WEEK = 60 * 60 * 24 * 7  # cache TTL, in seconds
_TIMEOUT = httpx.Timeout(10.0)


async def get_gbif_occurrence_count(species_name: str, region: str) -> int:
    """Regional occurrence count for a species from GBIF, Redis-cached for 7 days.

    Uses the occurrence search with limit=0, which returns only the aggregate `count`
    for the scientificName + country filter — no result rows are transferred."""
    cache_key = f"gbif:{species_name}:{region}"
    cached = await r.get(cache_key)
    if cached is not None:
        return int(cached)

    params = {"scientificName": species_name, "country": region, "limit": 0}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{GBIF_BASE}/occurrence/search", params=params)
        resp.raise_for_status()
        count = int(resp.json()["count"])

    await r.set(cache_key, count, ex=_WEEK)
    return count


async def get_iucn_status(species_name: str) -> str:
    """IUCN Red List threat-status code (LC/NT/VU/EN/CR/...) for a species, Redis-cached.

    Two GBIF calls: match the name to a backbone `usageKey`, then read that taxon's
    IUCN Red List category. Falls back to "NE" (Not Evaluated) when the name doesn't
    match or the taxon has no Red List assessment in GBIF."""
    cache_key = f"iucn:{species_name}"
    cached = await r.get(cache_key)
    if cached is not None:
        return cached if isinstance(cached, str) else bytes(cached).decode()

    status = "NE"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        match = await client.get(f"{GBIF_BASE}/species/match", params={"name": species_name})
        match.raise_for_status()
        usage_key = match.json().get("usageKey")
        if usage_key:
            cat = await client.get(f"{GBIF_BASE}/species/{usage_key}/iucnRedListCategory")
            if cat.status_code == 200 and cat.content:
                # GBIF returns e.g. {"category": "ENDANGERED", "code": "EN", ...};
                # `code` is the short form the rarity engine keys on.
                status = cat.json().get("code") or "NE"

    await r.set(cache_key, status, ex=_WEEK)
    return status
