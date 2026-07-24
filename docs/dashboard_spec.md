---
project: Sindh Agents
type: spec
status: draft (awaiting Ayesha sign-off)
owner: Arham (draft) / Ayesha (sign-off + evolution)
created: 2026-07-23
scope: Hackathon MVP — dashboard + chat widget
audience: Claude Code (implementation)
---

# Sindh Agents — Dashboard & Widget Spec (MVP)

> **Purpose:** Everything Claude Code needs to build the MVP frontend without guessing. This is not a design brief. Every section below either constrains implementation or defines a contract.

> **Not in scope:** Multi-tenancy, Enterprise SSO, multi-agent orchestration, WhatsApp API integration, live payments. All Phase 2+.

---

## 0. Non-negotiables (read first)

These come from ADRs and Blockers. Violating any of these breaks a downstream phase.

1. **Widget message contract must be WhatsApp-webhook-compatible** (ADR-009). Rendering the widget as a WA chat later must be a channel swap, not a rewrite.
2. **Numbers displayed to the SME must come from tool outputs verbatim.** Narrator preserves numbers. No client-side re-formatting of numeric content from agent replies (Architecture Principle 1).
3. **Audit ledger is one tap from any message.** Trust wedge. If the "why did the agent say X" flow takes more than one tap, it's a bug.
4. **Mobile-first Next.js 14 App Router + shadcn + Tailwind.** Not "responsive after the fact." Design and build starts at 360px viewport.
5. **Roman Urdu labels are first-class.** Every user-facing string has a Roman Urdu variant. Not translated at runtime — authored.
6. **Per-SME data scoping is enforced at the API layer, not the UI.** UI does not filter by SME ID — it receives already-scoped data. Do not add `?sme_id=` query params anywhere.
7. **Session auth via BetterAuth.** Owner session only in MVP. No role separation, no invited users. Phase 2.
8. **No PII in localStorage.** Session token only. Everything else is server state.

---

## 1. Tech stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js 14 App Router | ADR-007 |
| Styling | Tailwind + shadcn/ui | ADR-007 |
| Auth | BetterAuth | ADR-008 |
| Data fetching | Server Components + `fetch` with `revalidate: 0` on live views | No SWR/React Query in MVP — server components sufficient at pilot scale |
| Language | TypeScript strict mode | Non-negotiable |
| Deployment | Vercel (frontend) + Docker Compose backend | ADR-012 |

**Component library — approved shadcn additions only:**
`button`, `card`, `input`, `label`, `textarea`, `sheet`, `dialog`, `dropdown-menu`, `tabs`, `badge`, `separator`, `scroll-area`, `avatar`, `skeleton`, `toast`, `data-table` (TanStack Table wrapper), `command` (for the search palette in Phase 2 — skip in MVP).

**Forbidden without ADR:** additional UI libraries (Radix primitives outside shadcn, MUI, Chakra), CSS-in-JS, custom design tokens beyond Tailwind's default palette + one accent color.

**Accent color:** `emerald-600` (green — reads as "safe/verified" in Pakistani business context, matches WhatsApp brand adjacency).

---

## 2. Screen inventory

Five screens. Every screen has a route, a mobile primary task, and a data contract.

| # | Route | Screen name | Mobile primary task | Auth |
|---|---|---|---|---|
| 1 | `/login` | Login | Owner logs in with phone + OTP | Public |
| 2 | `/` | Agents overview (home) | See all active agents, jump to conversations | Protected |
| 3 | `/conversations` | Conversation list | Find a specific buyer's chat | Protected |
| 4 | `/conversations/[id]` | Conversation detail | Read a chat + inspect any agent reply | Protected |
| 5 | `/conversations/[id]/audit/[messageId]` | Audit ledger view (drawer) | See *why* the agent said X | Protected |

**Explicitly not shipping in MVP:** settings page, billing page, user profile, notification preferences, agent creation flow (agents are provisioned via backend seed for pilot SMEs).

---

## 3. Per-screen specs

### 3.1 `/login`

**Purpose:** Phone-number-based login. OTP delivered via SMS (mocked in dev; real Twilio in staging).

**Layout:** Centered card, mobile-first (single column, 360px min viewport). Sindh Agents wordmark top. Two states via one component: `enter-phone` → `enter-otp`.

**Components:**
- `Card` (shadcn) — wraps the form
- `Input` type="tel" — phone number, `+92 3XX XXXXXXX` placeholder
- `Input` type="text" inputMode="numeric" pattern="[0-9]*" — 6-digit OTP
- `Button` variant="default" — "OTP bhejain" (Send OTP) → "Login karein" (Log in)
- `Skeleton` — for the 30s OTP wait state

**Roman Urdu strings:**
| Key | Roman Urdu | English fallback (for judges) |
|---|---|---|
| `login.title` | "Login karein" | "Log in" |
| `login.phonePlaceholder` | "Phone number daalein" | "Enter phone number" |
| `login.otpPrompt` | "OTP daalein (SMS pe aaya hai)" | "Enter OTP (sent via SMS)" |
| `login.sendOtp` | "OTP bhejain" | "Send OTP" |
| `login.submit` | "Login karein" | "Log in" |
| `login.otpError` | "OTP galat hai. Dobara try karein." | "Wrong OTP. Try again." |

**Data contract:**
```typescript
// POST /api/auth/send-otp
type SendOtpRequest = { phone: string };  // E.164, +923XXXXXXXXX
type SendOtpResponse = { ok: true } | { ok: false; error: string };

// POST /api/auth/verify-otp
type VerifyOtpRequest = { phone: string; otp: string };
type VerifyOtpResponse =
  | { ok: true; smeId: string; smeName: string }  // sets BetterAuth session cookie
  | { ok: false; error: string };
```

**Mobile constraints:**
- Phone input auto-focuses on load.
- OTP input auto-focuses after successful `send-otp`.
- Numeric keyboard on OTP input.
- ≤2 taps to submit (tap phone field, type; tap OTP field, type, auto-submit on 6 digits).

**Empty/error states:**
- Rate limit hit: "Ek minute rukein, phir try karein." ("Wait a minute, then retry.")
- Invalid phone format: inline field error, don't disable button.

---

### 3.2 `/` — Agents overview (home)

**Purpose:** First screen owner sees post-login. Answers: "kya chal raha hai?" (what's happening?)

**Layout:** Header bar (SME name, logout dropdown) + agent cards grid (2 columns desktop, 1 column mobile) + "Recent conversations" section below.

**Components:**
- Header: `Avatar` (initials, SME name), `DropdownMenu` (logout, help)
- Agent card: custom card with `Card` shadcn base. Shows agent name, status dot (green=live, gray=paused), message count today, "View conversations →" link
- Recent conversations: 5-row list, tapping any row → `/conversations/[id]`

**Roman Urdu strings:**
| Key | Roman Urdu |
|---|---|
| `home.greeting` | "Assalam-o-alaikum, {ownerName}" |
| `home.agentsTitle` | "Aap ke agents" |
| `home.agentStatus.live` | "Kaam kar raha hai" |
| `home.agentStatus.paused` | "Ruka hua hai" |
| `home.recentConvos` | "Haal hi ki baat cheet" |
| `home.viewAll` | "Sab dekhein →" |
| `home.msgsToday` | "{n} messages aaj" |

**Data contract:**
```typescript
// GET /api/agents (server component fetch — no client cache)
type AgentsResponse = {
  smeName: string;
  ownerName: string;
  agents: Array<{
    id: string;
    name: string;         // e.g. "Inventory Agent"
    nameUrdu: string;     // e.g. "Stock Agent"
    status: 'live' | 'paused';
    messagesToday: number;
    lastActive: string;   // ISO timestamp
  }>;
  recentConversations: Array<{
    id: string;
    buyerName: string;
    lastMessagePreview: string;  // first 60 chars, no numeric truncation
    lastMessageAt: string;       // ISO timestamp
    unread: boolean;
  }>;
};
```

**Mobile constraints:**
- Agent cards stack single-column below 640px.
- Recent conversations use `Sheet` on mobile for full-height list — no nested scroll.
- ≤2 taps to reach any conversation (tap card → tap row = 2 taps).

**Empty state:** "Abhi tak koi conversation nahi. Buyers ke messages ka intezaar karein." ("No conversations yet. Wait for buyer messages.")

---

### 3.3 `/conversations` — Conversation list

**Purpose:** Full list of conversations. Filterable by buyer name.

**Layout:** Top: search input (`Input` with debounced `onChange`). Below: `data-table` on desktop, `ScrollArea` list of cards on mobile.

**Components:**
- `Input` — search by buyer name or phone
- `Tabs` — All / Unread / Flagged (Flagged = SME manually flagged a conversation for review)
- `DataTable` (desktop) — columns: Buyer, Last message, Last activity, Status
- Mobile cards — buyer name, preview, timestamp, unread dot

**Roman Urdu strings:**
| Key | Roman Urdu |
|---|---|
| `convos.searchPlaceholder` | "Buyer ka naam ya number dhundein" |
| `convos.tabAll` | "Sab" |
| `convos.tabUnread` | "Naye" |
| `convos.tabFlagged` | "Nishaan lagaye hue" |
| `convos.colBuyer` | "Buyer" |
| `convos.colLastMsg` | "Aakhri message" |
| `convos.colTime` | "Waqt" |

**Data contract:**
```typescript
// GET /api/conversations?tab=all|unread|flagged&q=<search>
type ConversationsResponse = {
  conversations: Array<{
    id: string;
    buyerName: string;
    buyerPhone: string;   // for display only, masked as +92 3XX ****XXX
    lastMessagePreview: string;
    lastMessageAt: string;
    unread: boolean;
    flagged: boolean;
    agentName: string;    // which agent handled it
    channel: 'widget' | 'whatsapp';   // day-one field; icon rendered in list row
  }>;
  total: number;
};
```

**Channel indicator:** Each row shows a small icon (12px) next to the buyer name — `ti-message-circle` for widget, `ti-brand-whatsapp` for WhatsApp. Purely visual — no interaction. MVP renders `widget` on all rows; demo-day flip lights up mixed rows.

**Mobile constraints:**
- Search input sticky at top on scroll.
- Tap row → `/conversations/[id]`.
- Long-press row → flag/unflag (Phase 2 nice-to-have; MVP: three-dot menu).

---

### 3.4 `/conversations/[id]` — Conversation detail

**Purpose:** Read a full conversation. Every agent reply has a tappable "🔍" (magnifier) icon that opens the audit ledger drawer for that message.

**Layout:** WhatsApp-inspired chat view. Buyer messages left-aligned in white bubbles; agent messages right-aligned in emerald-50 bubbles. Timestamps below each message. Sticky header with buyer name, phone, agent-in-use pill. Sticky bottom composer (disabled in MVP — read-only; owner does not reply from dashboard, agent does).

**Components:**
- `ScrollArea` — chat body
- Custom `MessageBubble` component (see below)
- `Sheet` (side=right on desktop, bottom on mobile) — audit ledger drawer, opened from magnifier
- `Badge` — agent-in-use pill

**MessageBubble structure:**
```tsx
type MessageBubbleProps = {
  message: {
    id: string;
    sender: 'buyer' | 'agent';
    text: string;                    // rendered verbatim — no client-side numeric formatting
    textOriginal?: string;           // buyer's original Roman Urdu (for reference)
    timestamp: string;
    audit?: {                        // only for sender='agent'
      messageId: string;             // for /audit/[messageId] route
    };
  };
};
```

**Audit magnifier:** Only rendered when `sender === 'agent'`. Icon: `ti-search`. Tapping opens the audit drawer (screen 3.5).

**Roman Urdu strings:**
| Key | Roman Urdu |
|---|---|
| `convo.agentPill` | "Agent: {agentNameUrdu}" |
| `convo.auditTooltip` | "Yeh jawaab kaise bana?" ("How was this reply made?") |
| `convo.readOnlyBanner` | "Aap yahan se reply nahi kar sakte. Agent khud kar raha hai." |

**Data contract:**
```typescript
// GET /api/conversations/[id]
type ConversationDetailResponse = {
  id: string;
  buyer: {
    name: string;
    phone: string;
    firstSeenAt: string;
  };
  agent: {
    id: string;
    nameUrdu: string;
  };
  messages: Array<{
    id: string;
    sender: 'buyer' | 'agent';
    text: string;
    textOriginal?: string;
    timestamp: string;
    auditMessageId?: string;   // present iff sender='agent'
  }>;
};
```

**Mobile constraints:**
- Chat viewport = 100vh minus header height. No page scroll — only chat body scrolls.
- Message bubbles wrap at 85% viewport width.
- Audit magnifier tap target ≥ 44×44px (WCAG).
- Numeric content in agent replies is non-selectable-styled to discourage copy-mangling (visual only; still copyable). This signals "these numbers came from your Excel."

**Empty state:** Conversation with no messages: "Buyer ne abhi tak message nahi bheja." ("Buyer hasn't messaged yet.")

---

### 3.5 `/conversations/[id]/audit/[messageId]` — Audit ledger (drawer)

**Purpose:** Trust wedge. Answers "why did the agent say X?" in ≤5 seconds of reading.

**Layout:** `Sheet` drawer, opens over the conversation. Not a full route in MVP — implemented as parallel route + intercepting route so URL is shareable but drawer overlays conversation.

**Contents (top to bottom):**
1. Header: "Yeh jawaab kaise bana?"
2. **Buyer's original message** — verbatim, monospace font.
3. **Agent's understanding** — one line: "Agent ne yeh samjha: {parsedIntent}" (e.g., "denim stock kitna hai puch rahe hain")
4. **Tools called** — list of tool invocations with inputs and outputs. Each tool call is a collapsible row:
   - Tool name (e.g., `read_excel_stock`)
   - Input parameters (JSON, pretty-printed, small font)
   - Output — displayed as-is (this is where numeric verbatim comes from)
5. **Agent's reply** — the same text shown in the chat.
6. **Timing** — total latency + per-tool latency.
7. **Model used** — e.g., "Llama 3.3 70B via Groq"
8. Footer: "Yeh galat lag raha hai? [Nishan lagayein]" (Flag button — Phase 2 wires to a review queue)

**Components:**
- `Sheet` from shadcn
- Custom `ToolCallRow` component (accordion-like)
- `Badge` for model name
- `Button` variant="outline" for flag

**Data contract:**
```typescript
// GET /api/audit/[messageId]
type AuditResponse = {
  messageId: string;
  buyerMessage: {
    text: string;
    timestamp: string;
  };
  parsedIntent: string;              // one-line Roman Urdu summary from the agent
  toolCalls: Array<{
    name: string;                    // e.g., 'read_excel_stock'
    inputs: Record<string, unknown>; // JSON-serializable
    outputs: unknown;                // JSON-serializable
    latencyMs: number;
  }>;
  agentReply: {
    text: string;
    timestamp: string;
  };
  model: string;                     // e.g., 'llama-3.3-70b-instruct'
  totalLatencyMs: number;
};
```

**Mobile constraints:**
- Drawer opens from bottom on mobile (≤ 768px), takes 90vh.
- Tool call rows collapsed by default. Tap to expand.
- ≤1 tap from any agent message = magnifier tap opens drawer. Drawer close = tap outside or drag down.

---

## 4. Widget contract (WA-webhook-compatible)

The chat widget is embedded on a public-facing URL for the demo (e.g., `demo.sindhagents.com`). The widget accepts messages from an anonymous "buyer" and posts them to the backend. **The exact same POST payload must work when Meta sends a webhook in Phase 2.**

### 4.1 Widget UI

**Layout:** Fixed-position bubble (bottom-right) that expands into a WhatsApp-like chat window on click. Header shows agent name + green online dot. Body shows message history for this browser session. Footer has textarea + send button.

**Not designed — copied from WhatsApp Web:**
- Bubble spacing, colors, avatars
- Timestamp position (below bubble, right-aligned for own messages)
- Read receipts (single tick = sent, double tick = agent read — MVP: always single tick)

**Component:** Single React component, `SindhAgentsWidget`, exported from `@/components/widget/SindhAgentsWidget.tsx`. Zero external dependencies beyond what dashboard uses.

### 4.2 Message contract — matches Meta WhatsApp webhook payload shape

```typescript
// Widget → Backend
// POST /api/widget/inbound
// Payload deliberately mirrors Meta's `messages` webhook payload
type WidgetInboundMessage = {
  // Meta-webhook-compatible fields:
  messaging_product: 'widget';            // Phase 2: 'whatsapp'
  metadata: {
    display_phone_number: string;         // agent's assigned phone (MVP: fixed dev number)
    phone_number_id: string;              // MVP: fixed dev ID
  };
  contacts: [{
    profile: { name: string };            // buyer name (MVP: prompted in widget on first open)
    wa_id: string;                        // buyer's phone or session ID (MVP: browser session ID)
  }];
  messages: [{
    from: string;                         // same as wa_id
    id: string;                           // client-generated UUID
    timestamp: string;                    // Unix epoch seconds, as string
    text: { body: string };
    type: 'text';                         // MVP: text-only. Meta supports image/audio — deferred.
  }];
};

// Backend → Widget (long-polling or SSE — Ayesha's choice)
// GET /api/widget/outbound?session=<wa_id>
type WidgetOutboundMessage = {
  messages: Array<{
    id: string;
    timestamp: string;
    text: { body: string };               // agent reply text, verbatim
    auditMessageId: string;               // links to /audit/[messageId] — visible to SME dashboard, not to widget UI
  }>;
};
```

**Why this shape:** Meta's WhatsApp Cloud API sends inbound messages in this exact structure. When Phase 2 flips `messaging_product` to `'whatsapp'` and points at the Meta webhook URL instead of `/api/widget/inbound`, backend code paths are identical. Zero refactor. This is the ADR-009 promise made concrete.

### 4.3 Widget constraints

- Widget must render on Chrome, Firefox, Safari, and Samsung Internet (last two versions each). Judges may test on any browser.
- Widget must work on 3G — total JS bundle ≤ 80KB gzipped.
- No third-party scripts. No analytics. No fonts from Google CDN — inline system font stack.
- Widget must not crash if backend is unreachable — show "Server abhi busy hai, thodi der mein try karein" and keep the textarea usable so user's typed message is not lost.

---

## 5. Global type contracts

For Claude Code to generate these once and reuse:

```typescript
// types/domain.ts

export type SmeId = string & { __brand: 'SmeId' };
export type AgentId = string & { __brand: 'AgentId' };
export type ConversationId = string & { __brand: 'ConversationId' };
export type MessageId = string & { __brand: 'MessageId' };

export type Agent = {
  id: AgentId;
  name: string;
  nameUrdu: string;
  status: 'live' | 'paused';
  createdAt: string;
};

export type Conversation = {
  id: ConversationId;
  smeId: SmeId;              // never rendered — server-scoped
  agentId: AgentId;
  buyerName: string;
  buyerPhone: string;
  channel: 'widget' | 'whatsapp';    // day-one field for zero-migration WA swap
  createdAt: string;
  lastMessageAt: string;
  unread: boolean;
  flagged: boolean;
};

export type Message = {
  id: MessageId;
  conversationId: ConversationId;
  sender: 'buyer' | 'agent';
  text: string;
  textOriginal?: string;
  timestamp: string;
  auditMessageId?: MessageId;
};
```

Branded types force server responses through a type gate — prevents accidental cross-SME ID leakage in the UI.

---

## 6. Mobile-first performance budget (Blocker 7)

Every screen must meet:

| Metric | Target | Measured on |
|---|---|---|
| Lighthouse Mobile Performance | ≥ 90 | Chrome DevTools throttled to Slow 4G, mid-tier Android |
| Lighthouse Accessibility | ≥ 95 | Same |
| Time to Interactive | ≤ 3s | Real device — Samsung A-series or similar |
| Primary task | ≤ 2 taps, ≤ 3s | Real device |
| Bundle size (first load JS) | ≤ 150KB gzipped per route | `next build` output |

**How this is enforced:**
- CI runs Lighthouse on every PR (Ayesha wires this).
- No new dependencies without a bundle-size impact note in PR description.
- Screens tested on a real Android device (Ayesha's phone or borrowed pilot SME device) before merge to `main`.

---

## 7. Directory structure (Claude Code — build to this)

```
app/
  (auth)/
    login/page.tsx
  (dashboard)/
    layout.tsx                    // Header + auth gate
    page.tsx                      // Screen 3.2 — agents overview
    conversations/
      page.tsx                    // Screen 3.3 — list
      [id]/
        page.tsx                  // Screen 3.4 — detail
        @audit/
          [messageId]/page.tsx   // Screen 3.5 — parallel route drawer
  api/
    auth/
      send-otp/route.ts
      verify-otp/route.ts
    agents/route.ts
    conversations/route.ts
    conversations/[id]/route.ts
    audit/[messageId]/route.ts
    widget/
      inbound/route.ts
      outbound/route.ts
components/
  ui/                             // shadcn generated
  chat/
    MessageBubble.tsx
    ToolCallRow.tsx
    AuditDrawer.tsx
  widget/
    SindhAgentsWidget.tsx
lib/
  auth.ts                         // BetterAuth setup
  api.ts                          // typed fetch wrappers
  strings.ts                      // Roman Urdu string catalog
types/
  domain.ts                       // types from section 5
```

---

## 8. Claude Code handoff checklist

Before starting implementation, verify:

- [ ] Ayesha has signed off on this spec (change log entry below).
- [ ] Arham has provided the API contract (`api-contract.md`) matching all `type XxxResponse` above.
- [ ] Baneen has approved the Roman Urdu string catalog (`lib/strings.ts` values).
- [ ] Backend seed data exists for at least one test SME with 3 conversations and 20 messages (for local dev + demo).
- [ ] shadcn is initialized in a fresh Next.js 14 App Router repo. Only the components listed in section 1 are installed.
- [ ] BetterAuth is wired against Neon (dev branch) with phone-OTP flow.

**Then hand this spec + the API contract + the string catalog to Claude Code as the sole source of truth. Any Claude Code question not answered by these three documents = someone updates the spec before coding continues.**

---

## Change log

| Date | Change | Owner |
|---|---|---|
| 2026-07-23 | Initial draft. Awaiting Ayesha sign-off + Baneen Roman Urdu review. | Arham |
| 2026-07-23 | Add `channel` field to Conversation type + list-row icon. Widget-first MVP; demo-day flip lights up WA rows. | Arham |
