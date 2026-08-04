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
    assert out["rarity_tier"] == "uncommon"  # 500 occurrences -> uncommon
    assert out["coin_value"] == 25
    assert out["species_id"] == "Passer domesticus"
    assert out["common_name"] == "House Sparrow"


def test_sensitive_status_is_legendary(monkeypatch):
    _patch_lookups(monkeypatch, count=1_000_000, status="EN")

    out = asyncio.run(species.resolve_species_rarity("Panthera tigris", "Tiger"))

    # IUCN status outranks abundance: an endangered species is legendary even when
    # occurrence records are plentiful. This is the one-way override -- status can
    # promote to legendary but never demote.
    assert out["iucn_status"] == "EN"
    assert out["rarity_tier"] == "legendary"
    assert out["coin_value"] == 500


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
