# AnimalGO

A mobile game where players photograph real animals, get them ranked by rarity, collect them, and battle other players.

## Tech Stack
- Mobile: React Native (Expo) — see `mobile/`
- Backend: Python + FastAPI — see `backend/`
- Database + Auth: Supabase (Postgres + Supabase Auth)
- Photo storage: Cloudflare R2
- Species ID: DeepSeek V4 vision (OpenAI-compatible API)
- Rarity data: GBIF + IUCN
- Caching: Redis

## Repo Structure
- `mobile/` — Expo app (camera, map, collection, battle, shop)
- `backend/` — FastAPI service (captures, rarity, battles, wallet, shop)

## Getting Started

First time on this project? See **[SETUP.md](SETUP.md)** — it walks through
creating the shared Supabase/R2/DeepSeek/Redis accounts and the git workflow.
Quick reference once you have credentials:

### Mobile
```
cd mobile
npm ci                  # committed lockfile, versions pinned to Expo SDK 57
cp .env.example .env    # fill in EXPO_PUBLIC_API_URL and Supabase keys
npx expo start
```

### Backend
```
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env       # fill in Supabase, R2, DeepSeek, Redis credentials
alembic upgrade head       # apply migrations to the shared Supabase DB
uvicorn app.main:app --reload
```

## Team Ownership
Each person owns one feature vertical end-to-end (mobile + backend). See the project plan doc for the full week-by-week breakdown.

| Person | Vertical | Key files |
|---|---|---|
| A | Capture & Species ID | `mobile/app/(tabs)/camera.tsx`, `backend/app/routers/captures.py`, `backend/app/services/vision.py`, `backend/app/services/storage.py` |
| B | Rarity Engine & Collection | `mobile/app/(tabs)/map.tsx`, `mobile/app/(tabs)/collection.tsx`, `backend/app/routers/collection.py`, `backend/app/services/gbif_iucn.py`, `backend/app/services/rarity.py` |
| C | Battle System | `mobile/app/(tabs)/battle.tsx`, `backend/app/routers/battles.py` |
| D | Economy, Shop & Shared Infra | `mobile/app/(tabs)/shop.tsx`, `backend/app/routers/wallet.py`, `backend/app/routers/shop.py`, `backend/app/routers/leaderboard.py` |
