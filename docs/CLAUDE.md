# CLAUDE.md — Sindh Agents

> Prescriptive project doc for Claude Code. Read this file every session before writing code. If any rule below conflicts with a task instruction, this file wins — flag the conflict and stop.

---

## 1. What this project is

**Sindh Agents** is a WhatsApp-first AI employee for Pakistani SMEs. Owner deploys an AI agent that reads their Excel stock sheet, talks to buyers in Roman Urdu, and tracks compliance deadlines. MVP is a hackathon build — single Stock Agent per SME, web chat widget instead of WhatsApp (Phase 2 swap), no payments, no live tax filing.

**You are Claude Code. Your job is to ship the MVP against three source-of-truth documents:**

- `dashboard_spec.md` — every screen, component, and data contract for the frontend
- `api-contract.md` — every route, request/response type, error, and rate limit
- This file — code style, invariants, do/don't for THIS repo

**Not source of truth (do not derive rules from these):**
- Vault notes (`Roadmap.md`, `Blockers.md`, `Decisions.md`) — for humans, not you
- Prior commits, prior branches — code drifts; specs don't

---

## 2. Voice and comment discipline

**The single most-broken rule in AI-generated code: over-commenting.**

- Comments explain **why**, never **what**. If the code says what, adding a comment that says the same what is noise.
- Function/variable names do the *what*. `calculateOrderTotal()` needs no header comment saying "calculates order total."
- Comments are for: non-obvious business rules ("Buyer's phone is masked at API layer per `api-contract.md` §0.5"), reversal notices ("This looks like a race condition — it isn't because Neon serializes on `sme_id`"), or references to a spec section.
- If you find yourself writing a comment because the code is confusing, rewrite the code instead.
- JSDoc/TSDoc on **exported functions only**, and only when the return shape isn't obvious from the TS type.
- **No file-header comment blocks.** No `/* * * Copyright * * */`. The repo is proprietary; the git history is authorship.
- **No commented-out code.** Delete it. Git preserves it.
- **No TODO comments without an owner initial and a linked issue.** `// TODO(arham): retry logic — see #42`. `// TODO: fix later` is banned.
- **No emojis** in code, comments, commits, or logs. Ever.

**Naming — sentence-case rules from the design system also apply to code identifiers where sensible:**

- Files: `kebab-case.ts` (e.g., `message-bubble.tsx`, `send-otp.ts`).
- Directories: `kebab-case`.
- Components: `PascalCase` (React convention).
- Functions, variables: `camelCase`.
- Types, interfaces, classes: `PascalCase`. Prefer `type` over `interface` unless declaration-merging is needed.
- Constants exported for reuse: `SCREAMING_SNAKE_CASE`.
- Enums: don't use enum — use `as const` object literals.

---

## 3. Tech stack (locked — do not deviate)

| Layer | Choice |
|---|---|
| Frontend framework | Next.js 14 App Router |
| Frontend styling | Tailwind + shadcn/ui |
| Frontend language | TypeScript strict mode |
| Backend | FastAPI (Python 3.11) |
| Backend language | Python 3.11 with strict type hints |
| Database | Neon Postgres (dev = free tier, staging = paid) |
| Vector store | Qdrant Cloud |
| LLM | Groq — Llama 3.3 70B Instruct |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024-dim) |
| Auth | BetterAuth (dashboard), unauthenticated widget |
| SMS | Twilio (staging) / stdout logging (dev) |
| Local dev | Docker Compose (both apps + local Postgres) — see `infra/docker-compose.dev.yml` |
| Deployment | Vercel (FE), Docker Compose on shared VPS (BE) |

**Version pins:** first PR sets `package.json` and `pyproject.toml` versions. Do not bump without an ADR entry.

**Forbidden without ADR:**
- Adding UI libraries beyond shadcn (no MUI, Chakra, Ant, Mantine, Radix outside shadcn primitives).
- Adding state libraries (no Redux, Zustand, Jotai, Recoil in MVP — server components + `useState` suffice).
- Adding ORM abstractions on top of the base repository (see §7).
- Adding Python type-checkers besides `mypy --strict`.
- Introducing runtime schema validation libraries (Pydantic on backend is the choice — no Zod on backend, no marshmallow).
- Frontend gets Zod for runtime API validation. No other runtime validators.

---

## 4. Repo structure

```
/
├── apps/
│   ├── web/                        # Next.js 14 dashboard + widget host
│   │   ├── app/                    # App Router
│   │   ├── components/
│   │   ├── lib/
│   │   ├── types/
│   │   ├── public/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   └── .dockerignore
│   └── backend/                    # FastAPI
│       ├── src/
│       │   ├── api/                # HTTP routes
│       │   ├── agents/             # narrator, planner, orchestrator
│       │   ├── tools/              # MCP-shaped tool functions
│       │   ├── repositories/       # SME-scoped DB access
│       │   ├── services/           # cross-cutting (OTP, embeddings)
│       │   └── main.py
│       ├── migrations/             # alembic
│       ├── seeds/                  # dev seed data
│       ├── tests/
│       ├── pyproject.toml
│       ├── Dockerfile
│       └── .dockerignore
├── packages/
│   └── shared-types/               # TS types generated from Pydantic (Phase 2 — skip in MVP)
├── docs/
│   ├── CLAUDE.md                   # this file
│   ├── dashboard_spec.md
│   ├── api-contract.md
│   ├── tools_spec.md
│   ├── db_schema.md
│   ├── env_setup.md
│   ├── agent_prompts.md
│   ├── eval_spec.md
│   ├── seed_data.md
│   ├── strings.ts.md               # Roman Urdu catalog spec
│   └── MVP_v1.md
├── infra/
│   ├── docker-compose.dev.yml       # db (Postgres) + backend + web
│   └── docker-compose.staging.yml  # backend + web
├── .env.example
├── .gitignore
├── README.md
└── ponytail.config.json            # if Ponytail plugin needs it
```

**Monorepo tool:** none in MVP. `apps/web` and `apps/backend` are independent — deploy separately, no shared build. Do not add Turbo, Nx, or pnpm workspaces. Manual `npm install` and `pip install` in each app dir.

**Do not create:**
- Extra top-level dirs (`shared/`, `utils/`, `common/`) — put helpers in the app that uses them.
- `src/` inside `apps/web/` — Next.js App Router uses `app/` at the root of `apps/web/`.
- `index.ts` barrel files. Import from the file, not from a barrel. Prevents circular imports and speeds up TS compile.

---

## 5. TypeScript rules (apps/web)

**tsconfig.json — non-negotiable:**
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "noPropertyAccessFromIndexSignature": true,
    "isolatedModules": true,
    "target": "ES2022",
    "moduleResolution": "bundler"
  }
}
```

**Rules:**
- No `any`. If you truly need dynamic, use `unknown` and narrow. `any` fails PR review.
- No `!` non-null assertion outside of tests. Prove the type instead.
- No `as` type casts except at trust boundaries (JSON.parse, fetch response). Every cast is followed by a Zod parse.
- Prefer `type` over `interface`.
- Discriminated unions for state — `type Result = { ok: true; data: T } | { ok: false; error: E }`. Match on `.ok`.
- Server responses go through Zod validation before being trusted. Failed validation = throw `ApiError`, do not silently proceed.

**React rules:**
- Server components by default. Add `'use client'` only when the component needs state, effects, browser APIs, or event handlers.
- No `useEffect` for data fetching in server components (obvious) or in client components fetching from our API (use server components). `useEffect` is only for browser APIs, subscriptions, and cleanup.
- Every `useEffect` has a cleanup or an explanatory `// why: no cleanup — one-shot on mount`.
- Every list needs a stable `key`. Array index is banned as key except in fully static lists you never reorder.
- No inline function definitions in JSX for anything expensive (charts, maps). Fine for onClick handlers on 1-3 buttons.

**Imports:**
- Absolute imports via `@/` from `apps/web/` root.
- Ordering enforced by Prettier + `eslint-plugin-import`: (1) node builtins, (2) external packages, (3) `@/` internal, (4) relative.

---

## 6. Python rules (apps/backend)

**pyproject.toml — non-negotiable:**
- Python 3.11 pinned.
- `mypy` with `--strict`.
- `ruff` for linting.
- `black` for formatting.
- `pytest` for tests.

**Rules:**
- Every function has type hints. `def foo(x)` fails PR review.
- Use `Pydantic v2` for request/response models. FastAPI auto-validates.
- No `Any` type outside of test fixtures.
- No `try: ... except Exception`. Catch specific exceptions or don't catch. Blanket except hides bugs.
- Async everywhere for I/O — Neon queries, Groq calls, Qdrant queries, Twilio. `def` is for pure functions.
- Repositories return domain types, not DB rows. Row → domain mapping happens in the repo, not in the route handler.

**Structure per module:**
```
apps/backend/src/api/conversations.py
- FastAPI router (route handlers)
- Handlers are thin — call service or repo, return response

apps/backend/src/services/conversation_service.py
- Business logic — no DB, no HTTP, just orchestration

apps/backend/src/repositories/conversation_repository.py
- DB access. Inherits BaseRepository.
- ALL queries include `sme_id` filter. See §7.
```

**Route handler pattern:**
```python
@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: ConversationId,
    session: AuthSession = Depends(require_session),
    repo: ConversationRepository = Depends(),
) -> ConversationDetailResponse:
    convo = await repo.get_by_id(conversation_id, sme_id=session.sme_id)
    if convo is None:
        raise HTTPException(404, "NOT_FOUND")
    return ConversationDetailResponse(ok=True, data=convo)
```

---

## 7. Invariants — break any of these and the phase gate fails

### 7.1 SME scoping

Every DB query MUST filter by `sme_id`. Enforced by `BaseRepository`:

```python
class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def scoped(self, sme_id: SmeId) -> "ScopedQuery":
        """Every query goes through this. No raw self.db.execute() in child repos."""
        ...
```

Child repositories that bypass `self.scoped(sme_id)` fail code review. A single cross-tenant leak = Phase 1 gate failure per `Roadmap.md`.

### 7.2 Deterministic narrator

The narrator LLM emits the final text SME/buyer sees. **The narrator must not invent numbers.** If a tool returned `stock=450`, the reply says "450". If the tool returned nothing, the reply says "pata nahi karna paya" (couldn't check), not a guess.

Enforced by:
- Tool outputs are inserted into the narrator prompt as verbatim strings.
- Every eval case in Baneen's corpus asserts numeric equality with tool outputs.
- If eval regresses below 80% hard-fail, this invariant is likely broken.

### 7.3 Audit is synchronous

Audit row write is in the same DB transaction as the agent-message row write. If audit fails, reply fails. Never write the message and then queue the audit — the audit drawer would show nothing and the trust wedge dies.

### 7.4 No PII in the browser

- `localStorage` — session state only (theme preference, sidebar collapsed state). Nothing else.
- `sessionStorage` — banned.
- Cookies — auth cookie only, via BetterAuth.
- Console logs in prod builds — banned. Use the logger.

### 7.5 Widget contract = Meta webhook shape (both channels must stay in sync)

The widget's inbound payload matches Meta's WhatsApp Cloud API webhook shape byte-for-byte except for `messaging_product: 'widget'`. WhatsApp comes in via the same handler in Phase 2 (or demo-day sandbox flip) with `messaging_product: 'whatsapp'`.

**Any change to the widget inbound payload must update BOTH channels' contracts in the same PR.** No widget-only fields. No widget-specific extensions. If the shape needs to diverge, that's an ADR, not a PR.

**Three disciplines from day one — non-negotiable:**
1. Outbound channel abstraction (`OutboundChannel` protocol in `apps/backend/src/channels/`). Widget implementation writes to `messages` table for long-poll. `WhatsAppChannelStub` logs to stdout and exists from PR #1 — swapping to Twilio is not "designing an interface for the first time."
2. `conversations.channel` column exists from initial schema. No mid-project migration.
3. `FEATURE_WHATSAPP=false` in env from day one. Flipping it registers the real Twilio channel. Absence of Twilio env vars when flag is `true` = backend refuses to start.

### 7.6 Roman Urdu strings are author-time

Every user-facing string lives in `apps/web/lib/strings.ts` with a key. No hardcoded Urdu (or English) in JSX. Baneen reviews all values before merge. Runtime i18n (dynamic locale switching) is Phase 2 — MVP has one language: Roman Urdu, with English fallback for judges.

### 7.7 Verbatim rendering

`text` fields from the API render verbatim in the UI. Do not `toLocaleString()` numbers, do not `formatCurrency()`, do not re-punctuate. What the narrator emitted is what the buyer/SME sees. This is Architecture Principle 1 extended to the FE.

---

## 8. Testing rules

**Two levels only in MVP:**

1. **Unit tests** — pytest for backend, Vitest for frontend. Colocated: `foo.py` → `foo_test.py`, `Foo.tsx` → `Foo.test.tsx`.
2. **Eval tests** — Baneen's 30-query Roman Urdu corpus. Run in CI on every PR that touches `apps/backend/src/agents/` or `apps/backend/src/tools/`. Below 80% hard-fail rate = PR does not merge.

**Not in MVP:**
- E2E tests (Playwright) — Phase 2.
- Load tests — Phase 2.
- Visual regression — never.

**Test rules:**
- Test names describe behavior, not implementation. Good: `it("returns 404 when conversation belongs to another SME")`. Bad: `it("calls repo.getById once")`.
- No test-only branches in production code. If code needs a test seam, it's a design smell — refactor.
- No mocks of your own code. Mock only external services (Groq, Qdrant, Twilio, Neon in unit tests).
- Every route handler has at least: happy path, 401 unauth, 404 wrong SME, 400 validation.

---

## 9. Git and PR rules

**Branch names:** `<owner>/<phase>-<slug>`. Examples: `arham/mvp-auth-otp`, `ayesha/mvp-dashboard-home`, `baneen/mvp-eval-corpus`.

**Commit messages:** `<type>(<scope>): <subject>` — Conventional Commits.
- Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`.
- Scope: `web`, `backend`, `db`, `docs`, `infra`.
- Subject: sentence case, no period, ≤72 chars.

Examples:
- `feat(backend): add /api/audit/[messageId] handler`
- `fix(web): mask buyer phone in conversation list`
- `docs: sync api-contract with dashboard-spec after audit drawer route change`

**PR rules:**
- One phase feature per PR. If it touches more than one, split.
- Description references spec section: `Implements dashboard_spec.md §3.4 + api-contract.md §2.3`.
- Every PR runs: typecheck (both apps) + lint + unit tests + Baneen's eval (if agent/tools changed).
- No merging own PR without one review. In the three-person hackathon team, review is 15 min, not a formality.

**Do not commit:**
- `.env`, `.env.local`, `.env.staging` — only `.env.example`.
- `node_modules/`, `__pycache__/`, `.next/`, `.venv/`.
- Log files, coverage reports.
- Screenshots (put in `docs/img/` if truly needed for a spec).

---

## 10. Running locally

**Recommended — Docker Compose** (no Python/Node version to manage; both apps + a local
Postgres, so dev doesn't depend on the Neon credentials at all):

```bash
git clone <repo>
cd sindh-agents
cp .env.example .env
# Fill in .env — see docs/env_setup.md

cd infra
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.dev.yml up -d backend web
curl http://localhost:8001/health
```

`backend` binds host port **8001** (container port stays 8000) — remapped from 8000 since that
port is commonly taken by other local projects. Native `uvicorn` below is unaffected and still
runs on 8000.

`backend`/`web` bind-mount their source, so edits reload without a rebuild; rebuild only when
`pyproject.toml`/`package.json` changes (`docker compose -f docker-compose.dev.yml build`).
Migrations are a one-off command, not automatic on every boot — rerun the `alembic upgrade
head` line whenever a new migration lands.

**Alternative — native:**

```bash
# One-time setup
git clone <repo>
cd sindh-agents
cp .env.example .env
# Fill in .env — see docs/env_setup.md

# Backend
cd apps/backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m seeds.pilot_sme      # loads test SME + agents + convos + audit
uvicorn src.main:app --reload --port 8000

# Frontend (new terminal)
cd apps/web
npm install
npm run dev                    # http://localhost:3000
```

**Common tasks:**
```bash
# Run backend tests
cd apps/backend && pytest

# Run frontend tests
cd apps/web && npm test

# Run Baneen's eval (from repo root)
cd apps/backend && python -m evals.roman_urdu

# Typecheck
cd apps/web && npm run typecheck
cd apps/backend && mypy src

# Format
cd apps/web && npm run format
cd apps/backend && black src && ruff check --fix src

# Reset dev DB
cd apps/backend && alembic downgrade base && alembic upgrade head && python -m seeds.pilot_sme
```

---

## 11. When to stop and ask

You are Claude Code. You do not silently guess. Stop and flag if:

- A task instruction contradicts this file, `dashboard_spec.md`, or `api-contract.md`.
- A required file doesn't exist (e.g., asked to modify `agent_prompts.md` and it's not in `docs/`).
- Environment variables mentioned in a task aren't in `.env.example` (see `env_setup.md`).
- A change would break invariant §7.1–§7.7. Do not "fix" the invariant.
- You're asked to add a dependency not in the locked stack (§3).
- A spec section is ambiguous. Ask before implementing your interpretation.

**Do not:**
- Refactor code that isn't in the task's scope.
- Add "nice-to-have" features not in the task.
- Rename existing files unless the task says so.
- "Improve" existing patterns you don't like. If a pattern is wrong, propose in a separate PR.

---

## 12. Do / Don't (quick reference)

| Do | Don't |
|---|---|
| Server components by default | Add `'use client'` reflexively |
| Zod-validate every API response | Trust JSON.parse output |
| Filter by `sme_id` in every query | Assume "the framework will handle it" |
| Write eval cases when adding tools | Ship a tool without an eval case |
| Use `unknown` when types are unclear | Reach for `any` |
| Reference spec sections in PR desc | Merge without spec traceability |
| Ask when contract is ambiguous | Implement your interpretation |
| Delete commented-out code | Preserve "just in case" |
| Roman Urdu strings in catalog | Hardcode in JSX |
| Verbatim number rendering | Format currency client-side |
| One feature per PR | Bundle unrelated changes |
| Comment *why*, name *what* | Add header comments to every file |

---

## 13. Debugging discipline

When something breaks:

1. **Reproduce deterministically** before fixing. Not "sometimes it works." What was the input?
2. **Read the log line, not the summary.** `X-Request-ID` in the error toast → grep backend logs.
3. **Bisect.** If Baneen's eval regresses, `git bisect` between last-passing and current.
4. **Do not add a try/except to make a failure disappear.** Understand it. If a failure is expected under some input, guard the input, don't swallow the error.
5. **Ask before pushing a fix that you don't understand why it works.**

---

## 14. When Ponytail plugin comes into play

You mentioned Ponytail plugin will be used. If it introduces:
- Its own file conventions → follow them, but flag any conflict with §4.
- Its own commit rules → follow them, but flag any conflict with §9.
- Custom tooling → document in this file (add a §15).

Do not silently adapt to plugin conventions that break the invariants in §7.

---

## Change log

| Date | Change |
|---|---|
| 2026-07-23 | Initial draft. Prescriptive per Arham's call. Sole source-of-truth for repo conventions. |
| 2026-07-23 | Swap OpenAI embeddings → Cohere `embed-multilingual-v3.0` (better Roman Urdu, no OpenAI key needed). Tighten §7.5 with three-disciplines rule for widget/WA parity. |
| 2026-07-24 | Containerize local dev per Arham's call: `docker-compose.dev.yml` now runs `db` (local Postgres) + `backend` + `web`, not just backend. §3, §4, §10 updated. Both Dockerfiles added and boot-verified end-to-end (migration, seed, `/health`, frontend root all confirmed working in containers). |
| 2026-07-24 | `backend`'s Docker host port remapped 8000 → 8001 (container port unchanged) — 8000 was already bound by an unrelated local project. §10 updated. |
| 2026-07-24 | Reversed the "Excel reingest out of scope for MVP" call from `tools_spec.md` per `phase/P6.md` — sellers can now upload/replace their stock sheet from the dashboard's new `/inventory` page (`POST /api/excel/reingest`) instead of only via seed script. New dependencies: `openpyxl`, `python-multipart`. |
