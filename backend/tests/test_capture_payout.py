import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.routers import captures

# Owner: Person B — the B -> D hand-off.
# Vision, storage, rarity and the wallet are all faked, so no network, no DB, no
# credentials. What's under test is the payout decision, not anyone else's code.

USER_ID = "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f"
PHOTO = {"file": ("bird.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}


@pytest.fixture
def credits(monkeypatch):
    """Records every credit_wallet call the endpoint makes."""
    calls = []

    async def fake_credit(db, user_id, amount, reason):
        calls.append({"user_id": str(user_id), "amount": amount, "reason": reason})
        return amount

    monkeypatch.setattr(captures, "credit_wallet", fake_credit)
    return calls


@pytest.fixture
def client(monkeypatch):
    async def fake_identify(image_bytes, mime_type="image/jpeg"):
        return {"species": "House Sparrow", "scientific_name": "Passer domesticus", "confidence": 0.9}

    monkeypatch.setattr(captures.vision, "identify_species", fake_identify)
    monkeypatch.setattr(captures.storage, "upload_bytes", lambda key, data: f"https://r2.test/{key}")

    app = FastAPI()
    app.include_router(captures.router)
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _rarity(monkeypatch, result):
    async def fake_resolve(scientific_name, common_name=None):
        return result

    monkeypatch.setattr(captures.species, "resolve_species_rarity", fake_resolve)


SCORED = {
    "species_id": "Passer domesticus",
    "common_name": "House Sparrow",
    "gbif_occurrence_count": 500,
    "iucn_status": "LC",
    "rarity_tier": "uncommon",
    "coin_value": 25,
}


def test_scored_capture_pays_its_coin_value(monkeypatch, client, credits):
    _rarity(monkeypatch, SCORED)

    body = client.post("/captures/detect-and-store", files=PHOTO).json()

    assert body["coins_awarded"] == 25
    assert credits == [{"user_id": USER_ID, "amount": 25, "reason": "capture:uncommon"}]


def test_unknown_rarity_pays_nothing(monkeypatch, client, credits):
    # The whole point of rarity being None: an unresolved species must not mint coins.
    # score_rarity(0, ...) would call it legendary, so paying on unknown pays 500.
    _rarity(monkeypatch, None)

    body = client.post("/captures/detect-and-store", files=PHOTO).json()

    assert body["coins_awarded"] is None
    assert credits == []  # the wallet is never touched


def test_capture_survives_a_wallet_failure(monkeypatch, client):
    # The photo is already in R2 by this point. A 500 here would cost the player their
    # capture as well as their coins, and their retry would re-run vision and re-upload.
    _rarity(monkeypatch, SCORED)

    async def boom(db, user_id, amount, reason):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(captures, "credit_wallet", boom)

    resp = client.post("/captures/detect-and-store", files=PHOTO)

    assert resp.status_code == 200
    assert resp.json()["image_url"].startswith("https://r2.test/")
    assert resp.json()["coins_awarded"] is None  # reported honestly, not assumed paid


def test_coordinates_are_fuzzed_before_they_are_returned(monkeypatch, client, credits):
    _rarity(monkeypatch, SCORED)

    body = client.post(
        "/captures/detect-and-store?lat=39.8283&lng=-98.5795", files=PHOTO
    ).json()

    assert body["location"] == {"lat": 39.85, "lng": -98.55}


def test_oversized_upload_is_rejected_before_anything_is_paid(monkeypatch, client, credits):
    _rarity(monkeypatch, SCORED)
    oversized = {"file": ("big.jpg", io.BytesIO(b"x" * (captures.MAX_UPLOAD_BYTES + 1)), "image/jpeg")}

    resp = client.post("/captures/detect-and-store", files=oversized)

    assert resp.status_code == 413
    assert credits == []
