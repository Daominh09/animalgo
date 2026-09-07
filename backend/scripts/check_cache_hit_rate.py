"""Measure Redis hit rate under repeated GBIF/IUCN lookups.

Run from ``backend/`` while Redis is available:

    python -m scripts.check_cache_hit_rate --repeats 5

Starting cold, each species/reference pair should miss once and hit on every repeat.
An already-warm cache will report an even higher rate. The command exits non-zero when
the measured rate falls below that expected cold-cache floor.
"""

import argparse
import asyncio

from app.services.cache import cache_metrics, r
from app.services.gbif_iucn import get_gbif_occurrence_count, get_iucn_status

DEFAULT_SPECIES = [
    "Passer domesticus",
    "Cardinalis cardinalis",
    "Ursus americanus",
]


async def measure(species_names: list[str], region: str, repeats: int) -> None:
    cache_metrics.reset()

    for _ in range(repeats):
        for species_name in species_names:
            await asyncio.gather(
                get_gbif_occurrence_count(species_name, region),
                get_iucn_status(species_name),
            )

    expected_floor = (repeats - 1) / repeats
    print(
        f"requests={cache_metrics.requests} hits={cache_metrics.hits} "
        f"misses={cache_metrics.misses} hit_rate={cache_metrics.hit_rate:.1%}"
    )
    print(f"cold-cache floor for {repeats} repeats: {expected_floor:.1%}")

    if cache_metrics.hit_rate < expected_floor:
        raise SystemExit(
            "Cache hit rate is below the expected floor; check Redis connectivity, "
            "evictions, and cache-key consistency."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--region", default="US")
    parser.add_argument("species", nargs="*", default=DEFAULT_SPECIES)
    args = parser.parse_args()

    if args.repeats < 2:
        parser.error("--repeats must be at least 2")

    async def run() -> None:
        try:
            await measure(args.species, args.region, args.repeats)
        finally:
            await r.aclose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
