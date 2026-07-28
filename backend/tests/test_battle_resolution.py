import random
import pytest

from app.services.battle_resolution import resolve_battle


class FixedRandom(random.Random):
    """Fabricated RNG stub: returns a scripted sequence of randint() results."""

    def __init__(self, rolls: list[int]):
        super().__init__()
        self._rolls = list(rolls)

    def randint(self, a, b):
        return self._rolls.pop(0)


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
