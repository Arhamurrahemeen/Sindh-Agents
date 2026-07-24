---
project: Sindh Agents
type: db-schema
status: draft (awaiting Arham backend sign-off)
owner: Arham
created: 2026-07-23
scope: Hackathon MVP — Neon Postgres
pairs_with: api-contract.md, tools_spec.md
---

# DB Schema (MVP — Neon Postgres)

> **Purpose:** Every table, column, index, constraint, and scoping rule. This is the source of truth backing `api-contract.md` responses and `tools_spec.md` tool inputs/outputs.

> **Rule zero:** Every table with SME-owned data has a `sme_id` column. Every query filters on it. See §0.3.

---

## 0. Conventions

### 0.1 Naming

- Tables: `snake_case`, plural (`conversations`, `messages`, `audit_entries`).
- Columns: `snake_case`, singular.
- Primary keys: `id` (UUIDv7).
- Foreign keys: `<referenced_table_singular>_id` (e.g., `conversation_id`, `sme_id`).
- Timestamps: `created_at`, `updated_at`, `deleted_at` — always `timestamptz`.
- Booleans: `is_<state>` (`is_flagged`, `is_pending`).

### 0.2 Types

| Domain | Postgres type | Notes |
|---|---|---|
| IDs | `uuid` | UUIDv7 (time-sortable). App generates, not DB default. |
| Timestamps | `timestamptz` | Always. Store UTC, display Asia/Karachi. |
| Currency | `numeric(12,2)` | Never float. PKR has no decimals in practice but schema supports it. |
| Text (short) | `varchar(N)` | With bounded N when we know the ceiling. |
| Text (long) | `text` | Message bodies, notes. |
| JSON | `jsonb` | Never `json`. Audit `tool_calls` uses `jsonb`. |
| Enums | `text` + `CHECK (col IN (...))` | Not Postgres ENUM type — schema evolves too fast for ALTER TYPE. |

### 0.3 SME scoping — enforced two ways

**Application layer (primary):** `BaseRepository.scoped(sme_id)` in `apps/backend/src/repositories/base.py`. Every child repo goes through it. Direct `db.execute()` in child repos fails PR review (see `CLAUDE.md` §7.1).

**Database layer (defense in depth):** Row Level Security (RLS) on every SME-scoped table:

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_sme_isolation ON conversations
  USING (sme_id = current_setting('app.current_sme_id')::uuid);
```

The app sets `SET LOCAL app.current_sme_id = '<sme_id>'` at transaction start via a FastAPI dependency. If the app forgets to set it, RLS blocks all rows. This is the belt-and-suspenders per `Roadmap.md` Phase 1 gate #4 (zero cross-tenant leaks).

**MVP posture:** RLS is enabled but the `superuser` role bypasses it — used only for migrations and seed scripts. The app connects as `app_role`, which cannot bypass RLS.

### 0.4 Migrations

- **Tool:** Alembic (Python) — matches FastAPI backend.
- **File naming:** `NNNN_<slug>.py` — sequentially numbered, not timestamped. E.g., `0001_initial_schema.py`, `0002_add_flagged_column.py`.
- **Rule:** Never edit a migration after it's merged. Add a new one.
- **Rollback:** Every migration has a `downgrade()`. If it can't be reversed (e.g., data destructive), the migration must be split into two: forward-only + a documented data recovery plan.

### 0.5 Indexes

Every foreign key gets an index. Every column in a `WHERE` clause on a hot path gets an index. Composite indexes ordered by selectivity: (`sme_id`, `<other>`, `<other>`).

---

## 1. Tables

### 1.1 `smes` — tenant root

Every other table hangs off this.

```sql
CREATE TABLE smes (
  id                uuid PRIMARY KEY,
  name              varchar(120) NOT NULL,
  owner_name        varchar(120) NOT NULL,
  owner_phone       varchar(20)  NOT NULL UNIQUE,   -- E.164, +923XXXXXXXXX
  city              varchar(60)  NOT NULL DEFAULT 'Karachi',
  segment           varchar(40)  NOT NULL DEFAULT 'textile',
  onboarded_at      timestamptz  NOT NULL DEFAULT now(),
  created_at        timestamptz  NOT NULL DEFAULT now(),
  updated_at        timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT owner_phone_e164 CHECK (owner_phone ~ '^\+923[0-9]{9}$'),
  CONSTRAINT segment_check CHECK (segment IN ('textile', 'pharma', 'retail', 'other'))
);

CREATE INDEX ix_smes_owner_phone ON smes (owner_phone);
```

**RLS:** none — this is the tenant root, not tenant-scoped.

### 1.2 `sessions` — BetterAuth sessions

BetterAuth may auto-generate parts of this; documenting the shape we need.

```sql
CREATE TABLE sessions (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  cookie_hash       varchar(64) NOT NULL UNIQUE,     -- SHA-256 of session cookie
  expires_at        timestamptz NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  last_used_at      timestamptz NOT NULL DEFAULT now(),
  user_agent        text,
  ip_address        inet,

  CONSTRAINT expires_future CHECK (expires_at > created_at)
);

CREATE INDEX ix_sessions_cookie_hash ON sessions (cookie_hash);
CREATE INDEX ix_sessions_sme_id ON sessions (sme_id);
CREATE INDEX ix_sessions_expires ON sessions (expires_at);
-- not "WHERE expires_at > now()" — Postgres requires partial-index predicates to be
-- IMMUTABLE, and now() isn't (a partial index can't track a rolling "now" anyway).
-- Callers still filter expires_at > now() at query time; a plain btree serves that fine.
```

**RLS:** off. Session lookup happens before we know the SME.

### 1.3 `otp_challenges` — OTP for phone login

```sql
CREATE TABLE otp_challenges (
  id                uuid PRIMARY KEY,
  phone             varchar(20) NOT NULL,
  otp_hash          varchar(64) NOT NULL,          -- SHA-256 of 6-digit code
  expires_at        timestamptz NOT NULL,
  attempts          smallint    NOT NULL DEFAULT 0,
  consumed_at       timestamptz,                   -- null until successful verify
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT phone_e164 CHECK (phone ~ '^\+923[0-9]{9}$'),
  CONSTRAINT attempts_ceiling CHECK (attempts <= 10)
);

CREATE INDEX ix_otp_phone_active ON otp_challenges (phone)
  WHERE consumed_at IS NULL;
-- "AND expires_at > now()" dropped — same IMMUTABLE issue as ix_sessions_expires above.
```

**RLS:** off — pre-session.

**Retention:** rows deleted 24h after `expires_at` via a scheduled job (not in MVP — manual cleanup).

### 1.4 `agents`

```sql
CREATE TABLE agents (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  name              varchar(60) NOT NULL,          -- "Stock Agent"
  name_urdu         varchar(60) NOT NULL,          -- "Stock Agent" (transliterated)
  status            varchar(20) NOT NULL DEFAULT 'live',
  tool_bindings     jsonb       NOT NULL,          -- ["read_excel_stock", "check_delivery_slot", ...]
  system_prompt_key varchar(40) NOT NULL,          -- key into agent_prompts.md registry, e.g. "stock_agent_v1"
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT status_check CHECK (status IN ('live', 'paused'))
);

CREATE INDEX ix_agents_sme_id ON agents (sme_id);
```

**RLS:** enabled — filters on `sme_id`.

**MVP seed:** one row per pilot SME with `name='Stock Agent'`, `tool_bindings=['read_excel_stock', 'check_delivery_slot', 'lookup_buyer_history', 'record_order_intent', 'get_current_date']`.

### 1.5 `buyers`

```sql
CREATE TABLE buyers (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  name              varchar(120) NOT NULL,
  phone             varchar(20),                    -- E.164 if known; MVP widget uses wa_id (browser session)
  wa_id             varchar(80)  NOT NULL,          -- widget session UUID OR future WA phone
  first_seen_at     timestamptz  NOT NULL DEFAULT now(),
  last_seen_at      timestamptz  NOT NULL DEFAULT now(),
  created_at        timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT phone_e164_if_present CHECK (phone IS NULL OR phone ~ '^\+923[0-9]{9}$')
);

CREATE UNIQUE INDEX ux_buyers_sme_wa_id ON buyers (sme_id, wa_id);
CREATE INDEX ix_buyers_sme_last_seen ON buyers (sme_id, last_seen_at DESC);
```

**RLS:** enabled.

### 1.6 `conversations`

```sql
CREATE TABLE conversations (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  agent_id          uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  buyer_id          uuid NOT NULL REFERENCES buyers(id) ON DELETE RESTRICT,
  channel           varchar(20) NOT NULL DEFAULT 'widget',   -- day-one column; zero migration on WA swap
  last_message_at   timestamptz NOT NULL DEFAULT now(),
  is_unread         boolean     NOT NULL DEFAULT false,
  is_flagged        boolean     NOT NULL DEFAULT false,
  flag_reason       varchar(500),
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT channel_check CHECK (channel IN ('widget', 'whatsapp'))
);

CREATE UNIQUE INDEX ux_convo_sme_buyer_agent ON conversations (sme_id, buyer_id, agent_id);
CREATE INDEX ix_convo_sme_last_message ON conversations (sme_id, last_message_at DESC);
CREATE INDEX ix_convo_sme_unread ON conversations (sme_id) WHERE is_unread = true;
CREATE INDEX ix_convo_sme_flagged ON conversations (sme_id) WHERE is_flagged = true;
CREATE INDEX ix_convo_sme_channel ON conversations (sme_id, channel);
```

**RLS:** enabled.

**One-buyer-one-agent rule (MVP):** unique constraint enforces one conversation per (SME, buyer, agent) triple. Multi-agent buyers get one conversation per agent.

### 1.7 `messages`

The largest table by row count. Design for read-heavy access.

```sql
CREATE TABLE messages (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender            varchar(10) NOT NULL,
  text              text        NOT NULL,
  text_original     text,                            -- buyer's raw Roman Urdu, if we ever normalize
  timestamp_ts      timestamptz NOT NULL DEFAULT now(),
  is_pending        boolean     NOT NULL DEFAULT false,   -- true if buyer msg, agent not yet replied
  audit_entry_id    uuid,                            -- set for sender='agent' iff audit written
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT sender_check CHECK (sender IN ('buyer', 'agent')),
  CONSTRAINT text_length CHECK (char_length(text) BETWEEN 1 AND 4096),
  CONSTRAINT pending_only_for_buyer CHECK (
    NOT (is_pending = true AND sender = 'agent')
  ),
  CONSTRAINT audit_only_for_agent CHECK (
    NOT (audit_entry_id IS NOT NULL AND sender = 'buyer')
  )
);

CREATE INDEX ix_msg_convo_ts ON messages (conversation_id, timestamp_ts ASC);
CREATE INDEX ix_msg_sme_ts ON messages (sme_id, timestamp_ts DESC);
CREATE INDEX ix_msg_sme_id_id ON messages (sme_id, id);     -- for widget outbound "after" pagination
```

**RLS:** enabled.

**Note on `id` vs `timestamp_ts`:** UUIDv7 embeds a timestamp, so `id > X` is time-sortable. `timestamp_ts` is kept separately for display and for the case where a delayed insert has a `created_at` different from the buyer's message wall-clock time.

### 1.8 `audit_entries`

Load-bearing. Every agent reply has exactly one row here.

```sql
CREATE TABLE audit_entries (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  message_id        uuid NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
  buyer_message_id  uuid NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
  parsed_intent     text        NOT NULL,
  tool_calls        jsonb       NOT NULL,          -- array of {name, inputs, outputs, latency_ms}
  agent_reply_text  text        NOT NULL,
  model             varchar(80) NOT NULL,          -- 'llama-3.3-70b-instruct'
  total_latency_ms  integer     NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT tool_calls_is_array CHECK (jsonb_typeof(tool_calls) = 'array')
);

CREATE INDEX ix_audit_sme ON audit_entries (sme_id, created_at DESC);
CREATE INDEX ix_audit_message_id ON audit_entries (message_id);
```

**RLS:** enabled.

**Synchronous write:** insertion happens in the same transaction as the `messages` row for the agent reply. If audit insert fails, the reply insert rolls back. Enforced via a repository method that wraps both:

```python
async def write_agent_reply_with_audit(self, reply: Message, audit: AuditEntry) -> None:
    async with self.db.begin():   # single transaction
        await self.db.execute(insert(messages).values(**reply.dict()))
        await self.db.execute(insert(audit_entries).values(**audit.dict()))
        await self.db.execute(update(messages)
            .where(messages.c.id == reply.id)
            .values(audit_entry_id=audit.id))
```

### 1.9 `excel_snapshots`

Ingested Excel state per SME. Read by `read_excel_stock`.

```sql
CREATE TABLE excel_snapshots (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  snapshot_hash     varchar(64) NOT NULL,          -- SHA-256 of source XLSX bytes
  ingested_at       timestamptz NOT NULL DEFAULT now(),
  is_active         boolean     NOT NULL DEFAULT true,
  source_filename   varchar(200),
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_excel_active_per_sme ON excel_snapshots (sme_id)
  WHERE is_active = true;   -- exactly one active snapshot per SME
CREATE INDEX ix_excel_sme_id ON excel_snapshots (sme_id, ingested_at DESC);
```

**Related:** `excel_stock_items` — the actual rows.

### 1.10 `excel_stock_items`

Denormalized rows from the Excel snapshot. This is what `read_excel_stock` queries.

```sql
CREATE TABLE excel_stock_items (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  snapshot_id       uuid NOT NULL REFERENCES excel_snapshots(id) ON DELETE CASCADE,
  sku_canonical     varchar(80)    NOT NULL,
  sku_aliases       text[]         NOT NULL DEFAULT '{}',   -- for fuzzy match
  stock             integer        NOT NULL,
  unit              varchar(20)    NOT NULL DEFAULT 'pieces',
  price_per_unit    numeric(12,2)  NOT NULL,
  price_currency    varchar(3)     NOT NULL DEFAULT 'PKR',
  reorder_threshold integer        NOT NULL DEFAULT 0,
  created_at        timestamptz    NOT NULL DEFAULT now(),

  CONSTRAINT stock_nonneg CHECK (stock >= 0),
  CONSTRAINT price_nonneg CHECK (price_per_unit >= 0),
  CONSTRAINT unit_check CHECK (unit IN ('pieces', 'meters', 'kg', 'liters', 'boxes'))
);

CREATE INDEX ix_stock_sme_sku ON excel_stock_items (sme_id, sku_canonical);
CREATE INDEX ix_stock_sme_snapshot ON excel_stock_items (sme_id, snapshot_id);
-- for fuzzy substring match at query time:
CREATE INDEX ix_stock_sku_gin ON excel_stock_items USING gin (sku_canonical gin_trgm_ops);
```

**Requires:** `CREATE EXTENSION IF NOT EXISTS pg_trgm;` — for trigram fuzzy match.

### 1.11 `order_intents`

Written by `record_order_intent` tool.

```sql
CREATE TABLE order_intents (
  id                uuid PRIMARY KEY,
  sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
  buyer_id          uuid NOT NULL REFERENCES buyers(id) ON DELETE RESTRICT,
  conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  message_id        uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  idempotency_key   varchar(80) NOT NULL,
  sku_canonical     varchar(80) NOT NULL,
  quantity          integer     NOT NULL,
  agreed_price_per_unit numeric(12,2) NOT NULL,
  total_amount      numeric(14,2) NOT NULL,           -- GENERATED ALWAYS AS (quantity * agreed_price_per_unit) STORED
  delivery_date     date        NOT NULL,
  notes             varchar(500),
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT qty_positive CHECK (quantity > 0),
  CONSTRAINT price_positive CHECK (agreed_price_per_unit > 0)
);

CREATE UNIQUE INDEX ux_order_intents_idem ON order_intents (sme_id, idempotency_key);
CREATE INDEX ix_order_intents_sme_created ON order_intents (sme_id, created_at DESC);
CREATE INDEX ix_order_intents_buyer ON order_intents (sme_id, buyer_id);
```

### 1.12 `qdrant_collection_registry`

Metadata — maps `sme_id` to the Qdrant collection name and dimensionality.

```sql
CREATE TABLE qdrant_collection_registry (
  sme_id            uuid PRIMARY KEY REFERENCES smes(id) ON DELETE CASCADE,
  collection_name   varchar(120) NOT NULL UNIQUE,      -- 'sme_{sme_id}_memory'
  embedding_model   varchar(80)  NOT NULL,             -- 'embed-multilingual-v3.0'
  dimension         integer      NOT NULL,             -- 1024 (Cohere multilingual)
  created_at        timestamptz  NOT NULL DEFAULT now()
);
```

Vector data lives in Qdrant; this table tracks configuration so a migration to `pgvector` (ADR-005 reversal path) or a different embedding provider is straightforward — collection name never changes, but new SMEs onboarded after a provider swap register under the new dimension.

---

## 2. Not-in-MVP tables (documented for Phase 1+)

Documented here so Claude Code does not "helpfully" create them:

| Table | When |
|---|---|
| `payments` | Phase 1 — Easypaisa/JazzCash reconciliation. Manual toggle for MVP; no table. |
| `tax_deadlines` | Phase 1 — Tax Reminder Agent's data source. |
| `sme_plans` | Phase 2 — pricing/billing. |
| `invoices` | Phase 2. |
| `webhook_events` | Phase 2 — Meta webhook deliveries. |
| `admin_audit_log` | Phase 2. |
| `custom_agents` | Phase 3 — user-defined agents. |

---

## 3. Full initial migration — `0001_initial_schema.py`

The migration executes in this order (foreign keys constrain it):

1. `CREATE EXTENSION pg_trgm;`
2. `smes`
3. `sessions`, `otp_challenges`
4. `agents`, `buyers`, `excel_snapshots`
5. `excel_stock_items`, `qdrant_collection_registry`
6. `conversations`
7. `messages`
8. `audit_entries`, `order_intents`
9. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` on all SME-scoped tables
10. Create RLS policies
11. Create `app_role` (limited role the FastAPI app connects as)

---

## 4. Seed data (referenced from `seed_data.md`)

Minimum for local dev:

| Table | Rows |
|---|---|
| `smes` | 1 (Aslam Textiles, +923005551234) |
| `agents` | 1 (Stock Agent, tool_bindings all 5) |
| `excel_snapshots` | 1 active |
| `excel_stock_items` | ~15 SKUs (denim-classic, denim-stretch, cotton-white, poly-blend, ...) |
| `buyers` | 3 (Ali Traders, Saleem Fabrics, Khan Garments — one with history for `lookup_buyer_history`) |
| `conversations` | 3 (one unread, one flagged, one plain) |
| `messages` | ~20 across the conversations, mix of buyer + agent |
| `audit_entries` | ~5 for the agent messages, each with 1-3 tool_calls populated |
| `order_intents` | 2 (from the returning-buyer conversations) |

Seed script: `apps/backend/seeds/pilot_sme.py`. Idempotent — runs once, subsequent runs are no-ops.

---

## 5. Data volume forecast (MVP + pilot)

Rough capacity planning for Neon free tier (0.5 GB storage, 100 hours compute):

| Table | Rows at end of pilot (5 SMEs × 30 days) | Bytes/row (est) | Total |
|---|---|---|---|
| `smes` | 5 | 300 | 1.5 KB |
| `agents` | 5 | 500 | 2.5 KB |
| `buyers` | 500 | 200 | 100 KB |
| `conversations` | 500 | 300 | 150 KB |
| `messages` | ~15,000 (10 msgs/convo/day × 30) | 800 | 12 MB |
| `audit_entries` | ~7,500 (half of messages, agent only) | 4000 | 30 MB |
| `excel_stock_items` | ~500 (20 SKUs × 5 SMEs, 5 snapshots each) | 400 | 200 KB |
| `order_intents` | ~1,000 | 500 | 500 KB |

**Total:** ~45 MB. Neon free tier fits.

**Phase 2 forecast:** at 25 paying SMEs × 90 days × 20 messages/day, we hit ~200 MB. Still fits free tier; paid tier upgrade is triggered by cold-start latency (ADR-006), not capacity.

---

## 6. Backup + recovery (MVP)

- Neon has automatic point-in-time recovery on the free tier (7-day window).
- **No custom backup logic in MVP.** If Neon has a data loss event, we lose pilot data. Acceptable at pilot scale; not acceptable at Phase 2 (see Roadmap Phase 3 deferred items).
- Migrations must be reversible via `alembic downgrade -1` for the last migration. Older reversals are best-effort.

---

## 7. Handoff checklist

Before Claude Code writes any table or migration:

- [ ] `alembic init migrations/` has been run.
- [ ] `alembic.ini` has `sqlalchemy.url = env://DATABASE_URL`.
- [ ] `pyproject.toml` includes: `sqlalchemy>=2`, `asyncpg`, `alembic`, `pgvector` (for Phase 3 readiness — not used in MVP).
- [ ] `.env.example` has `DATABASE_URL` matching Neon connection string format.
- [ ] `apps/backend/src/repositories/base.py` implements `BaseRepository` with `scoped()`.

---

## Change log

| Date | Change |
|---|---|
| 2026-07-23 | Initial draft. 12 tables covering MVP + explicit non-MVP list. |
| 2026-07-23 | Add `conversations.channel` column (day-one, no migration on WA swap). Update Qdrant registry example to Cohere `embed-multilingual-v3.0` (1024-dim). |
| 2026-07-24 | Fix `ix_sessions_expires` and `ix_otp_phone_active`: dropped `expires_at > now()` from both partial-index predicates — Postgres requires `IMMUTABLE` predicates and `now()` isn't, so both indexes failed to create as originally written. Found while containerizing P0 and running the migration against a real Postgres for the first time. |
