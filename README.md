# Sindh Agents

WhatsApp-first AI employee for Pakistani SMEs. Hackathon MVP — see `docs/CLAUDE.md` for
conventions and `phase/MVP_v1.md` for the phased build plan.

## One-time setup

```bash
git clone <repo>
cd sindh-agents
cp .env.example .env
# Fill in .env — see docs/env_setup.md
```

## Run with Docker (recommended)

Both apps, plus a local Postgres, run via Docker Compose — no Python/Node version to manage.

```bash
cd infra
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.dev.yml up -d backend web
```

Migrations run as a one-off command, not automatically on every boot — rerun the `alembic
upgrade head` line above whenever a new migration lands.

`db` publishes on host port `5433` (not `5432`) to avoid clashing with any other local
Postgres container; `backend` and `web` publish on the usual `8000`/`3000`. `backend` and
`web` bind-mount their source (`apps/backend/src`, `apps/web`) so edits reload without a
rebuild — rebuild only when `pyproject.toml`/`package.json` changes:

```bash
docker compose -f docker-compose.dev.yml build backend web
```

**Gotcha:** `web`'s `node_modules` lives in an anonymous volume (so the fast image copy isn't
shadowed by the slow bind-mounted source). Anonymous volumes persist across rebuilds/recreates,
so after changing `apps/web/package.json` a plain rebuild + recreate can still run against the
*old* `node_modules`. If `web` logs "Module not found" for something you just added, do:

```bash
docker compose -f docker-compose.dev.yml rm -f -s -v web
docker compose -f docker-compose.dev.yml build web
docker compose -f docker-compose.dev.yml up -d web
```

```bash
docker compose -f docker-compose.dev.yml down       # stop everything
docker compose -f docker-compose.dev.yml logs -f backend   # tail logs
```

## Run natively (alternative)

Backend requires **Python 3.11** (pinned per `docs/CLAUDE.md` §3). If `python3.11` isn't on
your machine, install it first (e.g. `winget install Python.Python.3.11` on Windows, or your
platform's equivalent) — do not substitute a different version.

```bash
# Backend
cd apps/backend
py -3.11 -m venv .venv && .venv\Scripts\activate       # Windows
# python3.11 -m venv .venv && source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
cp ../../.env .env
alembic upgrade head
uvicorn src.main:app --reload --port 8000

# Frontend (new terminal)
cd apps/web
copy ..\..\.env .env.local     # Windows; use cp on macOS/Linux
npm install
npm run dev
```

## Verify

```bash
curl http://localhost:8000/health
```

## Common tasks

```bash
# Backend tests
cd apps/backend && pytest

# Frontend tests
cd apps/web && npm test

# Typecheck
cd apps/web && npm run typecheck
cd apps/backend && mypy src

# Format
cd apps/web && npm run format
cd apps/backend && black src && ruff check --fix src

# Reset dev DB
cd apps/backend && alembic downgrade base && alembic upgrade head
```
