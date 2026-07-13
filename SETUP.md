# AnimalGO — Team Setup Guide

One-time setup so all four of you can run the app locally against the same
backend services. Do the "Shared accounts" section once as a team (whoever
sets each one up shares the credentials with the others, e.g. via a password
manager — never in Slack/email in plaintext). Then everyone does "Per-machine
setup" individually.

## Shared accounts (do these once, share the resulting values with the team)

### 1. Supabase (Postgres + Auth)
1. Go to [supabase.com](https://supabase.com) → New project.
2. Pick a region close to your team, set a strong DB password (save it —
   you'll need it in the connection string).
3. Once provisioned, go to **Project Settings → Database → Connection string**.
   Use the **Session pooler** (or direct connection) string on port `5432`,
   not the "Transaction" pooler on `6543` — `asyncpg` needs prepared
   statement support that the transaction pooler doesn't give you by default.
   It looks like:
   `postgresql://postgres.xxxx:[PASSWORD]@aws-x-region.pooler.supabase.com:5432/postgres`
   Rewrite the scheme to `postgresql+asyncpg://...` for `backend/.env`'s
   `DATABASE_URL`.
4. Go to **Project Settings → API**. Copy the **Project URL** (`SUPABASE_URL`)
   and the **JWT Secret** (under "JWT Settings" — may be labeled "Legacy JWT
   Secret" depending on when you read this) → `SUPABASE_JWT_SECRET`.
5. Share `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` with the team.

### 2. Cloudflare R2 (photo storage)
1. Cloudflare dashboard → R2 → Create bucket, name it `animalgo-photos`.
2. R2 → Manage API tokens → Create API token → permissions: Object Read &
   Write, scoped to that bucket.
3. Note down: Account ID, Access Key ID, Secret Access Key.
4. `R2_ENDPOINT_URL` is `https://<account_id>.r2.cloudflarestorage.com`.
5. Share `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
   `R2_BUCKET_NAME`, `R2_ENDPOINT_URL` with the team.

### 3. DeepSeek (vision / species ID)
1. [platform.deepseek.com](https://platform.deepseek.com) → API keys → Create.
2. Share `DEEPSEEK_API_KEY` with the team. `DEEPSEEK_BASE_URL` stays the
   default (`https://api.deepseek.com`).
3. Whoever owns cost-tracking (Person D, per the plan doc) should keep an eye
   on usage in the DeepSeek dashboard once real traffic starts.

### 4. Redis (Upstash)
1. [upstash.com](https://upstash.com) → Create database (Redis, regional is
   fine for a 4-person project).
2. Copy the `rediss://...` connection string → `REDIS_URL`.

### 5. IUCN Red List API token (optional for week 1)
1. [apiv3.iucnredlist.org](https://apiv3.iucnredlist.org) → request a token.
2. `IUCN_API_TOKEN` — B's rarity engine needs this once it moves off the
   placeholder in `backend/app/services/gbif_iucn.py`.

## Per-machine setup (everyone does this)

### Prerequisites
- Node 20+, Python 3.11+
- Expo Go app on your phone (fastest way to run the mobile app), or an
  iOS/Android simulator
- Git access to this repo

### Clone and configure
```
git clone <repo-url>
cd animalgo
```

### Backend
```
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt   # requirements.txt + pytest/ruff for local dev
cp .env.example .env
# fill in .env with the shared credentials from above
alembic upgrade head    # applies migrations to the shared Supabase DB
uvicorn app.main:app --reload
```
Visit `http://localhost:8000/health` — should return `{"status": "ok"}`.

### Mobile
```
cd mobile
npm ci                  # uses the committed lockfile, versions are already
                         # pinned to Expo SDK 57 — no need to run expo install
cp .env.example .env
# fill in EXPO_PUBLIC_API_URL (your machine's local IP if testing on a
# physical device via Expo Go, not localhost) and the Supabase keys
npx expo start
```
Scan the QR code with Expo Go, or press `i`/`a` for a simulator.

### Sanity checks before you start building
```
cd backend && source venv/bin/activate && pytest && ruff check .
cd mobile && npx tsc --noEmit && npm run lint && npx expo-doctor
```
All of these should pass clean on a fresh clone.

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
