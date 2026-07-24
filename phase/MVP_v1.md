---
project: Sindh Agents
type: build-plan
status: master (living)
owner: Arham
created: 2026-07-23
scope: Hackathon MVP v1
pairs_with: CLAUDE.md, dashboard_spec.md, api-contract.md, db_schema.md, tools_spec.md, env_setup.md
---

# MVP v1 — Master Build Plan

> **Purpose:** Ship-order for the hackathon MVP, feature-phased. Every phase ends in a demo you can show to a human. If a phase doesn't produce something demoable, it's the wrong phase boundary.

> **Rule:** Each `phase_N.md` gets written the day phase N starts, not upfront. This doc is the anchor; per-phase docs are living.

---

## 0. Structure

**7 phases. Each ships something visible.**

| Phase | Feature slice | Ships when demo shows |
|---|---|---|
| **P0** | Foundations | `curl /health` returns 200; DB migrated; env loads |
| **P1** | Auth + shell | Owner logs in with OTP, sees empty dashboard |
| **P2** | Widget + ingestion | Buyer types in widget, message appears in dashboard as "unread" |
| **P3** | Agent loop (deterministic) | Buyer asks "denim kitni hai," agent replies with real number from Excel |
| **P4** | Dashboard views | SME sees agent list, conversation list, message thread, audit drawer |
| **P5** | Eval + polish | Baneen's 30-query eval passes ≥80% hard-fail; Lighthouse mobile ≥90; strings reviewed |
| **P6** | Demo-day WhatsApp flip *(optional)* | Judge messages agent from real WhatsApp; agent replies on WhatsApp |

**Not phases:** unit tests (colocated per feature), commit hygiene (per PR), documentation updates (per feature).

---

## 1. Rules that apply to every phase

- **Phase gate is user-visible.** "The backend compiles" is not a gate. "You can see X happen" is.
- **Every PR names the phase in its title:** `feat(P3): agent orchestrator + tool executor`.
- **No cross-phase scope creep.** If a phase 4 feature is easier while you're touching phase 3 code — resist. It's how MVPs slip.
- **Blocking gate:** every phase has a "done means" section. If you can't check every box, phase is not done.
- **CLAUDE.md invariants (§7) apply to every phase.** Non-negotiable across the plan.
- **Ponytail plugin usage:** if the plugin dictates commit/PR/branch conventions that conflict with CLAUDE.md §9, plugin wins locally — but write a superseding ADR before the next phase starts.

---

## P0 — Foundations

**Goal:** repo skeleton that boots. No user-visible features. Everything past P0 assumes this exists.

**Files touched:**
- Root: `.env.example`, `.gitignore`, `README.md`
- `infra/`: `docker-compose.dev.yml` (`db` + `backend` + `web`), `docker-compose.staging.yml` — under `infra/` per CLAUDE.md §4, not root
- `apps/web/`: `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.js`, `app/layout.tsx`, `app/page.tsx` (stub), `lib/env.ts` (Zod schema), `Dockerfile`, `.dockerignore`, `public/.gitkeep`
- `apps/backend/`: `pyproject.toml`, `alembic.ini`, `src/main.py`, `src/config.py` (Pydantic Settings), `src/db.py` (async engine + session), `src/repositories/base.py` (BaseRepository + scoped()), `src/channels/base.py` + `widget.py` + `whatsapp_stub.py`, `src/logging.py`, `migrations/0001_initial_schema.py`, `Dockerfile`, `.dockerignore`
- `apps/backend/seeds/pilot_sme.py` (stub — full data in P4)

**What to expect:**
- `npm run dev` starts Next.js on 3000 (or `docker compose up -d web`).
- `uvicorn` starts FastAPI on 8000 (or `docker compose up -d backend`).
- `GET /health` returns `{ok: true}`.
- `alembic upgrade head` creates all 12 tables per `db_schema.md`.
- Startup fails loudly if any required env var is missing (per `env_setup.md` §3 guard).
- Backend logs show request ID on every request.
- Docker Compose (`infra/docker-compose.dev.yml`) brings up all three (`db`, `backend`, `web`)
  without needing the Neon credentials — the local Postgres is dev's default DB.

**Run (Docker — recommended):**
```bash
cp .env.example .env
cd infra
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.dev.yml up -d backend web
curl http://localhost:8000/health
```

**Run (native — alternative):**
```bash
cp .env.example .env                                # fill in secrets per env_setup.md
cd apps/backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.main:app --reload --port 8000

# new terminal
cd apps/web && npm install && npm run dev
curl http://localhost:8000/health
```

**Done means:**
- [x] Both apps boot in dev without errors.
- [x] `GET /health` returns 200 with request-ID header.
- [x] Alembic migration applied — all 12 tables present (verified against Docker Postgres;
      Neon dev branch still pending confirmation of the credentials in `.env`).
- [x] Kill-switch guard verified (set `NODE_ENV=production DEV_AUTO_SEED=true` → refuses to start).
- [x] `FEATURE_WHATSAPP=true` without Twilio vars → refuses to start.
- [x] Widget outbound channel + WhatsApp stub channel both registered; dispatcher picks widget by default.
- [x] `docker compose -f infra/docker-compose.dev.yml up` boots `db` + `backend` + `web`
      together; pilot SME auto-seeds against the local Postgres on backend startup.

**Deliberately NOT in P0:** any UI beyond a blank home page, any API beyond `/health`, any auth, any agent code, any seed data beyond one SME row.

---

## P1 — Auth + Shell

**Goal:** owner logs in via phone-OTP and lands on an empty dashboard. No agents yet, no conversations yet.

**Files touched:**
- `apps/backend/src/api/auth.py` — `/api/auth/send-otp`, `/verify-otp`, `/logout`, `/me`
- `apps/backend/src/services/otp_service.py` — generate, hash, verify, TTL, resend cooldown
- `apps/backend/src/services/sms_service.py` — Twilio or stdout (dev)
- `apps/backend/src/repositories/session_repository.py`, `otp_repository.py`
- `apps/backend/src/middleware/auth.py` — `require_session` FastAPI dependency
- `apps/web/app/(auth)/login/page.tsx` — phone → OTP two-step
- `apps/web/app/(dashboard)/layout.tsx` — auth gate + header (avatar, logout)
- `apps/web/app/(dashboard)/page.tsx` — empty state
- `apps/web/lib/auth-client.ts` — BetterAuth client wiring
- `apps/web/lib/api.ts` — typed fetch wrapper with error envelope handling
- `apps/backend/seeds/pilot_sme.py` — enroll ONE pilot SME (name, owner, phone) so login has a target

**What to expect:**
- Visit `/` → redirect to `/login`.
- Enter pilot SME's phone → dev log prints `DEV_OTP: phone=+923005551234 otp=482913`.
- Enter OTP → redirect to `/` → see "Assalam-o-alaikum, Aslam bhai" + empty state ("Abhi tak koi agent nahi").
- Refresh page → still logged in.
- Logout dropdown → clears session → back to `/login`.

**Run:**
```bash
# Seed one SME
cd apps/backend && python -m seeds.pilot_sme --only smes

# In backend terminal, watch logs for the OTP
# In browser: http://localhost:3000/login
```

**Done means:**
- [ ] Send OTP works; dev log shows OTP.
- [ ] Verify OTP creates session cookie.
- [ ] Wrong OTP returns 401 with Urdu error message.
- [ ] Rate limit: 4th OTP request within 1h returns 429.
- [ ] `/me` returns the pilot SME identity.
- [ ] Logout invalidates session; subsequent `/me` returns 401.
- [ ] Dashboard shell renders on mobile (360px viewport) without horizontal scroll.

**Deliberately NOT in P1:** agent creation UI, conversation UI, real SMS (stdout fine), password fallback, multi-user per SME.

---

## P2 — Widget + Ingestion

**Goal:** buyer types in a browser widget; message lands in the backend; dashboard shows "1 unread conversation." Agent doesn't reply yet.

**Files touched:**
- `apps/web/components/widget/SindhAgentsWidget.tsx` — self-contained widget
- `apps/web/app/widget/page.tsx` — standalone widget host page for the demo
- `apps/backend/src/api/widget.py` — `/api/widget/inbound`, `/api/widget/outbound`
- `apps/backend/src/services/inbound_message_service.py` — resolves buyer, upserts conversation, inserts message, marks conversation unread
- `apps/backend/src/repositories/buyer_repository.py`, `conversation_repository.py`, `message_repository.py`
- `apps/backend/src/channels/widget.py` — long-poll implementation (LISTEN/NOTIFY or interval)
- `apps/backend/seeds/pilot_sme.py` — extend to seed one Stock Agent row (no tool logic yet, just row)
- `apps/backend/src/services/rate_limit.py` — token-bucket for widget inbound

**What to expect:**
- Visit `/widget` in one tab → widget bubble bottom-right → expand → type name → "Assalam-o-alaikum" bot greeting appears.
- Type "denim kitni hai" → send.
- In the dashboard tab, home shows the conversation card with "1 unread" indicator on Stock Agent.
- Home's recent-conversations section shows the message preview.
- No agent reply yet — buyer sees their own message with a single tick.

**Run:**
```bash
# One-shot seed to get the Stock Agent row in place
cd apps/backend && python -m seeds.pilot_sme

# Two browser tabs
# Tab 1: http://localhost:3000/widget            (buyer)
# Tab 2: http://localhost:3000                   (SME dashboard)
```

**Done means:**
- [ ] Widget UI passes visual sanity check (WhatsApp-like, emerald accent).
- [ ] `POST /api/widget/inbound` accepts Meta-shaped payload, returns 200 with `messageId`.
- [ ] Message written to DB with correct `sme_id` (resolved via `metadata.phone_number_id` mapping).
- [ ] `conversations.channel = 'widget'` set on insert.
- [ ] Long-poll on `/api/widget/outbound` holds up to 25s, returns empty when no reply.
- [ ] Dashboard home reflects the new conversation within 5s of message send (server component + refresh).
- [ ] Idempotency-Key returns same messageId on retry.
- [ ] Rate limit: 31st inbound in 60s returns 429.

**Deliberately NOT in P2:** agent replies (P3), audit ledger (P4 renders it; P3 writes it), conversation-detail screen (P4), search/filter/tabs on conversation list (P4).

---

## P3 — Agent Loop (Deterministic Engine)

**Goal:** buyer's message triggers the agent. Planner picks tools, tools return data, narrator generates Roman Urdu reply with real numbers. Reply appears in the widget and dashboard.

**Files touched:**
- `apps/backend/src/tools/registry.py` — 5-tool registry per `tools_spec.md`
- `apps/backend/src/tools/read_excel_stock.py`, `check_delivery_slot.py`, `lookup_buyer_history.py`, `record_order_intent.py`, `get_current_date.py`
- `apps/backend/src/agents/orchestrator.py` — planner call → tool exec → narrator call → write reply + audit
- `apps/backend/src/agents/planner.py` — Groq call, tool-selection prompt
- `apps/backend/src/agents/narrator.py` — Groq call, deterministic reply prompt
- `apps/backend/src/services/embedding_service.py` — Cohere `embed-multilingual-v3.0` client
- `apps/backend/src/services/qdrant_service.py` — per-SME collection auto-create, upsert on new message, query
- `apps/backend/src/repositories/audit_repository.py`, `excel_stock_repository.py`, `order_intent_repository.py`
- `apps/backend/src/services/inbound_message_service.py` — extend to enqueue agent processing
- `apps/backend/src/workers/agent_worker.py` — async task consumer (in-process for MVP; queue in Phase 1)
- `apps/backend/seeds/pilot_sme.py` — extend to seed excel_snapshot + 15 stock items + 3 buyers (one returning)
- `docs/agent_prompts.md` — planner + narrator prompt text (written before code)

**What to expect:**
- In widget: type "denim kitni hai"
- Within 5s, agent replies: "Bhai, denim 450 pieces hain stock mein. Rate: Rs. 1,200/piece. Kal delivery ho jaayegi."
- Numbers match the seed data exactly (verify by reading `excel_stock_items` row directly).
- In dashboard `/api/audit/[messageId]`, `tool_calls` array populated with `read_excel_stock` + `check_delivery_slot` and their real inputs/outputs.
- Buyer follow-up: "purana customer hoon discount milega?" → agent calls `lookup_buyer_history`; if returning buyer with typical_discount_pct set, agent honors it.

**Run:**
```bash
cd apps/backend && python -m seeds.pilot_sme                # full seed now
# Verify DB
psql $DATABASE_URL_SYNC -c "SELECT sku_canonical, stock, price_per_unit FROM excel_stock_items WHERE sku_canonical='denim-classic';"
# Should print exactly what agent will quote

# Send from widget or via curl
curl -X POST http://localhost:8000/api/widget/inbound \
  -H 'Content-Type: application/json' \
  -d '{"messaging_product":"widget",...}'                  # full payload per api-contract §3.1
```

**Done means:**
- [ ] Planner picks correct tool for "denim kitni hai" (`read_excel_stock`).
- [ ] Narrator reply contains the exact number from the tool output — no invented figures.
- [ ] Audit row written in same transaction as agent message row (verify: kill the DB mid-write, both rollback).
- [ ] Qdrant collection auto-created for pilot SME on first agent processing.
- [ ] `lookup_buyer_history` returns `is_returning=false` cleanly for a new buyer (no hallucinated history).
- [ ] Cross-tenant test: create second SME, send widget message under SME2 credentials; verify SME1's Excel data is not queried.
- [ ] Planner + narrator both hit budget (P95 < 5s for one full agent turn).
- [ ] When Groq is down, `messages.is_pending=true` persists; agent retries on next Groq call.

**Deliberately NOT in P3:** dashboard rendering of agent replies (P4), audit drawer UI (P4), flag button (P4), any tool beyond the 5 registered.

---

## P4 — Dashboard Views

**Goal:** SME sees the full picture — agent list, conversation list with filter/search, message thread with bubbles, tap-to-open audit drawer.

**Files touched:**
- `apps/web/app/(dashboard)/page.tsx` — real data (was empty in P1); agent cards, recent-conversations list
- `apps/web/app/(dashboard)/conversations/page.tsx` — list + search + tabs
- `apps/web/app/(dashboard)/conversations/[id]/page.tsx` — thread view
- `apps/web/app/(dashboard)/conversations/[id]/@audit/[messageId]/page.tsx` — audit drawer (parallel route)
- `apps/web/components/chat/MessageBubble.tsx`, `ToolCallRow.tsx`, `AuditDrawer.tsx`
- `apps/backend/src/api/agents.py`, `conversations.py`, `audit.py` — read endpoints per `api-contract.md` §2
- `apps/web/lib/strings.ts` — full Roman Urdu catalog (draft; Baneen reviews in P5)
- `apps/web/lib/format.ts` — verbatim rendering helpers (mask phone, preview truncation)

**What to expect:**
- Log in → home shows Stock Agent card with real "N messages today" count.
- Tap agent card → jumps to conversation list, filtered to that agent.
- Search "Ali" → filters to Ali Traders' conversation.
- Tap conversation → thread renders WhatsApp-style bubbles, agent bubbles have the magnifier icon.
- Tap magnifier → drawer opens, shows `read_excel_stock` input `{sku: "denim"}` + output `{stock: 450, price_per_unit: 1200}` verbatim.
- Tap the flag button → conversation marked flagged, `/api/conversations` returns it in `flagged` tab.

**Run:**
```bash
# Everything from P3 running.
# Just open browser, log in, click around.
# For fresh data: kick a few messages via widget in one tab, watch dashboard update.
```

**Done means:**
- [ ] Home renders `AgentsResponse` shape from `api-contract.md` §2.1 correctly.
- [ ] Conversation list search matches buyer name (case-insensitive substring) and buyer phone (digits).
- [ ] Tabs (All / Unread / Flagged) filter correctly on server side.
- [ ] Conversation detail auto-marks unread=false on load (side effect per contract §2.3).
- [ ] Audit drawer opens from `?audit=<messageId>` (parallel + intercepting route works).
- [ ] Flag toggle round-trips through `/api/conversations/[id]/flag`.
- [ ] Numbers in agent bubbles are rendered verbatim (no `toLocaleString`).
- [ ] Mobile-first check: primary tasks ≤2 taps on 360px viewport.
- [ ] Read-only footer banner appears on conversation detail: "Agent kar raha hai".

**Deliberately NOT in P4:** agent creation UI, settings page, billing, notifications, Phase-2 features (payment toggle, tax reminders).

---

## P5 — Eval + Polish

**Goal:** hackathon-ready. Baneen's eval passes, mobile hits Lighthouse ≥90, Roman Urdu strings reviewed, demo rehearsed.

**Files touched:**
- `apps/backend/evals/roman_urdu/` — 30-query corpus (Baneen owns), `harness.py`, `run.py`
- `apps/backend/evals/roman_urdu/corpus.jsonl` — the 30 cases, each with buyer message + expected tool calls + expected numeric assertions
- `apps/web/lib/strings.ts` — Baneen review pass on every value
- `.github/workflows/ci.yml` — typecheck + lint + unit + eval, blocking merge to main
- `apps/web/next.config.mjs` — image optimization on, bundle analyzer scripts
- `apps/web/app/(dashboard)/*` — any P4 UX gaps caught during Lighthouse pass
- `docs/eval_spec.md` — corpus format + gate math (written before or alongside)
- `docs/strings.ts.md` — Roman Urdu catalog spec (Baneen sign-off)

**What to expect:**
- `python -m evals.roman_urdu` prints:
  ```
  30 cases, 26 passed hard-fail (86.7%), 4 failed
    FAILED: case #17 — expected stock=450, got 400
    FAILED: case #22 — expected price=1200, got 1220
    ...
  ```
- CI fails PRs that push the pass rate below 80%.
- Lighthouse mobile audit on `/`, `/conversations`, `/conversations/[id]` all ≥90 performance, ≥95 accessibility.
- Every string in the UI is in `strings.ts`; grep for hardcoded Urdu returns zero results outside the catalog.

**Run:**
```bash
# Eval
cd apps/backend && python -m evals.roman_urdu

# Lighthouse (from apps/web)
npm run build && npm run start &
npx lighthouse http://localhost:3000 --preset=perf --form-factor=mobile --output=json > lh-home.json

# String hardcoding check
grep -rEn '[a-zA-Z]+ (karein|karo|milega|hai)[a-zA-Z]?' apps/web/app apps/web/components || echo "clean"
```

**Done means:**
- [ ] Eval ≥80% hard-fail rate (Baneen calls it, not the person who tuned the prompt).
- [ ] Lighthouse mobile: performance ≥90, accessibility ≥95, on all 5 screens.
- [ ] All Roman Urdu strings in `strings.ts`; no hardcoded strings in JSX.
- [ ] Deterministic invariant verified on 5 rehearsed demo queries (numbers match tool outputs exactly).
- [ ] Widget contract Meta-webhook-compat verified: hit `/api/widget/inbound` with a real Meta test payload, response is 200.
- [ ] Deck delivered, all three founders comfortable, dry-run recorded and reviewed.
- [ ] Backup demo path: if internet fails at venue, local Docker Compose can run the full stack offline (Groq requires internet — degradation path shows canned reply).

**Deliberately NOT in P5:** new features, new endpoints, new tools. Anything not in P0–P4 does not enter P5.

---

## P6 — Demo-day WhatsApp Flip *(optional but recommended)*

**Goal:** judge messages the agent from real WhatsApp on their phone. Agent replies. Pitch multiplier.

**Files touched:**
- `.env` — new values for `FEATURE_WHATSAPP`, `TWILIO_WHATSAPP_*`
- Nothing else — the three disciplines from CLAUDE.md §7.5 mean the code paths already exist.

**Prereqs (do these the night before, not on stage):**
- Twilio account created.
- WhatsApp Sandbox enabled in Twilio console.
- Sandbox number + join keyword recorded.
- `ngrok http 8000` or public backend URL configured; Twilio inbound webhook URL points to `<public>/api/widget/inbound`.
- Team's phones opted in with `join <keyword>` — verify a message flows end-to-end.

**Run (demo day, on stage):**
```bash
# 1. Restart backend with flag on
export FEATURE_WHATSAPP=true
export TWILIO_WHATSAPP_ACCOUNT_SID=ACxxx
export TWILIO_WHATSAPP_AUTH_TOKEN=xxx
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
export TWILIO_WHATSAPP_WEBHOOK_SECRET=xxx
uvicorn src.main:app --port 8000

# 2. Judge sends `join <keyword>` from their WhatsApp to the sandbox number
# 3. Judge sends "denim kitni hai" via WhatsApp
# 4. Agent replies via WhatsApp within seconds
# 5. On the demo laptop, dashboard shows the same conversation with channel='whatsapp'
```

**Done means:**
- [ ] Backend starts cleanly with flag+creds.
- [ ] Twilio webhook proxies inbound to `/api/widget/inbound`; handler dispatches to WhatsApp outbound channel.
- [ ] Agent reply sent via Twilio's WhatsApp send API; judge sees it in their WhatsApp thread.
- [ ] Dashboard conversation list shows a WhatsApp icon (not widget icon) on the new row.
- [ ] Audit drawer shows the same tool_calls shape — no channel-specific fields.

**If P6 breaks 30 minutes before demo:** flip `FEATURE_WHATSAPP=false`, restart. Widget-only demo still ships. Do not troubleshoot Twilio on stage.

**Deliberately NOT in P6:** production-grade Twilio (that's Phase 2 per Roadmap), verified business number, opt-in flow automation, message template approvals.

---

## 2. Ownership sketch (advisory — Arham reassigns as reality dictates)

Feature-phased, not owner-phased. Each phase has multiple owners working in parallel.

| Phase | Backend lead | Frontend lead | Eval lead |
|---|---|---|---|
| P0 | Arham (setup, migrations) | Ayesha (Next.js + shadcn init) | — |
| P1 | Arham (auth, OTP, sessions) | Ayesha (login + shell) | — |
| P2 | Arham (inbound + long-poll) | Ayesha (widget UI + home fetch) | — |
| P3 | Arham (agent + tools + Qdrant) | — | Baneen (spot-check outputs) |
| P4 | Arham (read endpoints) | Ayesha (all dashboard screens) | Baneen (audit drawer copy) |
| P5 | — | Ayesha (Lighthouse pass, strings polish) | Baneen (eval corpus + CI gate) |
| P6 | Arham (Twilio wiring the night before) | — | — |

**Escalations per Team.md:** scope conflict → Arham. What "correct" means → Baneen. UX/memory design → Ayesha.

---

## 3. Timeline discipline

**Roadmap.md deliberately does not commit to calendar dates for MVP** because hackathon date is TBD. Same here.

Rough phase durations, honest estimate assuming 3 people ~40h/week:

| Phase | Estimated duration | Notes |
|---|---|---|
| P0 | 2 days | Repo, migrations, env, health checks |
| P1 | 2 days | OTP + shell |
| P2 | 3 days | Widget + ingestion. Long-poll is the tricky part. |
| P3 | 5 days | Largest phase. Agent loop + all 5 tools + Qdrant + audit. |
| P4 | 4 days | Five screens + audit drawer. |
| P5 | 3 days | Eval, polish, rehearsal. |
| P6 | 4 hours | If disciplines held. |

**Total: ~19 days sustained.** Add 30% for reality (~25 days). If hackathon runway is shorter, P6 goes first, then P5 polish is trimmed.

---

## 4. Handoff to Claude Code — what CC needs before each phase

Before starting phase N, the following must exist:

| Phase | Required specs | Required MDs |
|---|---|---|
| P0 | `db_schema.md`, `env_setup.md`, `CLAUDE.md` | All three |
| P1 | `api-contract.md` §1, `dashboard_spec.md` §3.1 | Above + `api-contract.md`, `dashboard_spec.md`, `strings.ts.md` (auth strings block) |
| P2 | `api-contract.md` §3, `dashboard_spec.md` §3.2 | Above + widget contract note |
| P3 | `tools_spec.md`, `agent_prompts.md`, `seed_data.md` | Above + all three |
| P4 | `dashboard_spec.md` §3.2–3.5, `api-contract.md` §2 | Above + final strings pass |
| P5 | `eval_spec.md` | Above + eval spec |
| P6 | Twilio WA section of `env_setup.md` §4.6 | Above (no new MDs) |

**Any phase started before its required specs exist = it's slower, not faster.**

---

## 5. Global blockers to keep in mind

Not repeated per phase; consult before starting any phase:

- **Cross-tenant leak = phase failure.** Every phase must verify §7.1 of CLAUDE.md.
- **Number invention = phase failure.** Every phase touching agent replies verifies §7.2 (deterministic narrator).
- **Widget/WA parity break = phase failure.** Every phase touching payload verifies §7.5 (both channels updated in same PR).
- **Audit write async = phase failure.** Every phase touching agent replies verifies §7.3 (synchronous audit).

If a phase makes you *want* to break one of these to ship faster — the invariant wins. Take the delay.

---

## 6. What's not in MVP v1 (deliberate — future MVP v2 candidates)

Documented so nobody "helpfully" adds them mid-phase:

| Feature | Where |
|---|---|
| Multi-agent orchestration | Phase 3 in `Roadmap.md` |
| Live payments (Easypaisa/JazzCash) | Phase 2 |
| FBR tax filing | Phase 3+ |
| SME agent creation UI | Phase 2 |
| Real MCP transport | Phase 3 |
| Multi-tenancy code path | Phase 2 |
| Enterprise SSO | Phase 3 |
| Tax Reminder Agent | Phase 1 (post-hackathon pilot) |
| Excel re-upload from dashboard | Phase 1 |

---

## 7. Related

- `CLAUDE.md` — invariants that apply to every phase
- `dashboard_spec.md` — UI contract
- `api-contract.md` — HTTP contract
- `db_schema.md` — persistence contract
- `tools_spec.md` — agent tools
- `env_setup.md` — dev + demo env
- `Roadmap.md` (vault) — post-MVP phases (Phase 1–4) — this doc is upstream of Roadmap Phase 1
- `Blockers.md` (vault) — non-code blockers, reversal triggers

---

## Change log

| Date | Change | Owner |
|---|---|---|
| 2026-07-23 | Initial draft — 7 phases (P0–P6), feature-sliced, widget-first + Cohere + demo-day WA flip locked in per Arham's calls. | Arham |
| 2026-07-24 | P0 containerized per Arham's call: `docker-compose.dev.yml` runs `db` (local Postgres) + `backend` + `web`. P0 files-touched/done-means updated; docker-compose files moved to `infra/` (CLAUDE.md §4 location, not the original root path this doc specified). | Arham |
