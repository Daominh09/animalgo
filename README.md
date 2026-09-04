# AnimalGO

A mobile game where players photograph real animals, get them ranked by rarity, collect them, and battle other players.

## Tech Stack
- Mobile: React Native (Expo) — see `mobile/`
- Backend: Python + FastAPI — see `backend/`
- Database + Auth: Supabase (Postgres + Supabase Auth)
- Photo storage: Cloudflare R2
- Species ID: DeepSeek V4 vision (OpenAI-compatible API) — **currently blocked**: DeepSeek's API doesn't accept image input at all (confirmed against the official docs and a live API call), so `backend/app/services/vision.py` needs a different provider (Claude or Gemini vision were the fallbacks discussed) before this can actually work. Not yet decided as of this writing.
- Rarity data: GBIF + IUCN
- Caching: Redis

## Repo Structure
- `mobile/` — Expo app (camera, map, collection, battle, shop)
- `backend/` — FastAPI service (captures, rarity, battles, wallet, shop)

## Getting Started

Backend runs via Docker or natively, your choice. Mobile always runs
natively — Expo Go and the iOS Simulator both need to talk to a live Metro
process on your machine; running Metro inside a container turned out to be
more trouble than it's worth (flaky native-binary loading under Docker's
process supervision — `lightningcss`, used by NativeWind, failed to load
consistently when run as the container's main process, even though it
loaded fine in one-off debugging containers, most likely something specific
to how Docker Desktop on macOS handles PID 1 for that init.node addon load
path — not worth chasing further given Docker buys nothing for Metro
compared to running it directly).

### Backend — Docker (recommended)
```
cd backend
cp .env.example .env    # fill in the shared credentials
cd ..
docker compose up --build
```
This builds the backend image and starts it alongside a local Redis
container — no need for the Upstash account until you actually deploy.
`REDIS_URL` in `.env` is overridden automatically to point at that
container; everything else (`DATABASE_URL`, `SUPABASE_URL`, R2, DeepSeek)
comes straight from your `.env`. Code changes on your host are picked up
live (bind-mounted, `uvicorn --reload`) — no rebuild needed for Python edits,
only for dependency changes.

Visit `http://localhost:8000/health` → `{"status": "ok"}`.
Stop it with `docker compose down`.

Migrations don't run automatically inside the container — run them from
your host once (see native setup below), since they only need to happen
once against the shared DB, not per-container-start.

### Backend — native
```
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env       # fill in the shared credentials
alembic upgrade head       # apply migrations to the shared Supabase DB
uvicorn app.main:app --reload
```

### Mobile
```
cd mobile
npm ci                  # committed lockfile, versions pinned to Expo SDK 54
cp .env.example .env
# fill in EXPO_PUBLIC_API_URL (your machine's LAN IP if testing on a
# physical device via Expo Go — get it with `ipconfig getifaddr en0` on
# macOS — not localhost, the phone can't resolve that) and the Supabase keys
npx expo start
```
Scan the QR code with Expo Go, or press `i`/`a` for a simulator.

Pinned to Expo **SDK 54**, not the newer SDK 57, on purpose: as of writing,
the public Expo Go app on the App Store still ships the SDK 54 runtime —
SDK 57's native Expo Go build is sitting in Apple's review queue. Bumping to
SDK 57 will break "scan the QR code with Expo Go" on physical devices until
that review clears (the iOS Simulator and `eas go` aren't affected, since
neither depends on the App Store release). Check
[the Expo SDK 57 changelog](https://expo.dev/changelog/sdk-57) before
upgrading — if Apple's approved it by the time you read this, upgrading is
just `npx expo install expo@latest && npx expo install --fix`.

### Sanity checks before you start building
```
cd backend && source venv/bin/activate && pytest && ruff check .
cd mobile && npx tsc --noEmit && npm run lint && npx expo-doctor
```
All of these should pass clean on a fresh clone.

## Env files you need to fill in

Ask whoever set up the shared accounts for these values (password manager,
not Slack/email plaintext) — accounts are already created, you're just
filling in credentials, not signing up for anything.

**`backend/.env`** (copy from `backend/.env.example`):
- `DATABASE_URL` — Supabase Postgres connection string
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` — identifies the project to Supabase's auth server.
  Required: `/auth/register`, `/auth/login` and `/auth/refresh` return 503
  without it. Dashboard → Project Settings → API Keys → "anon public".
  Never put the `service_role` key here.
- `CORS_ORIGINS` — optional, comma-separated. Only the web build needs it.
  Defaults cover Expo's dev server; add your port if Metro picks a
  different one, or the browser blocks every request with a bare
  "NetworkError" that says nothing about the cause.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET_NAME`, `R2_ENDPOINT_URL` — Cloudflare R2
- `DEEPSEEK_API_KEY` — currently blocked, see the Tech Stack note above;
  ask before building against it
- `REDIS_URL` — leave as the default; Docker overrides it to the local
  container automatically. Only matters if running natively without Docker
  and without a local Redis, or once there's a real deployment target.
- `IUCN_API_TOKEN` — optional for Week 1

**`mobile/.env`** (copy from `mobile/.env.example`):
- `EXPO_PUBLIC_API_URL` — see the LAN IP note in the setup steps above

That's the only one. The app signs in through the backend, so no Supabase
URL or key reaches the client. Create an account from the app's sign-in
screen rather than sharing credentials.

## Schema changes (Alembic)

The Supabase DB is shared — don't hand-edit tables. When you change
`backend/app/models.py`:
```
alembic revision --autogenerate -m "short description"
```
Review the generated file in `backend/migrations/versions/` (autogenerate
misses some things — renames, some constraint changes), commit it with your
PR. After your PR merges, run `alembic upgrade head` against the shared DB
yourself and mention it in standup, so nobody else's migration collides with
an unapplied one still sitting in your branch.

## Git workflow
- `main` is the deployable branch. Don't push to it directly.
- Branch per person/feature, e.g. `a/camera-capture`, `b/rarity-scoring`.
- Open a PR even for solo work on your own vertical — it's the paper trail
  for hand-offs (A→B, B→C, B/C→D per the project plan) and what CI runs
  against.
- Keep `.env` out of every commit — it's gitignored already; if you ever see
  it in `git status` as staged, something's wrong, stop and ask.
- At the hand-off syncs (start of Weeks 2 and 3 per the plan doc), agree on
  the request/response shape before either side starts building — update the
  relevant router stub's TODO comments to reflect what was agreed.

## Team Ownership
Each person owns one feature vertical end-to-end (mobile + backend). See the project plan doc for the full week-by-week breakdown.

| Person | Vertical | Key files |
|---|---|---|
| A | Capture & Species ID | `mobile/app/(tabs)/camera.tsx`, `backend/app/routers/captures.py`, `backend/app/services/vision.py`, `backend/app/services/storage.py` |
| B | Rarity Engine & Collection | `mobile/app/(tabs)/map.tsx`, `mobile/app/(tabs)/collection.tsx`, `backend/app/routers/collection.py`, `backend/app/services/gbif_iucn.py`, `backend/app/services/rarity.py` |
| C | Battle System | `mobile/app/(tabs)/battle.tsx`, `backend/app/routers/battles.py` |
| D | Economy, Shop & Shared Infra | `mobile/app/(tabs)/shop.tsx`, `backend/app/routers/wallet.py`, `backend/app/routers/shop.py`, `backend/app/routers/leaderboard.py` |
