import redis.asyncio as redis

from app.config import settings

# Owner: Person B — Rarity Engine & Collection
# Week 1: confirm response shape against real GBIF/IUCN calls, then fill in the TODOs below

r = redis.from_url(settings.redis_url)


async def get_gbif_occurrence_count(species_name: str, region: str) -> int:
    cache_key = f"gbif:{species_name}:{region}"
    cached = await r.get(cache_key)
    if cached:
        return int(cached)
    # TODO: call https://api.gbif.org/v1/occurrence/search?scientificName=...&country=...
    count = 0
    await r.set(cache_key, count, ex=60 * 60 * 24 * 7)  # 7 day TTL
    return count


async def get_iucn_status(species_name: str) -> str:
    cache_key = f"iucn:{species_name}"
    cached = await r.get(cache_key)
    if cached:
        return cached.decode()
    # TODO: call the IUCN Red List API
    status = "NE"  # Not Evaluated — placeholder
    await r.set(cache_key, status, ex=60 * 60 * 24 * 7)
    return status
