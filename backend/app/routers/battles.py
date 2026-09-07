import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Battle, Capture, User
from app.routers.wallet import credit_wallet
from app.services import push
from app.services.battle_resolution import battle_reward, resolve_battle, trait_for_species

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/battles", tags=["battles"])

# Owner: Person C — Battle System
#
# Battles are asynchronous, matching the v1 plan's "no WebSockets": a challenge is
# created, the opponent answers whenever they next open the app, and resolution happens
# at that moment. The lifecycle is:
#
#   POST /battles/challenge   -> pending          (+ push to the opponent)
#   POST /battles/{id}/accept -> resolved         (+ payout, + push to both)
#   POST /battles/{id}/decline-> declined
#   (nobody answers)          -> expired          (lazily, on the next read)
#
# Hand-off in from Person B: a capture's rarity_tier is what decides a battle, so the
# roster is only as good as the rarity engine. Hand-off out to Person D: the winner is
# paid through credit_wallet, and the "battle:win" transactions it writes are what the
# leaderboard aggregates.

# How long a challenge waits before it stops counting. Two days: long enough that a
# player who only opens the app at weekends still gets to answer, short enough that the
# Battle tab isn't a graveyard of challenges from people who quit.
CHALLENGE_TTL = timedelta(hours=48)

# A battle mid-resolution is claimed by setting `resolving` (see accept_battle). If the
# process dies in the small window between the claim and the outcome write, the row would
# otherwise be stuck in that state forever with nobody able to accept it. Anything that
# has sat in `resolving` longer than this is treated as an abandoned attempt and returned
# to `pending`. Safe to revert precisely because no payout can have happened yet -- the
# wallet is credited only after the outcome is committed.
STUCK_RESOLVING_AFTER = timedelta(minutes=5)

# Opponent list size. Matchmaking is deliberately "anyone with a capture" in v1; a real
# queue (skill/rarity matching, the Redis matchmaking set the plan mentions) is a later
# problem, and with a small player base a full list is friendlier than a clever one.
MAX_OPPONENTS = 50


def _utc_iso(value: datetime | None) -> str | None:
    """ISO 8601 with an explicit UTC offset.

    Same reasoning as collection.py's version, and the same bug if it's skipped: these
    columns are naive but written from utcnow(), so a bare string is read as local time by
    `new Date(...)` and shifts a battle onto the wrong day. Kept local rather than
    imported from Person B's router so the two verticals don't share a private helper.
    """
    return None if value is None else value.replace(tzinfo=timezone.utc).isoformat()


class ChallengeRequest(BaseModel):
    opponent_id: uuid.UUID
    capture_id: uuid.UUID


class AcceptRequest(BaseModel):
    capture_id: uuid.UUID


def _capture_card(capture: Capture | None) -> dict | None:
    """The bits of a capture a battle screen shows. Deliberately not the whole row:
    coordinates have no place in a battle, and sending them would put one player's
    capture locations (fuzzed, but still) in another player's hands."""
    if capture is None:
        return None
    return {
        "id": str(capture.id),
        "common_name": capture.common_name,
        "species_id": capture.species_id,
        "image_url": capture.image_url,
        "rarity_tier": capture.rarity_tier,
        # Derived, not stored -- see trait_for_species. The client shows it so a player
        # can see the matchup before committing a capture.
        "trait": trait_for_species(capture.species_id),
    }


def _display_name(user: User | None) -> str:
    # display_name defaults to "" and nothing sets it yet, so almost every player hits
    # this fallback today. "Player" beats rendering an empty string in a VS screen.
    if user is None or not user.display_name:
        return "Player"
    return user.display_name


def _serialize(
    battle: Battle,
    captures: dict[uuid.UUID, Capture],
    users: dict[uuid.UUID, User],
    viewer_id: uuid.UUID,
) -> dict:
    """One battle, from `viewer_id`'s point of view.

    Both players get the same numbers -- they're read from the row, not recomputed -- but
    `role` and `outcome` are relative, so each side's screen can say "You won" without the
    client having to work out which half of the row it is.
    """
    is_challenger = battle.challenger_id == viewer_id

    outcome = None
    if battle.status == "resolved" and battle.winner_id is not None:
        outcome = "won" if battle.winner_id == viewer_id else "lost"

    return {
        "id": str(battle.id),
        "status": battle.status,
        "role": "challenger" if is_challenger else "opponent",
        "outcome": outcome,
        "created_at": _utc_iso(battle.created_at),
        "resolved_at": _utc_iso(battle.resolved_at),
        # Only meaningful while pending; null afterwards so the client doesn't render a
        # countdown on a battle that has already been decided.
        "expires_at": _utc_iso(battle.created_at + CHALLENGE_TTL) if battle.status == "pending" else None,
        "challenger": {
            "user_id": str(battle.challenger_id),
            "display_name": _display_name(users.get(battle.challenger_id)),
            "capture": _capture_card(captures.get(battle.challenger_capture_id)),
            "total": battle.challenger_total,
            "roll": battle.challenger_roll,
        },
        "opponent": {
            "user_id": str(battle.opponent_id),
            "display_name": _display_name(users.get(battle.opponent_id)),
            # Null while pending: the opponent hasn't picked a capture yet.
            "capture": _capture_card(captures.get(battle.opponent_capture_id)) if battle.opponent_capture_id else None,
            "total": battle.opponent_total,
            "roll": battle.opponent_roll,
        },
        "winner_id": str(battle.winner_id) if battle.winner_id else None,
        "trait_advantage": battle.trait_advantage,
        # Coins the WINNER earned. Null on an unresolved battle, and also null if the
        # payout itself failed -- which is honest rather than a displayed lie.
        "coins_awarded": battle.coins_awarded,
    }


async def _hydrate(db: AsyncSession, battles: list[Battle]) -> tuple[dict, dict]:
    """Fetches the captures and users referenced by a list of battles, in two queries
    rather than two per battle."""
    capture_ids = set()
    user_ids = set()
    for b in battles:
        capture_ids.add(b.challenger_capture_id)
        if b.opponent_capture_id:
            capture_ids.add(b.opponent_capture_id)
        user_ids.update((b.challenger_id, b.opponent_id))

    captures = {}
    if capture_ids:
        rows = (await db.execute(select(Capture).where(Capture.id.in_(capture_ids)))).scalars().all()
        captures = {c.id: c for c in rows}

    users = {}
    if user_ids:
        rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u for u in rows}

    return captures, users


async def _sweep_stale(db: AsyncSession, battles: list[Battle]) -> None:
    """Expires unanswered challenges and reclaims abandoned resolutions.

    Done lazily on read rather than by a scheduled job: there is no worker process in v1,
    and a challenge only needs to *look* expired at the moment someone looks at it. The
    in-memory objects are updated too, so the response reflects the sweep without a
    re-query.
    """
    now = datetime.utcnow()
    expired = [b.id for b in battles if b.status == "pending" and now - b.created_at > CHALLENGE_TTL]
    # Measured from when the ATTEMPT started, not from when the challenge was created.
    # Using created_at here would reclaim resolutions that began a moment ago on an older
    # challenge, and a reclaimed battle can be accepted again -- so that version of this
    # line was a double-payout bug rather than a recovery mechanism.
    stuck = [
        b.id
        for b in battles
        if b.status == "resolving"
        and b.resolving_at is not None
        and now - b.resolving_at > STUCK_RESOLVING_AFTER
    ]
    if not expired and not stuck:
        return

    if expired:
        await db.execute(
            update(Battle).where(Battle.id.in_(expired), Battle.status == "pending").values(status="expired")
        )
    if stuck:
        await db.execute(
            update(Battle)
            .where(Battle.id.in_(stuck), Battle.status == "resolving")
            .values(status="pending", resolving_at=None)
        )
    await db.commit()

    for b in battles:
        if b.id in expired:
            b.status = "expired"
        elif b.id in stuck:
            b.status = "pending"


# --- Roster and matchmaking ------------------------------------------------------
#
# Declared before /{battle_id}: FastAPI matches routes in definition order, so a
# /battles/roster request would otherwise be captured by the parameterised route and 422
# on "roster" not being a UUID.


@router.get("/roster")
async def get_roster(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """The player's captures, as battle cards — what they choose from when challenging
    or answering.

    Every capture is eligible, including ones whose rarity never resolved: those fight
    with common's base power (see resolve_battle). Excluding them would leave a player
    whose lookups all failed with an empty roster and no way into the game at all.
    """
    rows = (
        await db.execute(
            select(Capture)
            .where(Capture.owner_id == uuid.UUID(user_id))
            .order_by(Capture.captured_at.desc())
        )
    ).scalars().all()
    return [_capture_card(c) for c in rows]


@router.get("/opponents")
async def get_opponents(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Players who can be challenged: anyone else who owns at least one capture.

    Someone with no captures can't answer a challenge, so listing them would only produce
    challenges that expire.
    """
    me = uuid.UUID(user_id)
    rows = (
        await db.execute(
            select(User, func.count(Capture.id).label("capture_count"))
            .join(Capture, Capture.owner_id == User.id)
            .where(User.id != me)
            .group_by(User.id)
            .order_by(func.count(Capture.id).desc())
            .limit(MAX_OPPONENTS)
        )
    ).all()

    return [
        {
            "user_id": str(user.id),
            "display_name": _display_name(user),
            "capture_count": capture_count,
        }
        for user, capture_count in rows
    ]


# --- Battles ---------------------------------------------------------------------


@router.get("")
async def list_battles(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Every battle the player is in, newest first.

    One list rather than separate incoming/outgoing/history endpoints: the Battle tab
    shows all three together, and `status` + `role` are enough for the client to group
    them.
    """
    me = uuid.UUID(user_id)
    battles = (
        await db.execute(
            select(Battle)
            .where((Battle.challenger_id == me) | (Battle.opponent_id == me))
            .order_by(Battle.created_at.desc())
        )
    ).scalars().all()
    battles = list(battles)

    await _sweep_stale(db, battles)
    captures, users = await _hydrate(db, battles)
    return [_serialize(b, captures, users, me) for b in battles]


@router.post("/challenge")
async def create_challenge(
    body: ChallengeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Challenges another player with one of your captures.

    The challenge sits in `pending` until the opponent answers with a capture of their
    own; nothing is decided here, so the response carries no outcome.
    """
    me = uuid.UUID(user_id)

    if body.opponent_id == me:
        # Otherwise a player could farm the win reward against themselves indefinitely,
        # since every battle pays the winner and there is always a winner.
        raise HTTPException(status_code=400, detail="You cannot challenge yourself")

    capture = await db.get(Capture, body.capture_id)
    # Ownership is checked here, not just in the roster query: the roster is only a
    # suggestion, and the capture id arrives from the client, so anyone could post
    # someone else's legendary. Same 404 for "doesn't exist" and "isn't yours" on
    # purpose -- a different message would let a player probe which capture ids are real.
    if capture is None or capture.owner_id != me:
        raise HTTPException(status_code=404, detail="Capture not found")

    opponent = await db.get(User, body.opponent_id)
    if opponent is None:
        raise HTTPException(status_code=404, detail="Opponent not found")

    # One outstanding challenge per pair. Without this, tapping Challenge repeatedly
    # sends the opponent a push per tap and buries the one they might have answered --
    # so the spam is aimed at a player, not just at the table. The existing challenge is
    # theirs to answer or decline; a second one adds nothing until it's dealt with.
    existing = (
        await db.execute(
            select(Battle.id).where(
                Battle.challenger_id == me,
                Battle.opponent_id == body.opponent_id,
                Battle.status.in_(("pending", "resolving")),
            )
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending challenge against this player",
        )

    battle = Battle(
        challenger_id=me,
        opponent_id=body.opponent_id,
        challenger_capture_id=capture.id,
        status="pending",
    )
    db.add(battle)
    await db.commit()
    await db.refresh(battle)

    challenger = await db.get(User, me)
    await push.send_push([
        push.PushMessage(
            token=opponent.push_token,
            title="You've been challenged",
            body=f"{_display_name(challenger)} sent a battle challenge. Pick a capture to fight back.",
            data={"type": "battle", "battle_id": str(battle.id)},
        )
    ])

    captures, users = await _hydrate(db, [battle])
    return _serialize(battle, captures, users, me)


@router.get("/{battle_id}")
async def get_battle(
    battle_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """One battle. Only the two players in it can read it."""
    me = uuid.UUID(user_id)
    battle = await db.get(Battle, battle_id)
    if battle is None or me not in (battle.challenger_id, battle.opponent_id):
        # 404 rather than 403 for a battle that exists but isn't yours: confirming it
        # exists tells a stranger something about two other players' game.
        raise HTTPException(status_code=404, detail="Battle not found")

    await _sweep_stale(db, [battle])
    captures, users = await _hydrate(db, [battle])
    return _serialize(battle, captures, users, me)


@router.post("/{battle_id}/accept")
async def accept_battle(
    battle_id: uuid.UUID,
    body: AcceptRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Answers a challenge with one of your captures, which resolves the battle.

    This is the only place a battle is decided. The dice are rolled once and the result
    is written to the row, so both players — and every later read — see the same numbers.
    """
    me = uuid.UUID(user_id)
    battle = await db.get(Battle, battle_id)
    if battle is None or me not in (battle.challenger_id, battle.opponent_id):
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.opponent_id != me:
        raise HTTPException(status_code=403, detail="Only the challenged player can accept")

    await _sweep_stale(db, [battle])
    if battle.status == "expired":
        raise HTTPException(status_code=409, detail="This challenge has expired")
    if battle.status != "pending":
        raise HTTPException(status_code=409, detail=f"This battle is already {battle.status}")

    my_capture = await db.get(Capture, body.capture_id)
    if my_capture is None or my_capture.owner_id != me:
        raise HTTPException(status_code=404, detail="Capture not found")

    challenger_capture = await db.get(Capture, battle.challenger_capture_id)
    if challenger_capture is None:
        # The challenger's capture was deleted between challenge and accept. Nothing to
        # fight, and resolving against a missing capture would be inventing a matchup.
        raise HTTPException(status_code=409, detail="The challenger's capture is no longer available")

    # Claim the battle with a conditional UPDATE before rolling anything. Two devices
    # tapping Accept at the same moment both pass the status check above -- without this,
    # both would resolve the same battle and the winner would be paid twice. Only the
    # transaction whose UPDATE matches a still-`pending` row proceeds.
    claim = await db.execute(
        update(Battle)
        .where(Battle.id == battle.id, Battle.status == "pending")
        .values(status="resolving", resolving_at=datetime.utcnow())
    )
    await db.commit()
    if claim.rowcount == 0:
        raise HTTPException(status_code=409, detail="This battle is already being resolved")
    # Keep the in-memory object in step with the row we just claimed, so the outcome write
    # below emits a status change from "resolving" rather than from a stale "pending".
    battle.status = "resolving"

    result = resolve_battle(
        challenger_rarity_tier=challenger_capture.rarity_tier,
        opponent_rarity_tier=my_capture.rarity_tier,
        challenger_trait=trait_for_species(challenger_capture.species_id),
        opponent_trait=trait_for_species(my_capture.species_id),
    )

    challenger_won = result["winner"] == "challenger"
    winner_id = battle.challenger_id if challenger_won else battle.opponent_id
    loser_capture = my_capture if challenger_won else challenger_capture
    reward = battle_reward(loser_capture.rarity_tier)

    # The outcome is committed BEFORE the wallet is touched, and coins_awarded stays null
    # until the credit actually succeeds. That ordering is what makes the payout safe: a
    # crash here leaves a resolved battle that was never paid (visible and fixable),
    # never a battle that could be resolved and paid a second time.
    battle.opponent_capture_id = my_capture.id
    battle.status = "resolved"
    battle.winner_id = winner_id
    battle.resolved_at = datetime.utcnow()
    battle.challenger_total = result["challenger_total"]
    battle.opponent_total = result["opponent_total"]
    battle.challenger_roll = result["challenger_roll"]
    battle.opponent_roll = result["opponent_roll"]
    battle.trait_advantage = result["trait_advantage"]
    db.add(battle)
    await db.commit()

    # Hand-off out to Person D. credit_wallet has no route on purpose -- if the client
    # could call it, a player could pay themselves. The "battle:win" reason is also what
    # the leaderboard reads to count battle earnings, so don't reword it casually.
    try:
        await credit_wallet(db, winner_id, reward, "battle:win")
        battle.coins_awarded = reward
        db.add(battle)
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("battle payout failed for battle %s, winner %s", battle.id, winner_id)

    await _notify_resolved(db, battle)

    captures, users = await _hydrate(db, [battle])
    return _serialize(battle, captures, users, me)


@router.post("/{battle_id}/decline")
async def decline_battle(
    battle_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Turns down a challenge. No payout, no dice — a declined battle never happened."""
    me = uuid.UUID(user_id)
    battle = await db.get(Battle, battle_id)
    if battle is None or me not in (battle.challenger_id, battle.opponent_id):
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.opponent_id != me:
        raise HTTPException(status_code=403, detail="Only the challenged player can decline")

    # Conditional on `pending` for the same reason accept is: decline and accept can race
    # each other from two devices, and a declined battle that had already paid out would
    # be a contradiction.
    claim = await db.execute(
        update(Battle).where(Battle.id == battle.id, Battle.status == "pending").values(status="declined")
    )
    await db.commit()
    if claim.rowcount == 0:
        await db.refresh(battle)
        raise HTTPException(status_code=409, detail=f"This battle is already {battle.status}")

    await db.refresh(battle)
    captures, users = await _hydrate(db, [battle])
    return _serialize(battle, captures, users, me)


async def _notify_resolved(db: AsyncSession, battle: Battle) -> None:
    """Tells both players how it went. Best effort — see push.send_push."""
    challenger = await db.get(User, battle.challenger_id)
    opponent = await db.get(User, battle.opponent_id)
    data = {"type": "battle", "battle_id": str(battle.id)}

    def message(user: User | None, them: User | None) -> push.PushMessage:
        won = user is not None and battle.winner_id == user.id
        if won:
            # coins_awarded is None when the payout failed. Saying "better luck next time"
            # to the winner because of that would be two contradictions in one
            # notification -- they won, and they were not unlucky, the credit just didn't
            # land. Report the win without a figure instead.
            tail = f"you won +{battle.coins_awarded} coins." if battle.coins_awarded else "you won."
        else:
            tail = "better luck next time."
        return push.PushMessage(
            token=user.push_token if user else None,
            title="You won!" if won else "You lost",
            body=f"Your battle against {_display_name(them)} is done — {tail}",
            data=data,
        )

    await push.send_push([message(challenger, opponent), message(opponent, challenger)])
