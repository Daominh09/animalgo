import random

# Owner: Person C — Battle System
# Week 1: pure resolution function, unit-tested against fabricated inputs only.
# Week 2: wire into POST /battles/challenge + GET /battles/{id} against real captures.

RARITY_BASE_POWER = {
    "common": 10,
    "uncommon": 20,
    "rare": 35,
    "legendary": 60,
}

STAT_ROLL_RANGE = (1, 20)


def resolve_battle(
    challenger_rarity_tier: str,
    opponent_rarity_tier: str,
    rng: random.Random | None = None,
) -> dict:
    """Resolves a battle between two captures' rarity tiers.

    Each side's power is its rarity tier's base power plus a random stat roll.
    Higher total wins; ties favor neither side and are resolved by an extra
    coin-flip roll so a winner is always returned.

    Pure function: takes an optional injected `random.Random` so tests can
    fabricate deterministic rolls without touching real capture data.
    """
    rng = rng or random.Random()

    challenger_base = RARITY_BASE_POWER.get(challenger_rarity_tier, RARITY_BASE_POWER["common"])
    opponent_base = RARITY_BASE_POWER.get(opponent_rarity_tier, RARITY_BASE_POWER["common"])

    challenger_roll = rng.randint(*STAT_ROLL_RANGE)
    opponent_roll = rng.randint(*STAT_ROLL_RANGE)

    challenger_total = challenger_base + challenger_roll
    opponent_total = opponent_base + opponent_roll

    if challenger_total == opponent_total:
        winner = "challenger" if rng.randint(0, 1) == 0 else "opponent"
    else:
        winner = "challenger" if challenger_total > opponent_total else "opponent"

    return {
        "winner": winner,
        "challenger_total": challenger_total,
        "opponent_total": opponent_total,
        "challenger_roll": challenger_roll,
        "opponent_roll": opponent_roll,
    }
