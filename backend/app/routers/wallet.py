import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import Transaction, User

router = APIRouter(prefix="/wallet", tags=["wallet"])

# Owner: Person D — Economy, Shop & Shared Infra


@router.get("")
async def get_wallet(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        # First time this Supabase-authenticated user has touched the app's
        # own `users` table — nothing else creates this row yet.
        user = User(id=uuid.UUID(user_id))
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return {"balance": user.wallet_balance}


async def credit_wallet(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    reason: str,
) -> int:
    """Credits (or debits, if amount is negative) a user's wallet and
    records the transaction. Intentionally not exposed as a route — B
    (rarity scoring) and C (battle resolution) call this directly with
    their own db session, since letting the mobile client hit this over
    HTTP would let any player mint themselves unlimited currency.

    Does the increment as a single atomic INSERT ... ON CONFLICT DO UPDATE
    rather than SELECT-then-write, so two concurrent callers crediting the
    same user (e.g. B and C firing at once) can't lose an update to a race
    — Postgres serializes the two statements via its own row lock instead
    of us reading a stale balance in Python. Also means a brand-new user's
    row and an existing one are handled by the same statement, no separate
    "does this user exist yet" branch needed.

    Commits its own transaction. If a caller needs this atomic with other
    writes in the same request, don't call this until those are ready to
    commit too, or refactor to a shared commit point.

    Doesn't enforce a non-negative balance floor — this always succeeds
    regardless of sign. Callers doing conditional debits (e.g. a shop
    purchase that must reject on insufficient funds) need a check-and-debit
    that can fail, which this isn't — see purchase_item in shop.py for that
    pattern instead of using this for debits.
    """
    stmt = (
        pg_insert(User)
        .values(id=user_id, wallet_balance=amount)
        .on_conflict_do_update(
            index_elements=[User.id],
            set_={"wallet_balance": User.wallet_balance + amount},
        )
        .returning(User.wallet_balance)
    )
    new_balance = (await db.execute(stmt)).scalar_one()

    db.add(Transaction(user_id=user_id, amount=amount, type=reason))
    await db.commit()
    return new_balance
