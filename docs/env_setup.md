---
project: Sindh Agents
type: env-setup
status: draft (awaiting Arham sign-off)
owner: Arham
created: 2026-07-23
scope: Hackathon MVP
pairs_with: CLAUDE.md, db_schema.md, api-contract.md
---

# Environment Setup (MVP)

> **Purpose:** Every environment variable, every secret, every local-dev override. If Claude Code needs a variable to write code, it MUST be listed here. If it's not here, it doesn't exist — flag and ask.

---

## 0. Rules

- **One `.env.example`** at repo root — the ONLY committed env file. All other env files are gitignored.
- **Local dev uses `.env`** at repo root, symlinked or copied into `apps/web/.env.local` and `apps/backend/.env` as needed.
- **Staging and prod use platform secret stores** — Vercel env vars (FE), Docker Compose `env_file` referencing a secret file (BE). Never commit real secrets.
- **Naming:** `SCREAMING_SNAKE_CASE`. Frontend public vars prefixed `NEXT_PUBLIC_`. Everything else is server-only.
- **Type discipline:** all env vars are strings at the OS level. Backend parses via Pydantic `Settings`; frontend parses via a Zod schema in `apps/web/lib/env.ts`. Missing required var = process exits at startup, not at first use.

---

## 1. Full `.env.example`

```bash
# =============================================================================
# Sindh Agents — .env.example
# Copy to .env and fill in real values. Never commit .env.
# =============================================================================

# ------------------------- App identity ---------------------------
NODE_ENV=development                       # development | staging | production
LOG_LEVEL=info                             # debug | info | warn | error
APP_TIMEZONE=Asia/Karachi                  # do not change — see db_schema.md §0.2

# ------------------------- URLs -----------------------------------
# Frontend
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_WIDGET_URL=http://localhost:3000/widget
NEXT_PUBLIC_API_BASE_URL=http://localhost:3000/api

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_PUBLIC_URL=http://localhost:8000   # used by widget outbound long-poll

# ------------------------- Database -------------------------------
# Neon Postgres. Get from https://console.neon.tech
# Dev: use the "dev" branch. Staging: use "staging" branch. Prod: "main".
DATABASE_URL=postgresql+asyncpg://user:pass@ep-example.neon.tech/sindh_agents_dev
DATABASE_URL_SYNC=postgresql://user:pass@ep-example.neon.tech/sindh_agents_dev   # for alembic

# Connection pool
DB_POOL_SIZE=5
DB_POOL_MAX_OVERFLOW=10
DB_POOL_TIMEOUT_SECONDS=30

# ------------------------- Qdrant ---------------------------------
QDRANT_URL=https://xxxxxxxx.qdrant.io
QDRANT_API_KEY=changeme

# ------------------------- LLM (Groq) -----------------------------
GROQ_API_KEY=changeme
GROQ_MODEL=llama-3.3-70b-versatile         # exact model string per ADR-002
GROQ_TIMEOUT_SECONDS=15

# Fallback model — used only if GROQ_MODEL 5xx twice in a row within 60s.
GROQ_FALLBACK_MODEL=llama-3.1-70b-versatile

# ------------------------- Embeddings (Cohere) --------------------
# Cohere multilingual — chosen over OpenAI for Roman Urdu quality.
# Free tier: 1000 calls/min, 100K/month. Covers pilot easily.
COHERE_API_KEY=changeme
COHERE_EMBEDDING_MODEL=embed-multilingual-v3.0    # 1024 dim, 100+ languages including Urdu-family
COHERE_INPUT_TYPE_INGEST=search_document           # for storing memory
COHERE_INPUT_TYPE_QUERY=search_query               # for buyer message queries

# ------------------------- WhatsApp channel (Phase 2 / demo-day flip) ----
# Widget-only in MVP. Twilio WA sandbox wired but disabled by default.
# Flip FEATURE_WHATSAPP=true on demo day or in Phase 2 to activate.
# Backend refuses to start if flag=true and any Twilio var is empty.
FEATURE_WHATSAPP=false
TWILIO_WHATSAPP_ACCOUNT_SID=
TWILIO_WHATSAPP_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=                              # e.g., 'whatsapp:+14155238886' (sandbox number)
TWILIO_WHATSAPP_WEBHOOK_SECRET=                    # for validating Twilio signature

# ------------------------- Auth (BetterAuth) ----------------------
# Generate a 64-char random string. See §4 for command.
BETTER_AUTH_SECRET=changeme_64_random_chars_here
BETTER_AUTH_URL=http://localhost:3000
SESSION_MAX_AGE_HOURS=168                  # 7 days

# OTP settings
OTP_TTL_SECONDS=300                        # 5 minutes
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5

# ------------------------- SMS (Twilio) ---------------------------
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=changeme
TWILIO_FROM_NUMBER=+15551234567

# Dev override — if true, OTPs log to stdout instead of sending real SMS.
# Set false in staging and prod.
DEV_SMS_LOG_TO_STDOUT=true

# ------------------------- Rate limits ----------------------------
# See api-contract.md §0.6 for canonical limits.
# These are runtime overrides for load testing; leave at defaults for MVP.
RATE_LIMIT_OTP_PER_HOUR=3
RATE_LIMIT_DASHBOARD_PER_MIN=120
RATE_LIMIT_WIDGET_INBOUND_PER_MIN=30
RATE_LIMIT_WIDGET_OUTBOUND_PER_MIN=60

# ------------------------- Widget CORS ----------------------------
WIDGET_ALLOWED_ORIGINS=http://localhost:3000,https://demo.sindhagents.com

# ------------------------- Feature flags --------------------------
# Toggles the manual "payment received" dashboard button (ADR-010).
# false in MVP demo, true in Phase 1 pilots.
FEATURE_PAYMENT_TOGGLE=false

# Toggles the audit drawer "flag as wrong" button.
# true in MVP — trust wedge depends on it.
FEATURE_AUDIT_FLAG=true

# ------------------------- Observability --------------------------
# MVP: local file logs. Phase 3: Prometheus + Grafana.
LOG_FORMAT=json                            # json | pretty
LOG_FILE=./logs/backend.log                # dev only; unset in prod

# Request ID header echoed to clients per api-contract.md §0.13.
REQUEST_ID_HEADER=X-Request-ID

# ------------------------- Dev-only overrides ---------------------
# Skip real OTP send — always accept "123456" in dev.
DEV_SKIP_OTP_VERIFY=false

# Auto-seed on backend startup. false in staging/prod.
DEV_AUTO_SEED=true

# Pretend Excel snapshot is always fresh — bypasses ingest freshness check.
DEV_EXCEL_ALWAYS_FRESH=true
```

---

## 2. Variable index — what each does + where it's read

| Variable | Read by | Required in dev | Required in prod | Notes |
|---|---|---|---|---|
| `NODE_ENV` | web + backend | Yes | Yes | Controls log verbosity, error stack traces |
| `LOG_LEVEL` | backend | No (default `info`) | Yes | |
| `APP_TIMEZONE` | backend | No (default `Asia/Karachi`) | Yes | Do not override |
| `NEXT_PUBLIC_APP_URL` | web (client + server) | Yes | Yes | Public — visible in browser |
| `NEXT_PUBLIC_WIDGET_URL` | web (client + server) | Yes | Yes | Public |
| `NEXT_PUBLIC_API_BASE_URL` | web (client + server) | Yes | Yes | Public |
| `BACKEND_HOST` | backend | Yes | Yes | `0.0.0.0` in prod containers |
| `BACKEND_PORT` | backend | Yes | Yes | |
| `BACKEND_PUBLIC_URL` | web (server only) | Yes | Yes | Used by server components fetching backend |
| `DATABASE_URL` | backend (asyncpg) | Yes | Yes | Async form for FastAPI |
| `DATABASE_URL_SYNC` | alembic | Yes | Yes | Sync form for migrations |
| `DB_POOL_*` | backend | No | Yes | Tune in Phase 2 |
| `QDRANT_URL` | backend | Yes | Yes | |
| `QDRANT_API_KEY` | backend | Yes | Yes | Secret |
| `GROQ_API_KEY` | backend | Yes | Yes | Secret |
| `GROQ_MODEL` | backend | Yes | Yes | ADR-002 pinned |
| `GROQ_TIMEOUT_SECONDS` | backend | No | Yes | |
| `GROQ_FALLBACK_MODEL` | backend | No | Yes | Used on 5xx retries |
| `COHERE_API_KEY` | backend | Yes | Yes | Secret. Replaces OpenAI per revised ADR-003. |
| `COHERE_EMBEDDING_MODEL` | backend | No | Yes | `embed-multilingual-v3.0` (1024-dim) |
| `COHERE_INPUT_TYPE_INGEST` | backend | No | Yes | Cohere requires input_type for v3 models |
| `COHERE_INPUT_TYPE_QUERY` | backend | No | Yes | Cohere requires input_type for v3 models |
| `FEATURE_WHATSAPP` | backend | No (default false) | No | Flip true to enable Twilio WA channel |
| `TWILIO_WHATSAPP_ACCOUNT_SID` | backend | Only if `FEATURE_WHATSAPP=true` | Only if flag on | Secret |
| `TWILIO_WHATSAPP_AUTH_TOKEN` | backend | ↑ | ↑ | Secret |
| `TWILIO_WHATSAPP_FROM` | backend | ↑ | ↑ | `whatsapp:+14155238886` format |
| `TWILIO_WHATSAPP_WEBHOOK_SECRET` | backend | ↑ | ↑ | Validates inbound Twilio signature |
| `BETTER_AUTH_SECRET` | web + backend | Yes | Yes | Secret — must match between apps |
| `BETTER_AUTH_URL` | web | Yes | Yes | Base URL for auth flows |
| `SESSION_MAX_AGE_HOURS` | backend | No | Yes | |
| `OTP_TTL_SECONDS` | backend | No | Yes | |
| `OTP_RESEND_COOLDOWN_SECONDS` | backend | No | Yes | |
| `OTP_MAX_ATTEMPTS` | backend | No | Yes | |
| `TWILIO_ACCOUNT_SID` | backend | If `DEV_SMS_LOG_TO_STDOUT=false` | Yes | Secret |
| `TWILIO_AUTH_TOKEN` | backend | If `DEV_SMS_LOG_TO_STDOUT=false` | Yes | Secret |
| `TWILIO_FROM_NUMBER` | backend | If `DEV_SMS_LOG_TO_STDOUT=false` | Yes | |
| `DEV_SMS_LOG_TO_STDOUT` | backend | Yes | Must be `false` | Kill switch: prod=false |
| `RATE_LIMIT_*` | backend | No | No | Override for load tests |
| `WIDGET_ALLOWED_ORIGINS` | backend | Yes | Yes | Comma-separated |
| `FEATURE_PAYMENT_TOGGLE` | web + backend | No (default false) | No | Phase 1 flip |
| `FEATURE_AUDIT_FLAG` | web + backend | No (default true) | Yes | Keep true in MVP |
| `LOG_FORMAT` | backend | No | Yes | |
| `LOG_FILE` | backend | No | Unset | Container stdout in prod |
| `REQUEST_ID_HEADER` | web + backend | No | No | Rarely overridden |
| `DEV_SKIP_OTP_VERIFY` | backend | No (default false) | Must be `false` | Kill switch |
| `DEV_AUTO_SEED` | backend | No | Must be `false` | Kill switch |
| `DEV_EXCEL_ALWAYS_FRESH` | backend | No | Must be `false` | Kill switch |

---

## 3. Kill switches — must be false in staging + prod

These are dev conveniences that must never leak. Backend refuses to start in `NODE_ENV=production` if any is `true`:

```python
# apps/backend/src/config.py
if settings.NODE_ENV == "production":
    for kill_switch in ["DEV_SMS_LOG_TO_STDOUT", "DEV_SKIP_OTP_VERIFY",
                         "DEV_AUTO_SEED", "DEV_EXCEL_ALWAYS_FRESH"]:
        if getattr(settings, kill_switch):
            raise RuntimeError(f"{kill_switch} must be false in production")

# Separate guard: FEATURE_WHATSAPP=true requires all four Twilio WA vars.
if settings.FEATURE_WHATSAPP:
    required = ["TWILIO_WHATSAPP_ACCOUNT_SID", "TWILIO_WHATSAPP_AUTH_TOKEN",
                "TWILIO_WHATSAPP_FROM", "TWILIO_WHATSAPP_WEBHOOK_SECRET"]
    missing = [k for k in required if not getattr(settings, k)]
    if missing:
        raise RuntimeError(f"FEATURE_WHATSAPP=true requires: {missing}")
```

---

## 4. First-time setup commands

### 4.1 Generate secrets

```bash
# BETTER_AUTH_SECRET — 64 random chars
openssl rand -base64 48 | tr -d '\n'
```

### 4.2 Neon setup

1. Create account at https://console.neon.tech (free tier).
2. Create project `sindh-agents`.
3. Create branches: `main` (prod), `staging`, `dev`.
4. For each branch, copy the async connection string into `DATABASE_URL` and the sync form into `DATABASE_URL_SYNC`.
5. Async form: `postgresql+asyncpg://...` (asyncpg driver).
6. Sync form: `postgresql://...` (psycopg2 for alembic).

### 4.3 Qdrant setup

1. Create free-tier cluster at https://cloud.qdrant.io.
2. Copy `QDRANT_URL` (looks like `https://xxxxxx.qdrant.io`) and `QDRANT_API_KEY`.
3. Collections are created programmatically per SME (see `tools_spec.md` §3 Qdrant integration + `db_schema.md` §1.12).

### 4.4 Groq setup

1. Sign up at https://console.groq.com.
2. Create API key. Copy to `GROQ_API_KEY`.
3. Verify `GROQ_MODEL=llama-3.3-70b-versatile` matches the model listed on Groq's console.

### 4.5 Cohere setup

1. https://dashboard.cohere.com — sign up (free tier, no card).
2. Create trial API key. Copy to `COHERE_API_KEY`.
3. Free tier: 1000 calls/min, 100K calls/month. Comfortable for MVP + pilot.
4. Model `embed-multilingual-v3.0` is available on trial keys — no separate provisioning.

### 4.6 WhatsApp channel — deferred to Phase 2 (or demo-day flip)

MVP ships with `FEATURE_WHATSAPP=false`. No Twilio WA setup needed to build or ship the MVP.

**When you're ready to flip (demo day or Phase 2):**

1. Twilio account (free trial covers sandbox).
2. Enable WhatsApp Sandbox in Twilio console → Messaging → Try it out → WhatsApp.
3. Note the sandbox number (e.g., `+1 415 523 8886`) and join keyword.
4. Fill env vars:
   ```
   TWILIO_WHATSAPP_ACCOUNT_SID=ACxxxxxxxxxxxx
   TWILIO_WHATSAPP_AUTH_TOKEN=changeme
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   TWILIO_WHATSAPP_WEBHOOK_SECRET=changeme
   FEATURE_WHATSAPP=true
   ```
5. Point Twilio inbound webhook URL at `https://<your-backend>/api/widget/inbound` — same handler, Twilio proxies the Meta-shaped payload.
6. Restart backend. Cross-check with a `join <keyword>` from your own WhatsApp.

**Pre-demo checklist:** each judge or test-buyer must send `join <keyword>` to the sandbox number ONCE from their WhatsApp before demo. Do this at the booth before the pitch.

### 4.7 Twilio SMS setup (skip for hackathon dev — use stdout)

For hackathon demo, keep `DEV_SMS_LOG_TO_STDOUT=true` and find OTPs in the FastAPI log:

```
INFO: DEV_OTP: phone=+923005551234 otp=482913 expires_in=300s
```

For Phase 1 (pilots):

1. Twilio account, verified sender number, buy a PK-capable number.
2. Fill `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.
3. Flip `DEV_SMS_LOG_TO_STDOUT=false`.

---

## 5. Local setup — end-to-end

Assumes fresh clone, all secrets obtained per §4.

```bash
# 1. Clone + env
git clone <repo> sindh-agents
cd sindh-agents
cp .env.example .env
# Fill in .env — DATABASE_URL, DATABASE_URL_SYNC, QDRANT_*, GROQ_API_KEY,
# COHERE_API_KEY, BETTER_AUTH_SECRET

# 2. Backend
cd apps/backend
python3.11 -m venv .venv
source .venv/bin/activate                                 # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Load env for backend (macOS/Linux)
export $(cat ../../.env | grep -v '^#' | xargs)
# Windows PowerShell: Get-Content ..\..\.env | ForEach-Object { ... }
# (or use direnv, or python-dotenv — auto-loaded by Pydantic Settings)

alembic upgrade head
python -m seeds.pilot_sme

uvicorn src.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd apps/web
ln -s ../../.env .env.local                               # symlink shared env
npm install
npm run dev

# 4. Verify
# Backend health: curl http://localhost:8000/health
# Frontend: http://localhost:3000 — should redirect to /login
# Send test OTP:
#   POST http://localhost:3000/api/auth/send-otp {"phone":"+923005551234"}
# Grep backend log for DEV_OTP line.
# Use that OTP to verify at /login.
```

---

## 6. Docker Compose (local dev — and staging/prod backend)

**As of 2026-07-24, `infra/docker-compose.dev.yml` runs the whole stack**: a local Postgres
(`db`), `backend`, and `web`. Local dev no longer needs the Neon credentials at all —
`DATABASE_URL`/`DATABASE_URL_SYNC` are overridden inside the compose file to point at `db`.

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=sindh_agents
      - POSTGRES_PASSWORD=sindh_agents
      - POSTGRES_DB=sindh_agents_dev
    ports:
      - "5433:5432"   # host 5433 → container 5432; avoids clashing with any other local Postgres
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sindh_agents"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ../apps/backend
    env_file:
      - ../.env
    environment:
      - NODE_ENV=development
      - BACKEND_HOST=0.0.0.0
      - DATABASE_URL=postgresql+asyncpg://sindh_agents:sindh_agents@db:5432/sindh_agents_dev
      - DATABASE_URL_SYNC=postgresql://sindh_agents:sindh_agents@db:5432/sindh_agents_dev
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8001:8000"   # host 8001 → container 8000; 8000 is often taken by other local projects
    volumes:
      - ../apps/backend/src:/app/src
    command: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

  web:
    build: ../apps/web
    env_file:
      - ../.env
    environment:
      - NODE_ENV=development
    ports:
      - "3000:3000"
    volumes:
      - ../apps/web:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      - backend
    command: npm run dev

volumes:
  db_data:
```

Migrations run as a one-off command, not automatically on every container start:

```bash
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.dev.yml up -d backend web
```

`infra/docker-compose.staging.yml` — same two app services (no `db`; staging points at the
real Neon `staging` branch), no volume mounts, env comes from `staging.env` (not committed):

```yaml
services:
  backend:
    build: ../apps/backend
    env_file:
      - /run/secrets/staging.env
    environment:
      - NODE_ENV=staging
    ports:
      - "8000:8000"

  web:
    build: ../apps/web
    env_file:
      - /run/secrets/staging.env
    environment:
      - NODE_ENV=staging
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

**Deployment target is unchanged from CLAUDE.md §3** — Vercel remains the documented default
for the frontend in staging/prod. The `web` service in `docker-compose.staging.yml` is an
available self-hosted alternative, not a replacement; pick one per environment, don't run both
against the same domain.

---

## 7. Vercel env sync (frontend)

Every `NEXT_PUBLIC_*` and BetterAuth var must exist in Vercel for both `preview` and `production` environments.

```bash
# One-shot per env
vercel env add BETTER_AUTH_SECRET production
vercel env add NEXT_PUBLIC_API_BASE_URL production
# ... repeat for every required var per §2

# Verify
vercel env ls
```

Missing var at Vercel = build fails at Zod schema parse (`apps/web/lib/env.ts`).

---

## 8. Secrets rotation (MVP posture — minimal)

- **Hackathon:** no rotation. Same keys for the full build.
- **Phase 1 pilot:** rotate `BETTER_AUTH_SECRET` when adding first paying SME. All existing sessions log out — expected.
- **Phase 2:** proper rotation policy per ADR TBD.

If a key leaks (committed to git, posted publicly): revoke immediately, rotate, force logout all sessions.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Backend fails to start with `RuntimeError: ... must be false in production` | Kill switch is true and `NODE_ENV=production`. Fix env or NODE_ENV. |
| Frontend 500 on every route | `BETTER_AUTH_SECRET` mismatch between FE and BE. Same value, both apps. |
| `DATABASE_URL` connection error, mentions asyncpg | Using sync driver format. Check `postgresql+asyncpg://` prefix. |
| Groq 401 | Key expired or not billing-enabled. |
| Cohere 429 in tests | Free tier rate limit — 1000/min. Add sleep between eval cases. |
| `FEATURE_WHATSAPP=true` startup crash | Missing Twilio WA env vars — see §3 guard. |
| Twilio WA sandbox not responding | Judge/tester didn't send `join <keyword>` first. 24h window since last opt-in expired. |
| OTP never arrives | `DEV_SMS_LOG_TO_STDOUT=true` → grep the log. `false` → Twilio credentials wrong or phone not verified in Twilio trial. |
| Qdrant 404 collection | Collection auto-create didn't run for this SME. Check `qdrant_collection_registry` table + seed script. |
| Frontend can't reach backend | `NEXT_PUBLIC_API_BASE_URL` points to backend port. Check backend actually listening. |

---

## 10. Handoff checklist

Before Claude Code writes anything that reads env:

- [ ] `.env.example` committed to repo root.
- [ ] `.gitignore` includes `.env`, `.env.local`, `.env.*.local`, `staging.env`, `production.env`.
- [ ] `apps/backend/src/config.py` implements Pydantic `Settings` with every required var.
- [ ] `apps/web/lib/env.ts` implements Zod schema for every `NEXT_PUBLIC_*` and server-side var used by Next.js.
- [ ] Both configs fail fast on missing required vars with a clear error naming the var.
- [ ] Kill-switch guard in place per §3.

---

## Change log

| Date | Change |
|---|---|
| 2026-07-23 | Initial draft. Every var used by MVP FE + BE. |
| 2026-07-23 | Swap OpenAI → Cohere multilingual. Add `FEATURE_WHATSAPP` + Twilio WA vars (default off; day-one wiring for zero-refactor swap). Add startup guard for flag+vars consistency. |
| 2026-07-24 | §6 rewritten: `docker-compose.dev.yml` now runs `db` (local Postgres) + `backend` + `web`, not backend-only. Local dev no longer depends on Neon credentials. `docker-compose.staging.yml` gained a `web` service as a self-hosted alternative to Vercel (Vercel stays the default). |
