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

1. Get the **shared credentials** — see
   [Shared accounts](#shared-accounts-one-time-team-setup) below if nobody's
   created them yet, or grab them from a teammate (password manager, not
   Slack/email in plaintext) if they have.
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

1. Same credentials step as above.
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

## Shared accounts (one-time team setup)

Do this once as a team — whoever sets each one up shares the resulting
values with the others via a password manager, never in Slack/email
plaintext.

### 1. Supabase (Postgres + Auth)
1. Go to [supabase.com](https://supabase.com) → New project.
2. Pick a region close to your team, set a strong DB password (save it —
   you'll need it in the connection string).
3. Click **Connect** (top nav) → **Direct** tab → Connection Method →
   **Session pooler**, Type `URI`, port `5432`. Not "Direct connection"
   (IPv6-only unless you pay for the IPv4 add-on — will fail to resolve on
   most home networks) and not "Transaction pooler" on port `6543`
   (`asyncpg` needs prepared-statement support that mode doesn't give you).
   Fill in the DB password you set at project creation, then rewrite the
   scheme from `postgresql://` to `postgresql+asyncpg://` for `backend/.env`'s
   `DATABASE_URL`.
4. Go to **Settings → API Keys**, copy the **Project URL** → `SUPABASE_URL`.
   You do *not* need a JWT secret: this app's backend verifies tokens via
   the project's JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`),
   which works automatically for projects on Supabase's newer asymmetric JWT
   signing keys (check **Settings → JWT Keys** — if "JWT Signing Keys" shows
   an ECC/RSA current key, you're on this path already; if the project only
   ever shows a "Legacy JWT Secret" with no signing keys tab, ping whoever's
   doing the backend work since `auth.py` will need a different code path).
5. Share `DATABASE_URL` and `SUPABASE_URL` with the team.

### 2. Cloudflare R2 (photo storage)
1. Cloudflare dashboard → R2 → Create bucket, name it `animalgo-photos`.
2. R2 → Manage API tokens → **Create Account API token** (not "User API
   token" — this is a service credential shared across the team and
   eventually production, not tied to one person's login).
3. Permissions: Object Read & Write, scoped to `animalgo-photos` only.
4. Note down: Account ID, Access Key ID, Secret Access Key.
5. `R2_ENDPOINT_URL` is `https://<account_id>.r2.cloudflarestorage.com`.
6. Share `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
   `R2_BUCKET_NAME`, `R2_ENDPOINT_URL` with the team.

### 3. DeepSeek (blocked — see Tech Stack note above)
1. [platform.deepseek.com](https://platform.deepseek.com) → add billing
   credit → API keys → Create.
2. Share `DEEPSEEK_API_KEY` with the team. `DEEPSEEK_BASE_URL` stays the
   default (`https://api.deepseek.com`).
3. Before building against it: confirm the vision-provider question above
   is resolved. The key will authenticate fine for text-only chat
   completions, but image input isn't supported by this API as of writing.

### 4. Redis (Upstash) — only needed for production/staging
Local dev uses the Redis container in `docker-compose.yml` — you don't need
this until deploying somewhere that isn't your laptop.
1. [upstash.com](https://upstash.com) → Create database (Redis, regional is
   fine for a 4-person project).
2. Copy the `rediss://...` connection string → `REDIS_URL`.

### 5. IUCN Red List API token (optional for week 1)
1. [apiv3.iucnredlist.org](https://apiv3.iucnredlist.org) → request a token.
2. `IUCN_API_TOKEN` — B's rarity engine needs this once it moves off the
   placeholder in `backend/app/services/gbif_iucn.py`.

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
