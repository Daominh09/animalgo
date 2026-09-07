from dataclasses import dataclass

import redis.asyncio as redis

from app.config import settings

# Owner: Person B — Rarity Engine & Collection
#
# The Redis hot cache and its get-or-fetch wrapper. Redis sits between the rarity engine
# and the GBIF API: the same handful of species get looked up over and over, while GBIF
# rate-limits bursts of anonymous requests (429 after a handful). get_or_fetch keeps
# repeated lookups off the wire.
#
# This is the only rarity cache. There is deliberately no durable copy in Postgres: the
# species_cache table was removed because nothing read it. The trade-off is that if
# Redis is unavailable, lookups go straight to GBIF, and if that fails too the capture
# gets unknown rarity rather than a stale-but-usable answer.

r = redis.from_url(settings.redis_dsn)

WEEK_SECONDS = 60 * 60 * 24 * 7  # default TTL for species reference data


@dataclass
class CacheMetrics:
    """Process-local counters for checking the rarity cache's effectiveness.

    These deliberately avoid extra Redis writes on the hot path. They reset whenever
    the API process restarts and are intended for diagnostics, not durable analytics.
    """

    hits: int = 0
    misses: int = 0

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.requests if self.requests else 0.0

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0


cache_metrics = CacheMetrics()


async def get_or_fetch(key: str, fetch, ttl: int = WEEK_SECONDS) -> str:
    """Return the cached string for ``key``, or call ``fetch()`` (an async callable),
    cache its result under ``key`` with ``ttl``, and return it.

    Values are stored as strings; callers cast as needed. If ``fetch`` raises, nothing is
    written — so a transient upstream error is retried next time rather than frozen in
    for the full TTL.
    """
    cached = await r.get(key)
    if cached is not None:
        cache_metrics.hits += 1
        return cached if isinstance(cached, str) else bytes(cached).decode()
    cache_metrics.misses += 1
    value = str(await fetch())
    await r.set(key, value, ex=ttl)
    return value
