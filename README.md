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

### Mobile
```
cd mobile
npm install
cp .env.example .env   # fill in EXPO_PUBLIC_API_URL and Supabase keys
npx expo start
```
Note: the versions in `package.json` are starting points. Run `npx expo install <package>` for
each Expo-related dependency once you've cloned this, so versions align with your installed Expo SDK.

### Backend
```
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # fill in Supabase, R2, DeepSeek, Redis credentials
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
