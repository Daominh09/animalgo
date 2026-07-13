# Owner: Person B — Rarity Engine & Collection
# Week 2: replace with the real regionally-weighted scoring formula and fuzzing logic

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
