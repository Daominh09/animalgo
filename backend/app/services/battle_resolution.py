import hashlib
import random

# Owner: Person C — Battle System
#
# Pure resolution logic. No DB, no network, no clock: everything this module needs is
# passed in, and the RNG is injectable, so a battle can be replayed exactly in a test.
# The router (app/routers/battles.py) is what talks to Postgres and the wallet.

RARITY_BASE_POWER = {
    "common": 10,
    "uncommon": 20,
    "rare": 35,
    "legendary": 60,
}

STAT_ROLL_RANGE = (1, 20)

# --- Counterplay -----------------------------------------------------------------
#
# Week 3 asked for "a counterplay mechanic so rarity alone doesn't determine outcomes".
# Rarity still decides most matchups -- it is what the whole capture loop is about, and a
# legendary that could lose to a sparrow would make finding one feel worthless. What this
# adds is a reason to keep a VARIED roster instead of only ever fielding your single
# rarest capture.
#
# Every species has one of three traits, in a rock-paper-scissors cycle. The trait is
# derived from the species name (see trait_for_species), so it is stable forever: a
# player who learns that foxes are Guile can rely on it, and nothing in the DB has to
# store it.
FEROCITY = "ferocity"
GUILE = "guile"
RESILIENCE = "resilience"

TRAITS = (FEROCITY, GUILE, RESILIENCE)

# trait -> the trait it beats.
BEATS = {FEROCITY: GUILE, GUILE: RESILIENCE, RESILIENCE: FEROCITY}

# Size of the counterplay swing, chosen against the rarity gaps rather than picked round:
#
#   legendary(60) vs rare(35)      gap 25 -> advantage exactly closes it, roll decides
#   legendary(60) vs uncommon(20)  gap 40 -> 15 behind, a top roll can still steal it
#   legendary(60) vs common(10)    gap 50 -> 25 behind, unreachable (max roll gap is 19)
#
# So a trait advantage is worth roughly one rarity tier. One tier of rarity can be played
# around; three cannot. That is the intended shape -- do not raise this without re-reading
# those gaps, since +30 would let a common beat a legendary on a good roll.
TRAIT_ADVANTAGE = 25


def trait_for_species(species_id: str | None) -> str | None:
    """The battle trait for a species, derived from its name.

    Deterministic and stable: the same species always has the same trait, on every
    machine and across restarts, so players can learn matchups. Uses blake2b rather than
    hash() because Python salts hash() per process -- with the builtin, a species' trait
    would silently change every time the API restarted.

    None for a capture whose species never resolved; such a capture fights with no trait
    and neither gains nor grants an advantage.
    """
    if not species_id:
        return None
    digest = hashlib.blake2b(species_id.strip().lower().encode(), digest_size=8).digest()
    return TRAITS[int.from_bytes(digest, "big") % len(TRAITS)]


def trait_advantage(challenger_trait: str | None, opponent_trait: str | None) -> str | None:
    """Which side the trait matchup favours: "challenger", "opponent", or None.

    None covers three different cases that all mean "no bonus": same trait, either side
    unidentified, and a trait string we don't recognise.
    """
    if challenger_trait is None or opponent_trait is None:
        return None
    if BEATS.get(challenger_trait) == opponent_trait:
        return "challenger"
    if BEATS.get(opponent_trait) == challenger_trait:
        return "opponent"
    return None


def resolve_battle(
    challenger_rarity_tier: str,
    opponent_rarity_tier: str,
    challenger_trait: str | None = None,
    opponent_trait: str | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Resolves a battle between two captures.

    Each side's power is its rarity tier's base power, plus a random stat roll, plus the
    counterplay bonus if its trait beats the other's. Higher total wins; an exact tie is
    broken by one extra coin-flip roll so a winner is always named -- a battle that
    resolved to "nobody" would leave the challenge in limbo with no screen to show.

    Traits default to None so a caller that only has rarity tiers (and the Week 1 tests)
    gets the original rarity-only behaviour.

    Pure: pass an injected `random.Random` to replay an exact sequence of rolls.
    """
    rng = rng or random.Random()

    # .get with a fallback rather than [] on purpose: a tier string this module doesn't
    # know (a typo, or a tier Person B adds later) must not 500 a battle mid-flight. It
    # fights as a common, which is the weakest assumption available and so can't be used
    # to smuggle in a strong capture.
    challenger_base = RARITY_BASE_POWER.get(challenger_rarity_tier, RARITY_BASE_POWER["common"])
    opponent_base = RARITY_BASE_POWER.get(opponent_rarity_tier, RARITY_BASE_POWER["common"])

    # Both rolls are drawn before any branching, so the RNG is consumed in a fixed order
    # regardless of the matchup. Tests depend on that: FixedRandom scripts the sequence.
    challenger_roll = rng.randint(*STAT_ROLL_RANGE)
    opponent_roll = rng.randint(*STAT_ROLL_RANGE)

    advantage = trait_advantage(challenger_trait, opponent_trait)
    challenger_bonus = TRAIT_ADVANTAGE if advantage == "challenger" else 0
    opponent_bonus = TRAIT_ADVANTAGE if advantage == "opponent" else 0

    challenger_total = challenger_base + challenger_roll + challenger_bonus
    opponent_total = opponent_base + opponent_roll + opponent_bonus

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
        # Which side the trait cycle favoured, so the result screen can explain an upset
        # instead of showing two numbers and leaving the player to guess.
        "trait_advantage": advantage,
    }


# --- Payout ----------------------------------------------------------------------
#
# Keyed on the DEFEATED capture's tier: beating a legendary is the achievement, beating a
# sparrow is not.
#
# Deliberately about a fifth of the capture payouts in app/services/rarity.py
# (500/200/75/25). Battles are repeatable from the couch; captures require going outside
# and finding an animal, which is the entire point of the app. If beating a legendary
# paid what photographing one pays, the optimal way to play would be to stop going
# outside -- so these numbers are what keep the core loop the best way to earn.
BATTLE_REWARDS = {"legendary": 100, "rare": 40, "uncommon": 15, "common": 5}

# Paid when the loser's capture has no resolved rarity. Matches the "common" reward
# rather than paying nothing, so an opponent whose species lookup failed is still worth
# fighting -- otherwise players would learn to dodge those matchups.
UNKNOWN_TIER_REWARD = 5


def battle_reward(loser_rarity_tier: str | None) -> int:
    """Coins the winner earns for beating a capture of this tier."""
    if loser_rarity_tier is None:
        return UNKNOWN_TIER_REWARD
    return BATTLE_REWARDS.get(loser_rarity_tier, UNKNOWN_TIER_REWARD)
