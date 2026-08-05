from fastapi import FastAPI

from app.routers import auth, battles, captures, collection, devices, leaderboard, shop, wallet

app = FastAPI(title="AnimalGO API")

app.include_router(auth.router)
app.include_router(captures.router)
app.include_router(collection.router)
app.include_router(battles.router)
app.include_router(wallet.router)
app.include_router(shop.router)
app.include_router(leaderboard.router)
app.include_router(devices.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
