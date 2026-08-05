import asyncio

from app.services import species

# Owner: Person B — Rarity Engine & Collection
# Tests for the A -> B hand-off: an identified species triggering the GBIF + IUCN
# lookup and scoring. The lookups are faked, so no network is needed. Coroutines are
# driven with asyncio.run() to avoid a pytest-asyncio dependency.


def _patch_lookups(monkeypatch, count=500, status="LC", fail=False):
    calls = {"gbif": 0, "iucn": 0}

    async def fake_gbif(name, region="US"):
        calls["gbif"] += 1
        if fail:
            raise RuntimeError("GBIF unavailable")
        return count

    async def fake_iucn(name):
        calls["iucn"] += 1
        return status

    monkeypatch.setattr(species, "get_gbif_occurrence_count", fake_gbif)
    monkeypatch.setattr(species, "get_iucn_status", fake_iucn)
    return calls


def test_lookup_triggered_and_scored(monkeypatch):
    calls = _patch_lookups(monkeypatch, count=500, status="LC")

    out = asyncio.run(species.resolve_species_rarity("Passer domesticus", "House Sparrow"))

    assert calls == {"gbif": 1, "iucn": 1}  # the hand-off fires both lookups
    assert out["rarity_tier"] == "rare"  # 500 occurrences -> rare
    assert out["coin_value"] == 200
    assert out["species_id"] == "Passer domesticus"
    assert out["common_name"] == "House Sparrow"


def test_every_tier_is_reachable_with_real_counts(monkeypatch):
    # The first threshold set (10/100/1000) scored every unlisted species "common",
    # because real US counts start in the tens of thousands. These are the actual
    # numbers from the Week 2 spot-check, so a regression collapses the tiers again.
    observed = [
        (7, "legendary"),        # Eurasian Blackbird, a vagrant
        (11_553, "rare"),        # Mountain Lion
        (41_892, "uncommon"),    # American Black Bear
        (24_852_472, "common"),  # Northern Cardinal
    ]
    for count, expected in observed:
        _patch_lookups(monkeypatch, count=count, status="LC")
        out = asyncio.run(species.resolve_species_rarity("Test species"))
        assert out["rarity_tier"] == expected, count


def test_sensitive_status_is_legendary(monkeypatch):
    _patch_lookups(monkeypatch, count=1_000_000, status="EN")

    out = asyncio.run(species.resolve_species_rarity("Panthera tigris", "Tiger"))

    # IUCN status outranks abundance: an endangered species is legendary even when
    # occurrence records are plentiful. This is the one-way override -- status can
    # promote to legendary but never demote.
    assert out["iucn_status"] == "EN"
    assert out["rarity_tier"] == "legendary"
    assert out["coin_value"] == 500


def test_payout_spread_stays_playable(monkeypatch):
    # The gap between the cheapest and dearest capture is a balance decision, not an
    # accident. At 100x, a walk that turned up nothing rare felt wasted. Pinning it here
    # so a future threshold tweak can't quietly widen it again.
    from app.services import rarity as rarity_module

    values = rarity_module.COIN_VALUES
    assert values["legendary"] / values["common"] == 20
    assert values["common"] * 10 > values["rare"]  # ten ordinary captures beat one rare


def test_locally_rare_species_is_legendary(monkeypatch):
    # Deliberate behaviour: occurrence counts are US-only, so a species that is abundant
    # abroad but barely recorded here scores legendary (e.g. Eurasian Blackbird, 7 US
    # records vs 13.4M globally). See the note in app/services/rarity.py.
    _patch_lookups(monkeypatch, count=7, status="LC")

    out = asyncio.run(species.resolve_species_rarity("Turdus merula", "Eurasian Blackbird"))

    assert out["rarity_tier"] == "legendary"


# --- fail-safe behaviour -------------------------------------------------------------
# An unresolved species must be "unknown", never scored. score_rarity(0, "NE") returns
# "legendary", so silently falling through would award 500 coins for every capture.


def test_no_scientific_name_returns_unknown(monkeypatch):
    calls = _patch_lookups(monkeypatch)

    assert asyncio.run(species.resolve_species_rarity(None, "House Sparrow")) is None
    assert calls == {"gbif": 0, "iucn": 0}  # nothing looked up


def test_no_animal_returns_unknown(monkeypatch):
    calls = _patch_lookups(monkeypatch)

    assert asyncio.run(species.resolve_species_rarity("none", "none")) is None
    assert calls == {"gbif": 0, "iucn": 0}


def test_upstream_failure_returns_unknown_not_legendary(monkeypatch):
    _patch_lookups(monkeypatch, fail=True)

    out = asyncio.run(species.resolve_species_rarity("Passer domesticus", "House Sparrow"))

    assert out is None  # NOT a scored tier
