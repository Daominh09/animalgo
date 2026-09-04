from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, battles, captures, collection, devices, leaderboard, shop, wallet

app = FastAPI(title="AnimalGO API")

# The web build runs on a different port from the API, so every request it makes is
# cross-origin. Without this the browser sends a preflight OPTIONS, gets no
# Access-Control-Allow-Origin back, and blocks the request -- which surfaces in the app
# as a bare "NetworkError when attempting to fetch resource" with no clue that the
# server was ever reached. iOS and Android are unaffected: they are not browsers and
# never send an Origin header.
#
# Explicit origins rather than "*", and allow_credentials stays False: we authenticate
# with a bearer token in a header, not a cookie, so there is nothing for a browser to
# attach automatically to a forged cross-site request. (The two are also mutually
# exclusive -- the spec forbids credentials with a wildcard origin.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
