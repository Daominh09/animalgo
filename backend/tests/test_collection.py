import uuid
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Capture
from app.routers import collection

# Owner: Person B — Rarity Engine & Collection
# Ordering and shaping only. The DB session is faked, so no Postgres is needed.

USER_ID = "8f14e45f-ceea-467a-9c1e-1a1b2c3d4e5f"


def _capture(tier, day, species="Passer domesticus", common="House Sparrow"):
    return Capture(
        id=uuid.uuid4(),
        owner_id=uuid.UUID(USER_ID),
        species_id=species,
        common_name=common,
        image_url="https://r2.test/photo.jpg",
        rarity_tier=tier,
        lat=39.85,
        lng=-98.55,
        confidence_score=0.9,
        confirmed_by_user=False,
        captured_at=datetime(2026, 8, day),
    )


def _client(rows):
    class _Result:
        def scalars(self):
            return self

        def all(self):
            return rows

    class _Session:
        async def execute(self, stmt):
            return _Result()

    app = FastAPI()
    app.include_router(collection.router)
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: _Session()
    return TestClient(app)


def test_rarest_first():
    # Alphabetical order would put common first, which is why the ranking is explicit.
    rows = [_capture("common", 1), _capture("legendary", 2), _capture("uncommon", 3), _capture("rare", 4)]

    body = _client(rows).get("/collection").json()

    assert [c["rarity_tier"] for c in body] == ["legendary", "rare", "uncommon", "common"]


def test_newest_first_within_a_tier():
    rows = [_capture("rare", 1), _capture("rare", 9), _capture("rare", 5)]

    body = _client(rows).get("/collection").json()

    assert [c["captured_at"][:10] for c in body] == ["2026-08-09", "2026-08-05", "2026-08-01"]


def test_unknown_rarity_sorts_last():
    # A capture whose rarity never resolved must not outrank a legendary one just
    # because its tier is missing.
    rows = [_capture(None, 9), _capture("common", 1)]

    body = _client(rows).get("/collection").json()

    assert [c["rarity_tier"] for c in body] == ["common", None]


def test_empty_collection_is_an_empty_list():
    assert _client([]).get("/collection").json() == []


def test_common_name_is_returned_for_the_card():
    body = _client([_capture("common", 1, common="House Sparrow")]).get("/collection").json()

    assert body[0]["common_name"] == "House Sparrow"
    assert body[0]["species_id"] == "Passer domesticus"  # still there, for the detail view


def test_missing_common_name_is_null_not_omitted():
    # Rows written before common_name existed, and family-level identifications. The app
    # falls back to species_id, so the key has to be present rather than absent.
    body = _client([_capture("common", 1, species="Troglodytidae", common=None)]).get("/collection").json()

    assert body[0]["common_name"] is None


def test_card_carries_what_the_screen_needs():
    body = _client([_capture("rare", 1)]).get("/collection").json()

    assert set(body[0]) == {
        "id", "common_name", "species_id", "image_url", "rarity_tier",
        "lat", "lng", "confidence_score", "confirmed_by_user", "captured_at",
    }
    # Already-fuzzed coordinates; nothing to strip here.
    assert (body[0]["lat"], body[0]["lng"]) == (39.85, -98.55)
