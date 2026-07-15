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

### Option A: Docker (recommended — no Node/Python setup needed)

Runs all three services (backend, mobile's Metro bundler, a local Redis) in
containers. Nobody needs Node.js or Python installed locally, and dependency
installs happen inside the image, not on your machine.

**One real limitation**: Docker can run the Metro bundler for you, but it
**cannot** run the iOS Simulator — that needs Xcode running natively on
macOS, which is impossible inside a Linux container. So you still need
**Expo Go on your phone** to actually view the mobile app; Docker just
removes the "install Node, run npm ci" step, not that one.

1. Get the **shared credentials** from whoever set up the accounts (password
   manager, not Slack/email plaintext) — you'll need values for
   `backend/.env` (Supabase, R2, DeepSeek) and `mobile/.env` (Supabase).
2. ```
   cp backend/.env.example backend/.env   # fill in the shared credentials
   cp mobile/.env.example mobile/.env     # fill in EXPO_PUBLIC_* keys
   cp .env.example .env
   # set HOST_LAN_IP in that root .env to your machine's LAN IP —
   # `ipconfig getifaddr en0` on macOS. This is what lets your phone's
   # Expo Go actually reach the container; skipping it breaks the QR code.
   docker compose up --build
   ```
3. Backend: visit `http://localhost:8000/health` → `{"status": "ok"}`.
4. Mobile: watch the `mobile` service logs for a QR code (`docker compose
   logs mobile`, or just watch the terminal you ran `up` in) and scan it
   with Expo Go. Your phone must be on the **same Wi-Fi** as this machine.
5. First time only — apply migrations to the shared DB (containers don't do
   this automatically, since it only needs to happen once, not on every
   container start): see step 3 under Option B below, or run it via
   `docker compose exec backend alembic upgrade head`.

Stop everything with `docker compose down` (add `-v` to also drop Redis's
data, though there's nothing durable in it — it's just a cache). Code
changes on your host are picked up live in both containers — no rebuild
needed unless you change `package.json`/`requirements.txt`.

### Option B: Native

Closer to how things actually run in production; also what you need if
you're touching Python/Node dependencies rather than just app code.

1. Same credentials step as above — get them from whoever set up the
   accounts, don't create your own.
2. **Backend**
   ```
   cd backend
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements-dev.txt
   cp .env.example .env       # fill in the shared credentials
   alembic upgrade head       # apply migrations to the shared Supabase DB
   uvicorn app.main:app --reload
   ```
3. **Mobile**
   ```
   cd mobile
   npm ci                  # committed lockfile, versions pinned to Expo SDK 54
   cp .env.example .env
   # fill in EXPO_PUBLIC_API_URL (your machine's LAN IP if testing on a
   # physical device via Expo Go — get it with `ipconfig getifaddr en0` on
   # macOS — not localhost, the phone can't resolve that) and the Supabase keys
   npx expo start
   ```
   Scan the QR code with Expo Go, or press `i`/`a` for a simulator (only
   available this way — see the Docker limitation above).

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
- `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`

**`.env`** at the repo root (Docker only, copy from root `.env.example`):
- `HOST_LAN_IP` — your own machine's LAN IP, see the Docker steps above

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
