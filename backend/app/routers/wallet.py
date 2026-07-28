import uuid

from fastapi import APIRouter, Depends
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

    Commits its own transaction. If a caller needs this atomic with other
    writes in the same request, don't call this until those are ready to
    commit too, or refactor to a shared commit point.

    Doesn't enforce a non-negative balance floor — callers doing debits
    (e.g. a future shop purchase flow) need to check the balance first.
    """
    user = await db.get(User, user_id)
    if user is None:
        # wallet_balance's `default=0` only applies at flush, so it'd still
        # be None here and crash the += below if not set explicitly.
        user = User(id=user_id, wallet_balance=0)
        db.add(user)
        # No ORM relationship() links User/Transaction, so the flush's
        # automatic FK-ordering doesn't kick in — without this explicit
        # flush, the transactions insert can be sent before the users
        # insert and get rejected by the FK constraint.
        await db.flush()

    user.wallet_balance += amount
    db.add(Transaction(user_id=user_id, amount=amount, type=reason))
    await db.commit()
    return user.wallet_balance
