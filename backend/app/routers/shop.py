from fastapi import APIRouter

router = APIRouter(prefix="/shop", tags=["shop"])

# Owner: Person D — Economy, Shop & Shared Infra


@router.get("/items")
async def list_items():
    # TODO: query shop_items table
    return []


@router.post("/purchase")
async def purchase_item(item_id: str):
    # TODO: debit wallet, grant item
    return {"status": "ok"}
