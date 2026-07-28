import redis.asyncio as redis

from app.config import settings

# Owner: Person B — Rarity Engine & Collection
#
# The Redis hot cache and its get-or-fetch wrapper. Redis sits between the rarity engine
# and the GBIF API: the same handful of species get looked up over and over, while GBIF
# rate-limits bursts of anonymous requests (429 after a handful). get_or_fetch keeps
# repeated lookups off the wire.
#
# This is the *hot* cache. The durable per-species record lives in the species_cache
# Postgres table (app/models.SpeciesCache), written on the capture path in Week 2; Redis
# is what the live request path checks first.

r = redis.from_url(settings.redis_dsn)

WEEK_SECONDS = 60 * 60 * 24 * 7  # default TTL for species reference data


async def get_or_fetch(key: str, fetch, ttl: int = WEEK_SECONDS) -> str:
    """Return the cached string for ``key``, or call ``fetch()`` (an async callable),
    cache its result under ``key`` with ``ttl``, and return it.

    Values are stored as strings; callers cast as needed. If ``fetch`` raises, nothing is
    written — so a transient upstream error is retried next time rather than frozen in
    for the full TTL.
    """
    cached = await r.get(key)
    if cached is not None:
        return cached if isinstance(cached, str) else bytes(cached).decode()
    value = str(await fetch())
    await r.set(key, value, ex=ttl)
    return value
