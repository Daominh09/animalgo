# Owner: Person B — Rarity Engine & Collection
# Week 2: replace with the real regionally-weighted scoring formula and fuzzing logic
#
# DELIBERATE: occurrence_count is US-only, so a species that is abundant elsewhere but
# barely recorded in the US scores as legendary. Example — Eurasian Blackbird
# (Turdus merula): 7 US records but 13.4M globally, so it scores legendary, the same as
# an endangered tiger. That is intended: this is a location-based game, and finding a
# bird that does not belong here IS the trophy moment. Do not "fix" it by switching to
# global counts without a team decision.
#
# Two consequences to keep in view:
#   - It is an exploit vector. Photographing a foreign species off a screen or in a zoo
#     mints 500 coins, and those are the easiest shots to fake. Anti-cheat (Person D:
#     live-camera enforcement, duplicate-image hashing) is what limits this, not the
#     scoring.
#   - Revisit at the Week 3 balance checkpoint ("adjust regional weighting based on
#     Week 2's spot-check flags") if payouts feel wrong in playtesting.

SENSITIVE_STATUSES = {"VU", "EN", "CR"}


def score_rarity(occurrence_count: int, iucn_status: str) -> tuple[str, int]:
    """Returns (rarity_tier, coin_value)."""
    if iucn_status in SENSITIVE_STATUSES or occurrence_count < 10:
        return "legendary", 500
    if occurrence_count < 100:
        return "rare", 100
    if occurrence_count < 1000:
        return "uncommon", 25
    return "common", 5


def fuzz_coordinates(lat: float, lng: float, iucn_status: str) -> tuple[float | None, float | None]:
    """TODO: implement real fuzzing (e.g. round to ~1 decimal degree) for sensitive species.
    Withholding entirely (None, None) is the safe placeholder default."""
    if iucn_status in SENSITIVE_STATUSES:
        return None, None
    return lat, lng
