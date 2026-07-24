---
project: Sindh Agents
type: api-contract
status: draft (awaiting Arham backend sign-off)
owner: Arham (backend) / consumed by Ayesha (frontend) + Claude Code (implementation)
created: 2026-07-23
scope: Hackathon MVP
pairs_with: dashboard_spec.md
---

# Sindh Agents — API Contract (MVP)

> **Purpose:** Every route the MVP frontend and widget can call. Response shapes match `dashboard_spec.md` verbatim. This is the sole source of truth for the FE/BE boundary — if a route isn't here, it doesn't exist; if a field isn't here, don't send it.

> **Not in scope:** Multi-tenant admin endpoints, billing, agent CRUD, WhatsApp webhook (real Meta payload comes in Phase 2 — MVP widget uses this same shape via `/api/widget/inbound`).

---

## 0. Rules that apply to every route

Read these once. They are not repeated per route.

### 0.1 Base URL

- Dev: `http://localhost:3000/api`
- Staging: `https://staging.sindhagents.com/api`
- Prod (pilot): `https://app.sindhagents.com/api`

### 0.2 Auth model

- **Session cookie via BetterAuth.** Cookie name: `sa_session`. `HttpOnly`, `Secure` (staging/prod), `SameSite=Lax`.
- **Dashboard routes:** require a valid session cookie. No JWT, no bearer tokens in MVP.
- **Widget routes** (`/api/widget/*`): unauthenticated. Rate-limited by IP + `wa_id`.
- **Auth routes** (`/api/auth/*`): unauthenticated by definition.
- Missing/invalid session on a protected route → `401` with error code `AUTH_REQUIRED`. Frontend redirects to `/login`.

### 0.3 Server-side SME scoping (non-negotiable)

**Every dashboard route resolves the SME from the session, not from the request.** No `?sme_id=`, no `X-SME-ID` header, no body field. If the frontend ever tries to pass an SME ID, the backend must return `400 BAD_REQUEST` — this is a defensive assertion, not silent-ignore.

Implementation contract: the session cookie resolves to `{ userId, smeId }`. All queries are scoped by `smeId` at the repository layer (base class in Architecture §Security Boundaries). A single cross-tenant leak = Phase 1 gate failure.

### 0.4 Content type

- All requests and responses: `application/json; charset=utf-8`.
- Widget inbound (Phase 2 will accept `multipart/form-data` for media; MVP: text only, JSON only).

### 0.5 Standard error envelope

Every non-2xx response uses this shape. No exceptions.

```typescript
type ErrorResponse = {
  ok: false;
  error: {
    code: string;              // stable machine-readable code
    message: string;           // human-readable English (for logs)
    messageUrdu?: string;      // Roman Urdu (for FE display when appropriate)
    field?: string;            // for 400 validation errors, name of the offending field
    requestId: string;         // for support debugging
  };
};
```

Success responses always have `ok: true` at the top level (except widget outbound long-poll which returns a bare `{ messages: [...] }` for compat with future Meta shape).

**Standard error codes used across routes:**

| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_REQUIRED` | 401 | No/invalid session |
| `FORBIDDEN` | 403 | Session valid but resource not owned by this SME |
| `NOT_FOUND` | 404 | Resource does not exist for this SME |
| `BAD_REQUEST` | 400 | Malformed request — see `field` |
| `RATE_LIMITED` | 429 | See `Retry-After` header |
| `SERVER_ERROR` | 500 | Unhandled — request ID for grep in logs |
| `SERVICE_UNAVAILABLE` | 503 | Downstream (LLM, Qdrant, Neon) failing — see §0.10 |

### 0.6 Rate limits

Applied per source. Headers on every response:

- `X-RateLimit-Limit` — window ceiling
- `X-RateLimit-Remaining` — remaining this window
- `X-RateLimit-Reset` — Unix epoch seconds when window resets

| Route pattern | Key | Limit |
|---|---|---|
| `POST /api/auth/send-otp` | `phone` | 3 per hour |
| `POST /api/auth/verify-otp` | `phone` | 6 per hour (5 attempts + 1 buffer) |
| Dashboard reads | session | 120 per minute |
| `POST /api/widget/inbound` | `wa_id` + IP | 30 per minute |
| `GET /api/widget/outbound` | `wa_id` | 60 per minute (polling) |

Over-limit → `429` with `Retry-After` header (seconds).

### 0.7 Timestamps

- **Wire format:** ISO 8601 with timezone, e.g., `"2026-07-23T10:12:34.567+05:00"`.
- **Widget inbound `timestamp` field:** exception — Unix epoch seconds as a string, to match Meta's exact webhook shape.
- **Timezone:** all display times computed against `Asia/Karachi`. Backend stores UTC.

### 0.8 IDs

All IDs are opaque strings. Frontend must not parse them. Format for MVP: UUIDv7 (time-sortable), 36 chars including dashes. Not exposed as such — treat as opaque.

Branded types in the FE (`SmeId`, `AgentId`, `ConversationId`, `MessageId`) map to the same underlying string shape. Backend does not distinguish — the branding is a FE type-safety measure only.

### 0.9 Pagination

MVP has one paginated endpoint (`GET /api/conversations`). Convention:

- Query params: `limit` (default 50, max 200), `cursor` (opaque, from previous response's `nextCursor`).
- Response includes `nextCursor: string | null`. Null = end of list.
- No offset-based pagination anywhere.

### 0.10 Downstream degradation

When Groq / Qdrant / Neon are degraded, dashboard routes return `503 SERVICE_UNAVAILABLE` with an Urdu-friendly message. Widget inbound queues the message (does not 503) and the agent replies late — messages are never dropped. Widget outbound returns whatever is available, even if empty.

### 0.11 CORS

- Dashboard API: same-origin only (Next.js server routes — CORS not applicable).
- Widget API: CORS enabled for `https://demo.sindhagents.com` (widget host) and `*` in dev. Preflight allowed methods: `POST, GET, OPTIONS`.

### 0.12 Idempotency

- `POST /api/widget/inbound` accepts an `Idempotency-Key` header. If present and previously seen within 24h, backend returns the original response without re-processing. Prevents double-sends from flaky mobile networks.
- `POST /api/auth/send-otp` is idempotent by phone within its rate-limit window (returns cached OTP nonce, does not resend).
- `POST /api/auth/verify-otp` is not idempotent (each attempt burns a slot).

### 0.13 Request ID

Every request generates a UUID request ID, returned in `X-Request-ID` header and echoed in error `requestId`. Used for log grep. FE should surface it in error toasts only in staging/dev.

---

## 1. Auth

### 1.1 `POST /api/auth/send-otp`

Send a 6-digit OTP to the given phone number via SMS.

**Auth:** none.

**Request body:**
```typescript
type SendOtpRequest = {
  phone: string;   // E.164 format, +923XXXXXXXXX. Validated with regex ^\+923[0-9]{9}$
};
```

**Success (200):**
```typescript
type SendOtpResponse = {
  ok: true;
  data: {
    expiresInSeconds: number;   // typically 300 (5 min)
    resendAvailableInSeconds: number;  // typically 60
  };
};
```

**Errors:**
- `400 BAD_REQUEST` field=`phone` — malformed phone number.
- `429 RATE_LIMITED` — too many sends for this phone.
- `503 SERVICE_UNAVAILABLE` — SMS provider (Twilio) down.

**Backend behavior:**
- Generates 6-digit OTP, stores hashed with 5-min TTL in Neon.
- Sends via Twilio (dev: logs to stdout with a `DEV_OTP:` prefix — Baneen/Ayesha find it in the FastAPI log for local testing).
- Same phone within 60s → returns the same expiry, does not resend.

**Not shipped in MVP:** WhatsApp OTP delivery (Meta), voice OTP fallback.

---

### 1.2 `POST /api/auth/verify-otp`

Verify OTP and issue session cookie.

**Auth:** none.

**Request body:**
```typescript
type VerifyOtpRequest = {
  phone: string;   // must match the phone from send-otp
  otp: string;     // 6 digits, string form to preserve leading zeros
};
```

**Success (200):** sets `Set-Cookie: sa_session=...` header.
```typescript
type VerifyOtpResponse = {
  ok: true;
  data: {
    smeId: string;         // opaque
    smeName: string;       // "Aslam Textiles"
    ownerName: string;     // "Aslam"
  };
};
```

**Errors:**
- `400 BAD_REQUEST` field=`otp` — OTP shape wrong (not 6 digits).
- `401 AUTH_REQUIRED` code=`OTP_INVALID` — wrong OTP.
- `401 AUTH_REQUIRED` code=`OTP_EXPIRED` — OTP past its TTL.
- `429 RATE_LIMITED` — too many attempts on this phone.
- `404 NOT_FOUND` code=`SME_NOT_ENROLLED` — phone is not registered to any pilot SME. In MVP, we do not self-serve signup — only pre-enrolled pilot SMEs can log in.

**Backend behavior:**
- Successful verification: creates BetterAuth session, sets cookie, invalidates the OTP.
- 5 failed attempts within window → phone locked for 15 min (returns `RATE_LIMITED`).

---

### 1.3 `POST /api/auth/logout`

Invalidate the current session.

**Auth:** session cookie required.

**Request body:** none.

**Success (200):**
```typescript
type LogoutResponse = { ok: true };
```

Clears the `sa_session` cookie via `Set-Cookie` with expired date.

---

### 1.4 `GET /api/auth/me`

Return the current session's SME + owner info. Used by dashboard on every page load (via server component, not client fetch) to render the header greeting.

**Auth:** session cookie required.

**Success (200):**
```typescript
type MeResponse = {
  ok: true;
  data: {
    smeId: string;
    smeName: string;
    ownerName: string;
    phone: string;    // masked, e.g., "+92 3XX ****172"
  };
};
```

**Errors:** `401 AUTH_REQUIRED` if no session.

---

## 2. Dashboard reads

### 2.1 `GET /api/agents`

Powers the home screen. Returns all agents for the session's SME + a recent conversations preview (last 5).

**Auth:** session required.

**Query params:** none.

**Success (200):**
```typescript
type AgentsResponse = {
  ok: true;
  data: {
    smeName: string;
    ownerName: string;
    agents: Array<{
      id: string;
      name: string;              // English canonical
      nameUrdu: string;          // Roman Urdu display name
      status: 'live' | 'paused';
      messagesToday: number;     // count of buyer messages routed to this agent since 00:00 Asia/Karachi
      lastActive: string;        // ISO 8601 or null if never
    }>;
    recentConversations: Array<{
      id: string;
      buyerName: string;
      lastMessagePreview: string;   // first 60 chars, no truncation inside a number
      lastMessageAt: string;
      unread: boolean;
    }>;
  };
};
```

**Errors:** `401`, `503`.

**Backend notes:**
- `messagesToday` is a fresh count each call — no caching. Pilot scale (≤100 msgs/day/SME) doesn't warrant a counter table.
- `lastMessagePreview`: server truncates at 60 chars using a **word-safe** cut (trim to last space). If truncated, append `"…"` (single ellipsis char, not three dots). If truncation would land mid-number (e.g., `"Rs. 12,3…"`), the truncation shifts left to the previous word boundary. This is the deterministic-narrator rule extending into previews.

---

### 2.2 `GET /api/conversations`

Full paginated list of conversations for the SME.

**Auth:** session required.

**Query params:**
| Name | Type | Default | Notes |
|---|---|---|---|
| `tab` | `'all' \| 'unread' \| 'flagged'` | `'all'` | |
| `q` | string | — | Search term. Matches `buyerName` (case-insensitive substring) OR normalized `buyerPhone` (digits only). Min 2 chars, else ignored. |
| `limit` | number | 50 | Max 200. |
| `cursor` | string | — | From previous response's `nextCursor`. |

**Success (200):**
```typescript
type ConversationsResponse = {
  ok: true;
  data: {
    conversations: Array<{
      id: string;
      buyerName: string;
      buyerPhone: string;         // masked: "+92 3XX ****172"
      lastMessagePreview: string;
      lastMessageAt: string;
      unread: boolean;
      flagged: boolean;
      agentName: string;          // Roman Urdu — which agent handled it
    }>;
    total: number;                 // total matching current filter (not cursor page size)
    nextCursor: string | null;
  };
};
```

**Errors:** `401`, `400 BAD_REQUEST` (bad cursor, bad tab value, limit > 200).

**Backend notes:**
- Sort: `lastMessageAt DESC`. Cursor encodes `(lastMessageAt, id)` for stable pagination under insertions.
- `buyerPhone` is always masked at the API layer. Raw phone never leaves the DB.
- `total` is exact for MVP pilot scale (≤5 SMEs, ≤1000 convos/SME). No approximation.

---

### 2.3 `GET /api/conversations/[id]`

Full conversation with all messages.

**Auth:** session required.

**Path params:** `id` — conversation ID.

**Query params:**
| Name | Type | Default | Notes |
|---|---|---|---|
| `before` | ISO timestamp | — | If set, return only messages with `timestamp < before`. For "load older" scroll — not shipped in MVP UI, reserved. |
| `limit` | number | 200 | Max 500. |

**Success (200):**
```typescript
type ConversationDetailResponse = {
  ok: true;
  data: {
    id: string;
    buyer: {
      name: string;
      phone: string;              // masked
      firstSeenAt: string;
    };
    agent: {
      id: string;
      nameUrdu: string;
    };
    messages: Array<{
      id: string;
      sender: 'buyer' | 'agent';
      text: string;               // rendered verbatim by FE — no client transforms
      textOriginal?: string;      // buyer's raw Roman Urdu, if the FE ever wants to display "original vs. normalized"
      timestamp: string;
      auditMessageId?: string;    // present iff sender='agent'
    }>;
  };
};
```

**Errors:**
- `401 AUTH_REQUIRED`
- `404 NOT_FOUND` — conversation ID does not exist for this SME (indistinguishable from "belongs to another SME" — deliberate: no info leak on tenant boundary)
- `400 BAD_REQUEST` — bad `before` or `limit`

**Backend notes:**
- Sort: `timestamp ASC`. Message-list order matches display order.
- `text` is exactly what the narrator emitted. No re-formatting, no i18n. This is Architecture Principle 1 enforced at the API layer.
- Mark conversation as read on this GET (200-only): set `conversations.unread = false` for this SME. This is a side-effect on read — noted here so it's not a surprise. If FE needs a read-only fetch, add `?peek=true` in a future ADR.

---

### 2.4 `GET /api/audit/[messageId]`

Full audit trace for a single agent reply. Trust wedge.

**Auth:** session required.

**Path params:** `messageId` — the agent message's ID (same as `auditMessageId` on the conversation detail).

**Success (200):**
```typescript
type AuditResponse = {
  ok: true;
  data: {
    messageId: string;
    buyerMessage: {
      text: string;
      timestamp: string;
    };
    parsedIntent: string;         // one-line Roman Urdu summary
    toolCalls: Array<{
      name: string;               // e.g., 'read_excel_stock'
      inputs: Record<string, unknown>;
      outputs: unknown;
      latencyMs: number;
    }>;
    agentReply: {
      text: string;
      timestamp: string;
    };
    model: string;                // e.g., 'llama-3.3-70b-instruct'
    totalLatencyMs: number;
  };
};
```

**Errors:**
- `401 AUTH_REQUIRED`
- `404 NOT_FOUND` — message ID does not exist, belongs to another SME, or belongs to a buyer message (audit only exists for agent replies)
- `410 GONE` code=`AUDIT_EXPIRED` — audit records are retained for 90 days in MVP; older entries return 410. Not expected during hackathon or Phase 1.

**Backend notes:**
- Audit rows are written **synchronously with the agent reply** — never asynchronously. If audit write fails, the reply fails. Non-negotiable per Architecture §Data Layer audit-ledger design.
- `inputs` and `outputs` are JSON-serialized as-stored — no redaction, no transformation. If a tool call output includes numeric strings ("450"), they stay as strings.
- `toolCalls` order is the invocation order (as executed). Not sorted alphabetically.

---

### 2.5 `POST /api/conversations/[id]/flag`

Toggle flag on a conversation. Used from the conversation-list three-dot menu and from the audit drawer flag button.

**Auth:** session required.

**Path params:** `id` — conversation ID.

**Request body:**
```typescript
type FlagRequest = {
  flagged: boolean;
  reason?: string;                // optional, ≤500 chars. Free-form. Reserved for Phase 2 review-queue triage.
};
```

**Success (200):**
```typescript
type FlagResponse = {
  ok: true;
  data: {
    id: string;
    flagged: boolean;
  };
};
```

**Errors:** `401`, `404`, `400`.

---

### 2.6 `POST /api/excel/reingest`

SME uploads a replacement stock sheet from the `/inventory` dashboard page. Full design in `phase/P6.md`.

**Auth:** session required.

**Request:** `multipart/form-data`, field name `file`, `.xlsx` only.

**Success (200):**
```typescript
type ReingestResponse = {
  ok: true;
  data: {
    snapshotId: string;
    itemCount: number;
    ingestedAt: string;
    isNoop: boolean;          // true if the uploaded file's hash matched the active snapshot — nothing changed
  };
};
```

**Errors:**
- `400 BAD_REQUEST` — missing required column, bad unit value, negative stock/price, non-integer stock, empty file, non-`.xlsx` file. `message` names the specific row/column problem (e.g. "Row 4: Stock must be a whole number") and is rendered verbatim in the upload UI — not replaced with a canned string.
- `401 UNAUTHENTICATED` — no/invalid session.
- `413 PAYLOAD_TOO_LARGE` — file exceeds the 2MB cap.

**Backend behavior:**
- SHA-256 of the raw file bytes is checked against the current active snapshot's `snapshot_hash`; an identical re-upload is a no-op.
- Otherwise: deactivate the current active snapshot, insert the new one as active, bulk-insert its rows — all in one DB transaction (`ExcelStockRepository.replace_snapshot`).
- A bad row rejects the whole file; nothing is partially written. Row cap: 500.
- `read_excel_stock` / `ExcelStockRepository.list_for_sme` are unchanged — they already read the active snapshot, so newly ingested rows apply with zero changes on that side.

---

## 3. Widget (buyer-facing, unauthenticated)

The widget contract is deliberately shaped like Meta's WhatsApp Cloud API webhook payload. Phase 2 flips the `messaging_product` field and points the same handler at Meta's webhook URL — no other changes.

### 3.1 `POST /api/widget/inbound`

Buyer sends a message. Backend accepts it, routes to the agent, and eventually the agent's reply appears on the outbound endpoint.

**Auth:** none. Rate-limited by `wa_id` + IP.

**Headers:**
- `Idempotency-Key: <uuid>` — optional but recommended. Prevents double-send on flaky networks. See §0.12.

**Request body (matches Meta webhook `entry.changes.value` shape):**
```typescript
type WidgetInboundRequest = {
  messaging_product: 'widget';       // Phase 2: 'whatsapp'. Backend switch on this field.
  metadata: {
    display_phone_number: string;    // agent's assigned phone. MVP: fixed dev value.
    phone_number_id: string;         // MVP: fixed dev value.
  };
  contacts: [{
    profile: { name: string };        // buyer name, prompted in widget on first open
    wa_id: string;                    // browser session ID in MVP (UUID). Phase 2: buyer's phone.
  }];
  messages: [{
    from: string;                     // must equal wa_id above
    id: string;                       // client-generated UUID; used for Idempotency-Key correlation
    timestamp: string;                // Unix epoch seconds, as string (Meta compat)
    text: { body: string };           // 1..4096 chars
    type: 'text';                     // MVP: text only
  }];
};
```

**Validation:**
- Array length exactly 1 for `contacts` and `messages` in MVP. Meta sometimes batches; MVP does not — reject `> 1` with `400 BAD_REQUEST field='messages'`.
- `messages[0].from === contacts[0].wa_id`.
- `text.body` non-empty after trim, ≤ 4096 chars.
- `messaging_product` MVP: must be `'widget'` (default). When `FEATURE_WHATSAPP=true`, also accepts `'whatsapp'` — same handler, dispatch by field value into the correct outbound channel (widget long-poll vs. Twilio WA send).

**Dispatch rule:** the route handler is channel-agnostic. It reads `messaging_product`, resolves the `conversations.channel` value on insert/update, and enqueues to the corresponding `OutboundChannel` implementation. When Twilio WA sandbox is enabled, point Twilio's inbound webhook URL at this same endpoint — no separate route.

**Success (200):**
```typescript
type WidgetInboundResponse = {
  ok: true;
  data: {
    accepted: true;
    messageId: string;               // server-assigned canonical ID (may differ from client's messages[0].id)
  };
};
```

**Errors:**
- `400 BAD_REQUEST` — shape validation failed. `field` names the offending path (e.g., `messages[0].text.body`).
- `429 RATE_LIMITED` — burst limit hit.
- Never `401` — widget is unauthenticated by design.
- Never `503` — buyer messages must not be lost. If downstream is degraded, queue in Neon and return `202 Accepted`? **No** — MVP: always return `200` and mark the message `pending` in the DB. The agent will reply late once downstream recovers. Buyer sees no error; SME sees the message in the dashboard.

**Backend behavior:**
- Insert message into `messages` table (`sender='buyer'`, associated with a `conversations` row keyed by `(sme_id, wa_id)`).
- If `Idempotency-Key` matches an entry ≤24h old, return the cached response — do not re-insert.
- Enqueue agent processing (Groq call + tool execution + narrator + audit write). Result appears on outbound endpoint.
- Backend must resolve which SME this widget belongs to. MVP: single pilot SME per widget instance, identified by the widget's compile-time `metadata.phone_number_id` mapping. Phase 2: Meta's phone_number_id maps to SME via a config table.

---

### 3.2 `GET /api/widget/outbound`

Buyer polls for new agent replies. Long-poll (up to 25s) to reduce request volume.

**Auth:** none. Rate-limited by `wa_id`.

**Query params:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `wa_id` | string | yes | Buyer's widget session ID |
| `after` | string | no | Last message ID the buyer has seen. Server returns only messages with ID after this one. If omitted, returns last 20. |
| `wait` | number | no | Max wait in seconds. Default 25, max 25. Long-poll: if no new messages, hold connection until timeout. |

**Success (200):**

Response deliberately does **not** wrap in `{ ok, data }` — it matches the shape the widget will receive from Meta in Phase 2 (Meta sends webhook pushes; the widget polls the same shape from us).

```typescript
type WidgetOutboundResponse = {
  messages: Array<{
    id: string;
    timestamp: string;               // Unix epoch seconds, as string (Meta compat)
    text: { body: string };
    // NB: auditMessageId is NOT sent to widget. Audit visibility is dashboard-only.
  }>;
  hasMore: boolean;                  // true if there are more beyond default limit — poll again immediately
};
```

Empty response (timeout with no new messages):
```json
{ "messages": [], "hasMore": false }
```

**Errors:**
- `400 BAD_REQUEST` — missing `wa_id` or malformed `after`.
- `429 RATE_LIMITED` — polling too fast (>60/min per wa_id).
- `503 SERVICE_UNAVAILABLE` — DB unreachable. Widget should retry with exponential backoff starting at 2s.

**Backend notes:**
- Long-poll implementation: PostgreSQL LISTEN/NOTIFY on `messages_inserted_{sme_id}` channel, or dumb 500ms-interval polling for MVP. Ayesha's choice; both meet MVP latency budget.
- `after` cursor: server matches `id > after` in insertion order (UUIDv7 is time-sortable). If `after` is not a valid ID or is from a different `wa_id`, treat as omitted.

---

## 4. Data flow diagrams (reference)

### 4.1 Buyer sends a message

```
Widget --POST /api/widget/inbound--> Backend
                                        |
                                        |-- insert message row (sender='buyer', pending agent reply)
                                        |-- enqueue agent processing
                                        |-- respond 200 { messageId }
                                        v
                              Agent worker (async)
                                        |
                                        |-- Qdrant retrieve context
                                        |-- Groq call → tool plan
                                        |-- execute tools (read Excel, etc.)
                                        |-- narrator prompt
                                        |-- write audit row (SYNC with reply write)
                                        |-- insert message row (sender='agent')
                                        |-- NOTIFY messages_inserted_{sme_id}
                                        v
Widget <--GET /api/widget/outbound-- Backend (long-poll released)
```

### 4.2 SME opens a conversation and inspects a reply

```
Dashboard --GET /api/conversations/[id]--> Backend
                                              |-- verify session, resolve sme_id
                                              |-- SELECT messages WHERE conversation_id AND sme_id
                                              |-- side-effect: mark unread=false
                                              v
Dashboard renders bubbles, agent bubbles show 🔍 magnifier
                                              |
                                              v (SME taps magnifier)
Dashboard --GET /api/audit/[messageId]--> Backend
                                              |-- verify session, resolve sme_id
                                              |-- SELECT audit WHERE message_id AND sme_id
                                              v
Drawer renders tool calls, model, timing
```

---

## 5. Route index (checklist for Claude Code)

| Method | Path | Auth | Body | Response type | §  |
|---|---|---|---|---|---|
| POST | `/api/auth/send-otp` | public | `SendOtpRequest` | `SendOtpResponse` | 1.1 |
| POST | `/api/auth/verify-otp` | public | `VerifyOtpRequest` | `VerifyOtpResponse` | 1.2 |
| POST | `/api/auth/logout` | session | — | `LogoutResponse` | 1.3 |
| GET | `/api/auth/me` | session | — | `MeResponse` | 1.4 |
| GET | `/api/agents` | session | — | `AgentsResponse` | 2.1 |
| GET | `/api/conversations` | session | — | `ConversationsResponse` | 2.2 |
| GET | `/api/conversations/[id]` | session | — | `ConversationDetailResponse` | 2.3 |
| GET | `/api/audit/[messageId]` | session | — | `AuditResponse` | 2.4 |
| POST | `/api/conversations/[id]/flag` | session | `FlagRequest` | `FlagResponse` | 2.5 |
| POST | `/api/excel/reingest` | session | multipart `file` | `ReingestResponse` | 2.6 |
| POST | `/api/widget/inbound` | public | `WidgetInboundRequest` | `WidgetInboundResponse` | 3.1 |
| GET | `/api/widget/outbound` | public | — | `WidgetOutboundResponse` | 3.2 |

Total: 12 routes.

---

## 6. What is NOT in the API (deliberate)

Not scope slippage — deliberate scope calls. Each traces to an ADR or Blocker.

| Not-shipped route | Reason | Reference |
|---|---|---|
| `POST /api/agents` (create agent) | Agents seeded via backend for pilot SMEs | Dashboard spec §2 |
| `PATCH /api/agents/[id]` (pause/resume) | Not in MVP dashboard flows | Dashboard spec §2 |
| `POST /api/messages` (SME sends manual message) | Owner does not reply from dashboard — ADR-014 identity call | ADR-014 |
| `POST /api/payments/reminder` | SMS reminders are Phase 1, not MVP | ADR-010 · Blockers 2 |
| `POST /api/tax/*` | Tax knowledge base is Phase 1 | ADR-011 · Blockers 3 |
| `/api/whatsapp/webhook` (real Meta) | Widget inbound serves this purpose in MVP | ADR-009 · Blockers 1 |
| `POST /api/billing/*` | No billing in MVP — pilots are free | Roadmap Phase 1 |
| `/api/admin/*` | No admin surface in MVP | Roadmap Phase 2 |
| SSE / WebSocket outbound | Long-poll suffices at pilot scale | Ayesha's choice; can add later without breaking contract |

---

## 7. Backend contracts implied by this document

Things the backend must guarantee that aren't visible in the wire protocol:

1. **Session cookie → SME resolution is O(1)** (session table indexed on cookie hash). Every dashboard route hits this on entry.
2. **Repository base class enforces `sme_id` filter on every query.** No ORM path bypasses it. Cross-tenant leak is a Phase 1 gate failure.
3. **Audit row write is in the same DB transaction as agent-message row write.** Never eventually-consistent.
4. **Widget inbound path never drops a message.** If enqueue fails, message row is inserted with `pending=true` and a background job retries agent processing.
5. **`text` fields in agent replies are the exact narrator output.** No downstream mutation, no logging redaction that changes visible content.
6. **UUIDv7 for all IDs** — for time-sortable pagination cursors and for `after` semantics on widget outbound.

---

## 8. Handoff checklist

Before Claude Code implements FE against this contract:

- [ ] Arham signs off on this document (change log below).
- [ ] Ayesha confirms every `type XxxResponse` matches what her components consume in `dashboard_spec.md`. Any drift = update spec first.
- [ ] Backend has a mock server (FastAPI stub or Next.js API routes with hardcoded returns) that serves this contract, so FE can develop against it before real backend is done.
- [ ] Seed data script produces at least one pilot SME with 2 agents, 3 conversations, 20 messages, and 5 audit records for local dev.
- [ ] `X-Request-ID` middleware wired end-to-end.

---

## Change log

| Date | Change | Owner |
|---|---|---|
| 2026-07-23 | Initial draft. Matches all types in `dashboard_spec.md`. Awaiting Arham backend sign-off. | Arham (draft) |
| 2026-07-23 | §3.1: clarify dispatch rule — same handler serves widget (MVP) and Twilio WA (flag on). Route stays `/api/widget/inbound` even when Twilio sends to it — payload shape is the contract, not the URL. | Arham |
