import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies.auth import get_current_user_id
from app.models import ShopItem, Transaction, User, UserItem

router = APIRouter(prefix="/shop", tags=["shop"])

# Owner: Person D — Economy, Shop & Shared Infra


@router.get("/items")
async def list_items(db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(ShopItem).order_by(ShopItem.cost))).scalars().all()
    return [
        {"id": str(i.id), "name": i.name, "type": i.type, "cost": i.cost, "effect": i.effect}
        for i in items
    ]


@router.post("/purchase")
async def purchase_item(
    item_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ShopItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Atomic conditional debit: the WHERE clause *is* the insufficient-funds
    # check. If it doesn't match — balance too low, or the user row doesn't
    # exist yet (same thing: an unmaterialized user has an implicit balance
    # of 0) — zero rows are affected and we know to reject. No separate
    # SELECT-then-check that a concurrent purchase could race against.
    result = await db.execute(
        update(User)
        .where(User.id == uuid.UUID(user_id), User.wallet_balance >= item.cost)
        .values(wallet_balance=User.wallet_balance - item.cost)
        .returning(User.wallet_balance)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    db.add(Transaction(user_id=uuid.UUID(user_id), amount=-item.cost, type=f"purchase:{item.name}"))
    db.add(UserItem(user_id=uuid.UUID(user_id), item_id=item.id))
    await db.commit()
    return {"status": "ok", "balance": row[0], "item": item.name}
