import random
import pytest

from app.services.battle_resolution import (
    RARITY_BASE_POWER,
    TRAITS,
    TRAIT_ADVANTAGE,
    battle_reward,
    resolve_battle,
    trait_advantage,
    trait_for_species,
)

# Owner: Person C — Battle System
# Pure resolution logic only: no DB, no HTTP. The endpoint that wraps this is covered in
# test_battles_api.py.


class FixedRandom(random.Random):
    """Fabricated RNG stub: returns a scripted sequence of randint() results."""

    def __init__(self, rolls: list[int]):
        super().__init__()
        self._rolls = list(rolls)

    def randint(self, a, b):
        return self._rolls.pop(0)


# --- Rarity ----------------------------------------------------------------------


def test_legendary_beats_common_even_on_a_low_roll():
    rng = FixedRandom([1, 20])  # challenger rolls 1, opponent rolls 20
    result = resolve_battle("legendary", "common", rng=rng)
    assert result["winner"] == "challenger"
    assert result["challenger_total"] == 61
    assert result["opponent_total"] == 30


def test_common_can_upset_uncommon_on_a_high_roll():
    rng = FixedRandom([20, 1])  # challenger rolls max, opponent rolls min
    result = resolve_battle("common", "uncommon", rng=rng)
    assert result["winner"] == "challenger"
    assert result["challenger_total"] == 30
    assert result["opponent_total"] == 21


def test_tie_is_broken_by_extra_coin_flip_roll():
    rng = FixedRandom([10, 10, 0])  # equal totals, then coin flip picks challenger
    result = resolve_battle("common", "common", rng=rng)
    assert result["challenger_total"] == result["opponent_total"]
    assert result["winner"] == "challenger"

    rng = FixedRandom([10, 10, 1])  # same tie, coin flip picks opponent
    result = resolve_battle("common", "common", rng=rng)
    assert result["winner"] == "opponent"


def test_unknown_rarity_tier_falls_back_to_common_power():
    rng = FixedRandom([5, 5, 0])
    result = resolve_battle("mythical-typo", "common", rng=rng)
    assert result["challenger_total"] == result["opponent_total"]


@pytest.mark.parametrize("tier", ["common", "uncommon", "rare", "legendary"])
def test_result_always_names_a_winner(tier):
    rng = FixedRandom([1, 1, 0])
    result = resolve_battle(tier, tier, rng=rng)
    assert result["winner"] in ("challenger", "opponent")


# --- Traits ----------------------------------------------------------------------


def test_a_species_always_gets_the_same_trait():
    # The trait is never stored, so it has to be reproducible from the name alone --
    # otherwise a capture's matchups would change under the player. blake2b rather than
    # hash() is what makes this hold across processes; with hash() it would pass inside
    # one run and break on restart.
    assert trait_for_species("Vulpes vulpes") == trait_for_species("Vulpes vulpes")


def test_trait_lookup_ignores_case_and_whitespace():
    assert trait_for_species("  vulpes VULPES ") == trait_for_species("Vulpes vulpes")


def test_unidentified_species_has_no_trait():
    assert trait_for_species(None) is None
    assert trait_for_species("") is None


def test_traits_are_spread_across_the_cycle():
    # A hash that bucketed every real species into one trait would compile and pass every
    # other test here while making counterplay do nothing at all.
    species = [
        "Vulpes vulpes", "Bubo scandiacus", "Danaus plexippus", "Panthera pardus",
        "Passer domesticus", "Canis lupus", "Sciurus carolinensis", "Cardinalis cardinalis",
        "Ursus americanus", "Puma concolor", "Grus americana", "Turdus merula",
    ]
    assert len({trait_for_species(s) for s in species}) == 3


def test_the_trait_cycle_has_no_dominant_trait():
    # Every trait beats exactly one and loses to exactly one. A trait that beat both
    # others would just be a second rarity ladder, and one that beat neither would be
    # dead weight -- either way the mechanic stops being counterplay.
    for trait in TRAITS:
        others = [o for o in TRAITS if o != trait]
        beaten = [o for o in others if trait_advantage(trait, o) == "challenger"]
        lost_to = [o for o in others if trait_advantage(trait, o) == "opponent"]
        assert len(beaten) == 1 and len(lost_to) == 1


def test_same_trait_gives_neither_side_an_edge():
    assert trait_advantage("ferocity", "ferocity") is None


def test_missing_trait_gives_neither_side_an_edge():
    # An unidentified capture does not hand its opponent a free bonus, and does not get one.
    assert trait_advantage(None, "ferocity") is None
    assert trait_advantage("ferocity", None) is None


# --- Counterplay in a real matchup ------------------------------------------------


def test_trait_advantage_adds_its_bonus_and_is_reported():
    rng = FixedRandom([5, 5])
    result = resolve_battle("common", "common", "ferocity", "guile", rng=rng)  # ferocity beats guile

    assert result["trait_advantage"] == "challenger"
    assert result["challenger_total"] == RARITY_BASE_POWER["common"] + 5 + TRAIT_ADVANTAGE
    assert result["opponent_total"] == RARITY_BASE_POWER["common"] + 5
    assert result["winner"] == "challenger"


def test_counterplay_lets_one_rarity_tier_be_played_around():
    # The whole point of the mechanic: a rare with the right trait can take a legendary.
    # rare(35) + 25 = 60 = legendary(60), so the roll decides.
    rng = FixedRandom([20, 1])
    result = resolve_battle("rare", "legendary", "guile", "resilience", rng=rng)  # guile beats resilience

    assert result["trait_advantage"] == "challenger"
    assert result["winner"] == "challenger"


def test_counterplay_cannot_close_a_three_tier_gap():
    # Rarity still has to mean something. A common with the trait advantage and a maximum
    # roll is 10+25+20 = 55, under a legendary's worst case of 60+1 = 61.
    rng = FixedRandom([20, 1])
    result = resolve_battle("common", "legendary", "ferocity", "guile", rng=rng)

    assert result["trait_advantage"] == "challenger"
    assert result["winner"] == "opponent"


def test_no_trait_advantage_is_reported_as_none():
    rng = FixedRandom([5, 5, 0])
    assert resolve_battle("common", "common", "guile", "guile", rng=rng)["trait_advantage"] is None


def test_rolls_are_drawn_in_a_fixed_order_regardless_of_traits():
    # Both rolls are taken before any branching. If a future change drew them lazily, the
    # RNG sequence would depend on the matchup and a battle could not be replayed.
    with_traits = resolve_battle("common", "common", "ferocity", "guile", rng=FixedRandom([3, 7]))
    without = resolve_battle("common", "common", rng=FixedRandom([3, 7, 0]))

    assert (with_traits["challenger_roll"], with_traits["opponent_roll"]) == (3, 7)
    assert (without["challenger_roll"], without["opponent_roll"]) == (3, 7)


# --- Payout ----------------------------------------------------------------------


def test_reward_scales_with_the_defeated_capture():
    # Beating a legendary is the achievement; beating a sparrow is not.
    assert battle_reward("legendary") > battle_reward("rare") > battle_reward("uncommon") > battle_reward("common")


def test_battle_rewards_stay_below_capture_payouts():
    # Battles are repeatable from the couch, captures require going outside -- which is
    # the entire premise of the app. If a battle win ever out-earned photographing the
    # same tier, the optimal way to play would be to stop playing outdoors.
    from app.services.rarity import COIN_VALUES

    for tier, capture_value in COIN_VALUES.items():
        assert battle_reward(tier) < capture_value


def test_beating_an_unscored_capture_still_pays_something():
    # Otherwise players learn to dodge opponents whose species lookup failed, which is
    # not something they did wrong.
    assert battle_reward(None) > 0
