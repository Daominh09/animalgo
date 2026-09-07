import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Base, Battle, Capture, User
from app.routers import battles
from app.services.battle_resolution import battle_reward

# Owner: Person C — Battle System
#
# These run against a real (temp-file SQLite) database rather than a faked session,
# unlike the other routers' tests. That is deliberate: what is under test here is
# transaction behaviour -- the conditional-UPDATE claim that stops a battle resolving
# twice, rowcount, and the commit ordering that keeps a payout from being applied twice.
# A stubbed session would assert that the code calls the methods it calls, which is the
# one thing that cannot go wrong here.
#
# Only push is faked (no network) and, where a test is about failure handling, the wallet.

ALICE = uuid.UUID("11111111-1111-1111-1111-111111111111")
BOB = uuid.UUID("22222222-2222-2222-2222-222222222222")
CAROL = uuid.UUID("33333333-3333-3333-3333-333333333333")

# A legendary against a common is decided before the dice are thrown: the 50-point base
# gap is larger than the biggest possible swing (a 25 trait bonus plus a 19 roll
# difference). Every test below that needs a known winner uses that matchup, so the real
# resolve_battle runs with real randomness and the assertion still holds every time.
LEGENDARY = ("Panthera pardus", "Amur Leopard", "legendary")
COMMON = ("Passer domesticus", "House Sparrow", "common")


class World:
    """The seeded database, the client, and the knobs a test needs to drive it."""

    def __init__(self, client, session_factory, viewer, pushes):
        self.client = client
        self.session_factory = session_factory
        self._viewer = viewer
        self.pushes = pushes

    def as_user(self, user_id: uuid.UUID) -> None:
        self._viewer["id"] = str(user_id)

    def read(self, coro_fn):
        """Runs a coroutine against a fresh session, for asserting on the DB directly."""

        async def run():
            async with self.session_factory() as session:
                return await coro_fn(session)

        return asyncio.run(run())

    def balance(self, user_id: uuid.UUID) -> int:
        return self.read(lambda s: s.get(User, user_id)).wallet_balance

    def battle_row(self, battle_id: str) -> Battle:
        return self.read(lambda s: s.get(Battle, uuid.UUID(battle_id)))


def _capture(owner: uuid.UUID, spec, captured_day: int = 1) -> Capture:
    species_id, common_name, tier = spec
    return Capture(
        id=uuid.uuid4(),
        owner_id=owner,
        species_id=species_id,
        common_name=common_name,
        image_url=f"https://r2.test/{uuid.uuid4()}.jpg",
        rarity_tier=tier,
        lat=39.85,
        lng=-98.55,
        confidence_score=0.9,
        confirmed_by_user=True,
        captured_at=datetime(2026, 8, captured_day),
    )


@pytest.fixture
def world(tmp_path, monkeypatch):
    # A temp file rather than :memory:, and NullPool rather than a shared connection:
    # TestClient runs the app on its own event loop in another thread, and a pooled
    # in-memory SQLite connection created during setup cannot be reused there.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            session.add_all(
                [
                    User(id=ALICE, display_name="Alice", wallet_balance=0, push_token="ExponentPushToken[alice]"),
                    User(id=BOB, display_name="Bob", wallet_balance=0, push_token="ExponentPushToken[bob]"),
                    User(id=CAROL, display_name="Carol", wallet_balance=0),  # no captures, no push token
                ]
            )
            await session.commit()

    asyncio.run(setup())

    pushes = []

    async def fake_send_push(messages):
        pushes.extend(messages)
        return len(messages)

    monkeypatch.setattr(battles.push, "send_push", fake_send_push)

    viewer = {"id": str(ALICE)}

    async def override_db():
        async with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(battles.router)
    app.dependency_overrides[get_current_user_id] = lambda: viewer["id"]
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        yield World(client, session_factory, viewer, pushes)

    asyncio.run(engine.dispose())


def _add(world, *objects):
    async def run():
        async with world.session_factory() as session:
            session.add_all(objects)
            await session.commit()

    asyncio.run(run())


def _seed_matchup(world):
    """Alice holds a legendary, Bob a common. Alice always wins this one."""
    alice_cap = _capture(ALICE, LEGENDARY)
    bob_cap = _capture(BOB, COMMON)
    _add(world, alice_cap, bob_cap)
    return alice_cap, bob_cap


def _challenge(world, capture_id, opponent_id=BOB):
    return world.client.post(
        "/battles/challenge",
        json={"opponent_id": str(opponent_id), "capture_id": str(capture_id)},
    )


# --- Roster ----------------------------------------------------------------------


def test_roster_returns_only_my_captures_with_their_traits(world):
    alice_cap, _bob_cap = _seed_matchup(world)

    body = world.client.get("/battles/roster").json()

    assert [c["id"] for c in body] == [str(alice_cap.id)]
    assert body[0]["trait"] in ("ferocity", "guile", "resilience")
    assert body[0]["rarity_tier"] == "legendary"


def test_roster_includes_captures_whose_rarity_never_resolved(world):
    # They fight as commons. Excluding them would leave a player whose lookups all failed
    # with an empty roster and no way into the game at all.
    _add(world, _capture(ALICE, ("Troglodytidae", None, None)))

    body = world.client.get("/battles/roster").json()

    assert len(body) == 1
    assert body[0]["rarity_tier"] is None


def test_roster_does_not_leak_capture_coordinates(world):
    # A battle card ends up on another player's screen. Locations, fuzzed or not, are not
    # part of a matchup.
    _seed_matchup(world)

    body = world.client.get("/battles/roster").json()

    assert "lat" not in body[0] and "lng" not in body[0]


# --- Opponents -------------------------------------------------------------------


def test_opponents_lists_other_players_who_can_actually_fight(world):
    _seed_matchup(world)

    body = world.client.get("/battles/opponents").json()

    # Bob has a capture. Alice is excluded (herself) and so is Carol, who has none and
    # could only ever let the challenge expire.
    assert [o["user_id"] for o in body] == [str(BOB)]
    assert body[0] == {"user_id": str(BOB), "display_name": "Bob", "capture_count": 1}


# --- Challenge -------------------------------------------------------------------


def test_challenge_creates_a_pending_battle_and_notifies_the_opponent(world):
    alice_cap, _ = _seed_matchup(world)

    body = _challenge(world, alice_cap.id).json()

    assert body["status"] == "pending"
    assert body["role"] == "challenger"
    assert body["challenger"]["capture"]["id"] == str(alice_cap.id)
    assert body["opponent"]["capture"] is None  # Bob has not picked yet
    assert body["outcome"] is None and body["winner_id"] is None
    assert body["expires_at"] is not None

    assert [p.token for p in world.pushes] == ["ExponentPushToken[bob]"]
    assert world.pushes[0].data == {"type": "battle", "battle_id": body["id"]}


def test_cannot_challenge_yourself(world):
    alice_cap, _ = _seed_matchup(world)

    resp = _challenge(world, alice_cap.id, opponent_id=ALICE)

    # Every battle pays its winner and every battle has a winner, so self-challenges are
    # an unlimited coin printer.
    assert resp.status_code == 400


def test_cannot_challenge_with_a_capture_you_do_not_own(world):
    _alice_cap, bob_cap = _seed_matchup(world)

    resp = _challenge(world, bob_cap.id)

    assert resp.status_code == 404


def test_challenging_an_unknown_player_is_rejected(world):
    alice_cap, _ = _seed_matchup(world)

    resp = _challenge(world, alice_cap.id, opponent_id=uuid.uuid4())

    assert resp.status_code == 404


def test_only_one_outstanding_challenge_per_opponent(world):
    # Otherwise tapping Challenge repeatedly pushes the opponent once per tap and buries
    # the challenge they might have answered.
    alice_cap, _ = _seed_matchup(world)
    assert _challenge(world, alice_cap.id).status_code == 200
    world.pushes.clear()

    second = _challenge(world, alice_cap.id)

    assert second.status_code == 409
    assert world.pushes == []


def test_a_new_challenge_is_allowed_once_the_last_one_is_settled(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/decline")

    world.as_user(ALICE)

    assert _challenge(world, alice_cap.id).status_code == 200


def test_a_missing_push_token_does_not_fail_the_challenge(world):
    # Carol never granted notification permission. She still gets challenged.
    _add(world, _capture(CAROL, COMMON))
    alice_cap, _ = _seed_matchup(world)

    resp = _challenge(world, alice_cap.id, opponent_id=CAROL)

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


# --- Accept and resolve ----------------------------------------------------------


def test_accepting_resolves_the_battle_and_pays_the_winner(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    world.as_user(BOB)
    body = world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)}).json()

    assert body["status"] == "resolved"
    assert body["winner_id"] == str(ALICE)  # legendary over common, always
    assert body["outcome"] == "lost"  # Bob is looking at it
    assert body["opponent"]["capture"]["id"] == str(bob_cap.id)
    assert body["resolved_at"] is not None
    assert body["expires_at"] is None  # no countdown on a decided battle

    reward = battle_reward("common")  # Alice beat Bob's common
    assert body["coins_awarded"] == reward
    assert world.balance(ALICE) == reward
    assert world.balance(BOB) == 0  # losing costs nothing in v1


def test_each_player_sees_the_same_numbers_from_their_own_side(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})
    bob_view = world.client.get(f"/battles/{battle_id}").json()
    world.as_user(ALICE)
    alice_view = world.client.get(f"/battles/{battle_id}").json()

    # The facts are identical...
    assert alice_view["challenger"] == bob_view["challenger"]
    assert alice_view["opponent"] == bob_view["opponent"]
    assert alice_view["winner_id"] == bob_view["winner_id"]
    # ...only the point of view differs, so each screen can say "you" without the client
    # working out which half of the row it is.
    assert (alice_view["role"], alice_view["outcome"]) == ("challenger", "won")
    assert (bob_view["role"], bob_view["outcome"]) == ("opponent", "lost")


def test_a_resolved_battle_never_re_rolls(world):
    # resolve_battle throws dice. If the result screen recomputed on read, the two players
    # would see different numbers, and one player would see new numbers every time they
    # looked at the same finished battle.
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    first = world.client.get(f"/battles/{battle_id}").json()
    second = world.client.get(f"/battles/{battle_id}").json()

    assert first == second
    assert first["challenger"]["roll"] is not None


def test_both_players_are_notified_of_the_result(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    world.pushes.clear()

    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    assert {p.token for p in world.pushes} == {"ExponentPushToken[alice]", "ExponentPushToken[bob]"}
    titles = {p.token: p.title for p in world.pushes}
    assert titles["ExponentPushToken[alice]"] == "You won!"
    assert titles["ExponentPushToken[bob]"] == "You lost"


def test_only_the_challenged_player_can_accept(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    # Alice tries to answer her own challenge.
    resp = world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(alice_cap.id)})

    assert resp.status_code == 403


def test_cannot_accept_with_a_capture_you_do_not_own(world):
    alice_cap, _bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    world.as_user(BOB)
    resp = world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(alice_cap.id)})

    assert resp.status_code == 404


def test_a_battle_cannot_be_resolved_twice(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    second = world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    assert second.status_code == 409
    # The point of the guard: the winner is paid once, not once per tap.
    assert world.balance(ALICE) == battle_reward("common")


def test_a_stranger_cannot_read_or_accept_a_battle(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    _add(world, _capture(CAROL, COMMON))

    world.as_user(CAROL)

    # 404 rather than 403 throughout: confirming the battle exists would tell a stranger
    # something about two other players' game.
    assert world.client.get(f"/battles/{battle_id}").status_code == 404
    assert world.client.post(
        f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)}
    ).status_code == 404


def test_the_battle_survives_a_payout_failure_and_says_so(world, monkeypatch):
    # Same trade-off as the capture flow: the battle has already been decided and both
    # players have been told. Failing the request would show an error for something that
    # really happened, and the retry would try to resolve it again.
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    async def boom(db, user_id, amount, reason):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(battles, "credit_wallet", boom)

    world.as_user(BOB)
    resp = world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    # Reported honestly as unpaid rather than displaying coins nobody received.
    assert resp.json()["coins_awarded"] is None
    assert world.balance(ALICE) == 0


def test_the_winner_is_paid_through_the_wallet_with_a_battle_reason(world):
    # The leaderboard aggregates transactions by reason, so this string is a contract
    # with Person D, not an internal label.
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    from sqlalchemy import select

    from app.models import Transaction

    async def fetch(session):
        return (await session.execute(select(Transaction))).scalars().all()

    rows = world.read(fetch)
    assert [(r.user_id, r.amount, r.type) for r in rows] == [(ALICE, battle_reward("common"), "battle:win")]


def test_beating_a_rarer_capture_pays_more(world):
    # Bob challenges with a common and loses to Alice's legendary; then the reverse. The
    # reward tracks the DEFEATED capture, so Bob's win pays far more than Alice's.
    alice_cap, bob_cap = _seed_matchup(world)

    world.as_user(BOB)
    first = _challenge(world, bob_cap.id, opponent_id=ALICE).json()  # Bob's common attacks
    world.as_user(ALICE)
    world.client.post(f"/battles/{first['id']}/accept", json={"capture_id": str(alice_cap.id)})

    assert world.balance(ALICE) == battle_reward("common")  # Alice beat a common
    assert world.balance(BOB) == 0
    assert battle_reward("legendary") > battle_reward("common")


# --- Decline ---------------------------------------------------------------------


def test_declining_ends_the_battle_without_a_payout(world):
    alice_cap, _bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    world.as_user(BOB)
    body = world.client.post(f"/battles/{battle_id}/decline").json()

    assert body["status"] == "declined"
    assert body["winner_id"] is None and body["outcome"] is None
    assert world.balance(ALICE) == 0  # a declined battle never happened


def test_only_the_challenged_player_can_decline(world):
    alice_cap, _ = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]

    assert world.client.post(f"/battles/{battle_id}/decline").status_code == 403


def test_cannot_decline_a_battle_that_was_already_resolved(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle_id = _challenge(world, alice_cap.id).json()["id"]
    world.as_user(BOB)
    world.client.post(f"/battles/{battle_id}/accept", json={"capture_id": str(bob_cap.id)})

    resp = world.client.post(f"/battles/{battle_id}/decline")

    assert resp.status_code == 409
    assert "resolved" in resp.json()["detail"]


# --- Expiry and recovery ---------------------------------------------------------


def _stale_battle(world, alice_cap, bob_cap, age, status="pending", resolving_age=None):
    battle = Battle(
        id=uuid.uuid4(),
        challenger_id=ALICE,
        opponent_id=BOB,
        challenger_capture_id=alice_cap.id,
        status=status,
        created_at=datetime.utcnow() - age,
        resolving_at=None if resolving_age is None else datetime.utcnow() - resolving_age,
    )
    _add(world, battle)
    return battle


def test_an_unanswered_challenge_expires(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle = _stale_battle(world, alice_cap, bob_cap, age=battles.CHALLENGE_TTL + timedelta(hours=1))

    body = world.client.get(f"/battles/{battle.id}").json()

    assert body["status"] == "expired"
    assert body["expires_at"] is None
    # Swept in the database, not just in the response -- otherwise it would be re-expired
    # on every read and could still be accepted in between.
    assert world.battle_row(str(battle.id)).status == "expired"


def test_an_expired_challenge_cannot_be_accepted(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle = _stale_battle(world, alice_cap, bob_cap, age=battles.CHALLENGE_TTL + timedelta(hours=1))

    world.as_user(BOB)
    resp = world.client.post(f"/battles/{battle.id}/accept", json={"capture_id": str(bob_cap.id)})

    assert resp.status_code == 409
    assert "expired" in resp.json()["detail"]
    assert world.balance(ALICE) == 0


def test_a_challenge_inside_its_window_is_still_answerable(world):
    alice_cap, bob_cap = _seed_matchup(world)
    battle = _stale_battle(world, alice_cap, bob_cap, age=battles.CHALLENGE_TTL - timedelta(hours=1))

    world.as_user(BOB)
    resp = world.client.post(f"/battles/{battle.id}/accept", json={"capture_id": str(bob_cap.id)})

    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_an_abandoned_resolution_is_returned_to_pending(world):
    # If the process dies between claiming a battle and writing its outcome, the row is
    # left in `resolving` with nobody able to accept it. Safe to reclaim precisely because
    # the wallet is only credited after the outcome is committed.
    alice_cap, bob_cap = _seed_matchup(world)
    battle = _stale_battle(
        world, alice_cap, bob_cap,
        age=timedelta(hours=1),
        status="resolving",
        resolving_age=battles.STUCK_RESOLVING_AFTER + timedelta(minutes=1),
    )

    body = world.client.get(f"/battles/{battle.id}").json()

    assert body["status"] == "pending"
    world.as_user(BOB)
    assert world.client.post(
        f"/battles/{battle.id}/accept", json={"capture_id": str(bob_cap.id)}
    ).status_code == 200


def test_a_resolution_in_flight_is_not_reclaimed(world):
    # The reclaim window is measured from when the ATTEMPT started, not from when the
    # challenge was created. Keying it on created_at let a concurrent read hand an
    # in-flight battle back to `pending`, where it could be resolved and paid a second
    # time -- this is the regression test for that.
    alice_cap, bob_cap = _seed_matchup(world)
    battle = _stale_battle(
        world, alice_cap, bob_cap,
        age=timedelta(days=1),  # an old challenge...
        status="resolving",
        resolving_age=timedelta(seconds=1),  # ...whose resolution started a moment ago
    )

    world.client.get(f"/battles/{battle.id}")

    assert world.battle_row(str(battle.id)).status == "resolving"
    world.as_user(BOB)
    assert world.client.post(
        f"/battles/{battle.id}/accept", json={"capture_id": str(bob_cap.id)}
    ).status_code == 409


# --- Listing ---------------------------------------------------------------------


def test_list_returns_both_sides_of_my_battles_newest_first(world):
    alice_cap, bob_cap = _seed_matchup(world)
    _challenge(world, alice_cap.id)  # Alice challenges Bob
    world.as_user(BOB)
    _challenge(world, bob_cap.id, opponent_id=ALICE)  # Bob challenges Alice

    world.as_user(ALICE)
    body = world.client.get("/battles").json()

    assert len(body) == 2
    assert {b["role"] for b in body} == {"challenger", "opponent"}
    assert body[0]["created_at"] >= body[1]["created_at"]


def test_list_excludes_other_peoples_battles(world):
    alice_cap, bob_cap = _seed_matchup(world)
    _challenge(world, alice_cap.id)
    _add(world, _capture(CAROL, COMMON))

    world.as_user(CAROL)

    assert world.client.get("/battles").json() == []


def test_unknown_battle_id_is_a_404_not_a_crash(world):
    assert world.client.get(f"/battles/{uuid.uuid4()}").status_code == 404


def test_roster_is_not_swallowed_by_the_battle_id_route(world):
    # /battles/roster and /battles/{battle_id} both match "GET /battles/roster". If the
    # parameterised route were declared first, the roster would 422 on "roster" not being
    # a UUID.
    _seed_matchup(world)

    assert world.client.get("/battles/roster").status_code == 200
    assert world.client.get("/battles/opponents").status_code == 200
