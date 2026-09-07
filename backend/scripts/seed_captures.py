"""Seed a player account with a map-and-collection demo.

The sample set includes repeated species and captures in the same geoprivacy grid cell,
so the Map's species filters and clusters are visible immediately.

Credentials are arguments, never defaults in the file, so no password ends up in git:

    python -m scripts.seed_captures --email you@example.com --password '...'

Idempotent: capture ids are derived from the owner and sample key, so re-running updates
nothing and inserts nothing twice. Original sample keys remain unchanged, preserving ids
created by older versions of this script.

Delete this script once real captures can be created through the app.
"""

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Capture, User
from app.services.rarity import COIN_VALUES

# Deterministic ids come from this namespace, so the same account and species always map
# to the same capture row.
SEED_NAMESPACE = uuid.UUID("6f1d9b2e-4a37-4c85-9d10-7e2b5c8a3f41")


def photo(keyword: str, lock: int) -> str:
    return f"https://loremflickr.com/400/400/{keyword}?lock={lock}"


# Coordinates are grid centres, because geoprivacy snaps every capture to a ~11 km cell
# before it is stored -- a real row never holds arbitrary decimals. The tiger sits at the
# fuzzed form of 48.87466, 2.34515.
#
# Tiers are what score_rarity actually returns for these species' US occurrence counts,
# so the seeded data cannot disagree with the live rarity engine. The first field is a
# stable sample key. Repeated coordinates deliberately model captures that landed in the
# same fuzzed grid cell, making MapLibre's clusters visible even after filtering.
SAMPLE_CAPTURES = [
    (
        "Panthera tigris",
        "Panthera tigris",
        "Tiger",
        "legendary",
        48.85,
        2.35,
        0.94,
        photo("tiger", 2),
    ),
    (
        "Puma concolor",
        "Puma concolor",
        "Mountain Lion",
        "rare",
        40.75,
        -111.85,
        0.81,
        photo("cougar", 5),
    ),
    (
        "Puma concolor:2",
        "Puma concolor",
        "Mountain Lion",
        "rare",
        40.75,
        -111.85,
        0.87,
        photo("cougar", 10),
    ),
    (
        "Ursus americanus",
        "Ursus americanus",
        "American Black Bear",
        "uncommon",
        44.45,
        -110.55,
        0.88,
        photo("bear", 6),
    ),
    (
        "Ursus americanus:2",
        "Ursus americanus",
        "American Black Bear",
        "uncommon",
        44.45,
        -110.55,
        0.84,
        photo("bear", 11),
    ),
    (
        "Cardinalis cardinalis",
        "Cardinalis cardinalis",
        "Northern Cardinal",
        "common",
        39.85,
        -98.55,
        0.96,
        photo("cardinal-bird", 7),
    ),
    (
        "Cardinalis cardinalis:2",
        "Cardinalis cardinalis",
        "Northern Cardinal",
        "common",
        39.85,
        -98.55,
        0.93,
        photo("cardinal-bird", 12),
    ),
    (
        "Cardinalis cardinalis:3",
        "Cardinalis cardinalis",
        "Northern Cardinal",
        "common",
        39.95,
        -98.45,
        0.90,
        photo("cardinal-bird", 13),
    ),
    # A family, not a species: no common name to show, and rarity could not be
    # determined. Renders the dashed "Unknown" badge, a grey pin, and falls back to the
    # scientific name on the card.
    (
        "Troglodytidae",
        "Troglodytidae",
        None,
        None,
        34.05,
        -118.25,
        0.42,
        photo("wren", 8),
    ),
    # A genuinely unidentified capture exercises the Map's Unidentified species chip.
    (
        "unidentified:1",
        None,
        None,
        None,
        34.05,
        -118.25,
        0.20,
        photo("wildlife", 14),
    ),
    # No location: shows in the Collection grid, never on the map.
    (
        "Passer domesticus",
        "Passer domesticus",
        "House Sparrow",
        "common",
        None,
        None,
        0.91,
        photo("sparrow", 9),
    ),
    # Mapped sparrows make the repeated-species count and another cluster easy to see.
    (
        "Passer domesticus:2",
        "Passer domesticus",
        "House Sparrow",
        "common",
        34.05,
        -118.25,
        0.95,
        photo("sparrow", 15),
    ),
    (
        "Passer domesticus:3",
        "Passer domesticus",
        "House Sparrow",
        "common",
        34.05,
        -118.25,
        0.89,
        photo("sparrow", 16),
    ),
]


async def resolve_user_id(email: str, password: str) -> str:
    """Sign in, registering first if the account is new, and return the Supabase user id."""
    if not settings.supabase_anon_key:
        raise SystemExit("SUPABASE_ANON_KEY is not set in backend/.env")

    headers = {"apikey": settings.supabase_anon_key}
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        # Signing up an existing address returns an error we can safely ignore; the
        # sign-in below is what actually decides whether the credentials work.
        await client.post(
            f"{settings.supabase_url}/auth/v1/signup",
            headers=headers,
            json={"email": email, "password": password},
        )

        resp = await client.post(
            f"{settings.supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers=headers,
            json={"email": email, "password": password},
        )

    if resp.status_code != 200:
        detail = resp.json().get("error_description") or resp.json().get("msg") or resp.text
        raise SystemExit(
            f"Could not sign in as {email}: {detail}\n"
            "If this says the email is not confirmed, turn off email confirmation in "
            "Supabase -> Authentication -> Providers -> Email, or confirm the address first."
        )

    return resp.json()["user"]["id"]


async def seed(email: str, password: str) -> None:
    owner_id = uuid.UUID(await resolve_user_id(email, password))
    print(f"{email} -> {owner_id}")

    async with AsyncSessionLocal() as db:
        # captures.owner_id references users.id, so the row has to exist first. Nothing
        # else creates it until the player opens their wallet.
        user = await db.get(User, owner_id)
        if user is None:
            user = User(id=owner_id, display_name=email.split("@")[0], wallet_balance=0)
            db.add(user)
            await db.flush()
            print("created users row")

        now = datetime.utcnow()
        inserted = 0
        updated = 0
        earned = 0

        for i, (sample_key, species, common, tier, lat, lng, confidence, image_url) in enumerate(
            SAMPLE_CAPTURES
        ):
            capture_id = uuid.uuid5(SEED_NAMESPACE, f"{owner_id}:{sample_key}")
            existing = (
                await db.execute(select(Capture).where(Capture.id == capture_id))
            ).scalar_one_or_none()

            if existing is not None:
                # Backfill fields added after this row was first seeded, so re-running
                # updates old rows in place instead of leaving them half-populated.
                # No coins here: they were credited when the row was inserted, and
                # paying again for the same capture would inflate the wallet on every run.
                if existing.common_name != common:
                    existing.common_name = common
                    updated += 1
                continue

            db.add(
                Capture(
                    id=capture_id,
                    owner_id=owner_id,
                    species_id=species,
                    common_name=common,
                    image_url=image_url,
                    rarity_tier=tier,
                    lat=lat,
                    lng=lng,
                    confidence_score=confidence,
                    confirmed_by_user=False,
                    captured_at=now - timedelta(days=i),
                )
            )
            inserted += 1
            # Credit what the real capture path would have paid, so the wallet matches
            # the collection instead of being a number from nowhere.
            earned += COIN_VALUES.get(tier, 0) if tier else 0

        if inserted:
            user.wallet_balance = (user.wallet_balance or 0) + earned
        await db.commit()

    print(f"inserted {inserted} capture(s), updated {updated}, credited {earned} coins")
    if inserted == 0 and updated == 0:
        print("(already seeded -- nothing to do)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.password))


if __name__ == "__main__":
    main()
