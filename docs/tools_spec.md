---
project: Sindh Agents
type: tools-spec
status: draft (awaiting Arham backend sign-off)
owner: Arham
created: 2026-07-23
scope: Hackathon MVP — Stock Agent tools
pairs_with: api-contract.md, agent_prompts.md, db_schema.md
---

# Tools Spec (MVP — Stock Agent)

> **Purpose:** Every tool function the Stock Agent can call. Names, signatures, inputs, outputs, timing budgets, error modes. This is what powers the audit ledger's `tool_calls[]` array.

> **Architecture:** MCP-*shaped* functions in FastAPI (ADR-013). Each tool is a Python async function with a Pydantic-typed input and output. Signatures are structured so migration to a real MCP transport in Phase 3 is a wrapper, not a rewrite.

> **MVP has ONE agent — Stock Agent — with 5 tools.** Tax Reminder Agent (visible in the home mockup for realism) is a Phase 1 add. Multi-agent orchestration is Phase 3.

---

## 0. Rules that apply to every tool

### 0.1 Function signature convention

Every tool is an async function with this shape:

```python
async def tool_name(
    inputs: ToolNameInput,
    context: ToolContext,
) -> ToolNameOutput:
    ...
```

Where:
- `ToolNameInput` and `ToolNameOutput` are Pydantic v2 models — this is what shows up in the audit drawer verbatim.
- `ToolContext` provides `sme_id`, `agent_id`, `conversation_id`, `request_id`, DB session, logger. Never bypass it — never pass `sme_id` as a direct arg.

### 0.2 Registration

Tools are registered in `apps/backend/src/tools/registry.py`:

```python
STOCK_AGENT_TOOLS = [
    ReadExcelStock,
    CheckDeliverySlot,
    LookupBuyerHistory,
    RecordOrderIntent,
    GetCurrentDate,
]
```

The planner LLM sees only the tools in the registered list for the current agent. No global tool exposure.

### 0.3 Timing budget

Per-tool P95 latency budget. Exceeding = warning in logs, second exceedance = slow-tool alert:

| Category | P95 budget |
|---|---|
| DB read (indexed) | 100ms |
| DB read (aggregation) | 300ms |
| DB write | 150ms |
| File read (Excel snapshot) | 250ms |
| External API (none in MVP) | 800ms |

Tools that exceed budget → the narrator receives a partial result flag and must say "abhi confirm nahi kar sakta" (can't confirm right now) rather than guess.

### 0.4 Error modes

Every tool can fail in three ways. Each is represented as a discriminated output, not an exception:

```python
class ToolSuccess[T](BaseModel):
    ok: Literal[True] = True
    data: T

class ToolNotFound(BaseModel):
    ok: Literal[False] = False
    reason: Literal["not_found"]
    detail: str  # for logs, not narrator

class ToolDegraded(BaseModel):
    ok: Literal[False] = False
    reason: Literal["degraded"]
    detail: str  # e.g., "excel file lock, retry"
```

**Never raise from a tool.** The planner and narrator must be able to reason about failures.

### 0.5 Numeric output rule

Numbers in tool outputs are **native types** (int, Decimal, not str). The narrator receives them as JSON. String-cast happens only at the narrator prompt injection layer — deterministic engine invariant.

Currency is `Decimal(...)`, quantity is `int`, timestamps are ISO 8601 strings.

### 0.6 Idempotency

Read tools (`read_*`, `check_*`, `lookup_*`, `get_*`) are idempotent by definition.

Write tools (`record_*`) accept an `idempotency_key` field on their input. Same key within 24h returns the same output without side effects. Prevents double-write if the planner retries.

### 0.7 Language

Tool outputs contain data, not natural language. The narrator translates data → Roman Urdu reply. Do not put Urdu strings in tool outputs. **Exception:** `GetTaxDeadlines` returns deadline names (`"Sales Tax filing"`) and one-liner descriptions — those are constant Roman Urdu strings from the DB.

---

## 1. Tool: `read_excel_stock`

**Purpose:** Read the SME's current Excel stock sheet and return stock + price for a given SKU.

**Called when:** Buyer asks about stock, availability, or price for a product.

**Latency budget:** 250ms P95.

### Input

```python
class ReadExcelStockInput(BaseModel):
    sku: str = Field(
        ...,
        description="Product identifier — SME's internal SKU. "
                    "For MVP, matches the first column of the Excel sheet.",
        min_length=1,
        max_length=64,
    )
```

**Planner prompt hint (for `agent_prompts.md`):** "Use the SKU as it appears in the buyer's message or in the buyer history. If the buyer says 'denim,' pass 'denim' — the tool handles fuzzy match to canonical SKU."

### Output

```python
class StockItem(BaseModel):
    sku_canonical: str          # normalized SKU (e.g., "denim-classic")
    sku_matched_from: str       # what the planner passed (for audit clarity)
    stock: int                  # units in inventory
    unit: str                   # "pieces", "meters", "kg"
    price_per_unit: Decimal     # in PKR
    price_currency: Literal["PKR"]
    last_updated: str           # ISO 8601 — when the Excel snapshot was ingested
    low_stock_flag: bool        # true if stock <= reorder_threshold

class ReadExcelStockOutput(ToolSuccess[StockItem] | ToolNotFound):
    ...
```

### Fuzzy matching

- Exact SKU match first.
- Case-insensitive substring match second.
- Levenshtein distance ≤2 third.
- If multiple matches, return `not_found` with `detail="ambiguous: matched N SKUs, please clarify"`.

The narrator translates ambiguity to "kaunsa denim bhai? classic ya stretch?" (which denim, classic or stretch?).

### Not found behavior

```python
ToolNotFound(reason="not_found", detail="sku 'silk' has no match in current stock")
```

Narrator says: "Yeh item stock mein nahi mila. Kuch aur poochein?" ("Didn't find this item. Ask about something else?")

### Excel source of truth

SME's Excel file is stored as a snapshot in the DB (see `db_schema.md` §`excel_snapshots`). Tool reads the snapshot, not the raw file — file I/O is not on the request path.

Reingest on Excel re-upload happens via `POST /api/excel/reingest` (Phase 6, see `phase/P6.md`) — session-authenticated multipart upload from the dashboard's `/inventory` page. Replaces the whole snapshot; does not touch `read_excel_stock`/`ExcelStockRepository.list_for_sme`.

**Column mapping** (header row, case-insensitive):

| Excel column | DB field | Notes |
|---|---|---|
| SKU | `sku_canonical` | required |
| Aliases | `sku_aliases` | optional, comma-separated → parsed to `text[]` |
| Stock | `stock` | required, integer ≥ 0 |
| Unit | `unit` | required, one of `pieces/meters/kg/liters/boxes` (case-insensitive) |
| Price | `price_per_unit` | required, ≥ 0, rounded to 2dp |
| Reorder Threshold | `reorder_threshold` | optional, default 0 |

**Behavior:** SHA-256 of the raw file bytes is compared against the current active snapshot's `snapshot_hash`. If it matches, the upload is a no-op (`isNoop: true` in the response, nothing re-written). Otherwise: deactivate the current active snapshot, insert a new one as active, bulk-insert its rows — all in one transaction. A bad row (missing column, negative stock/price, bad unit, non-integer stock) rejects the whole file; nothing is partially written. File size capped at 2MB, row count capped at 500.

---

## 2. Tool: `check_delivery_slot`

**Purpose:** Given a quantity and requested date, determine feasibility and suggest a delivery date.

**Called when:** Buyer asks "kal tak mil jayega?" ("will I get it by tomorrow?") or gives a quantity + timeline.

**Latency budget:** 100ms P95.

### Input

```python
class CheckDeliverySlotInput(BaseModel):
    sku: str                    # from a prior read_excel_stock call typically
    quantity: int = Field(..., gt=0, le=100_000)
    requested_date: date        # in Asia/Karachi calendar
```

### Output

```python
class DeliverySlot(BaseModel):
    feasible: bool
    earliest_date: date         # if feasible=false, this is the true earliest
    reason: Literal[
        "stock_ok_delivery_ok",
        "stock_ok_delivery_delayed",
        "stock_low_partial_only",
        "stock_zero",
    ]
    partial_quantity_available: int | None  # if reason=stock_low_partial_only

class CheckDeliverySlotOutput(ToolSuccess[DeliverySlot]):
    ...
```

### Business rules (MVP hardcoded — Phase 1 becomes per-SME configurable)

- Same-day requests before 11am `Asia/Karachi` → feasible if stock ≥ quantity.
- Same-day after 11am → next business day earliest.
- Weekend (Friday + Saturday in Pakistan) → shift to Sunday.
- Public holidays: not modeled in MVP. Documented Phase 1 gap.

### Rationale in output

`reason` field carries the reasoning as a code, not a string. Narrator has a lookup table in Roman Urdu:

| `reason` | Roman Urdu template |
|---|---|
| `stock_ok_delivery_ok` | "Ho jayega bhai, {earliest_date} tak deliver kar denge." |
| `stock_ok_delivery_delayed` | "Stock hai lekin {earliest_date} se pehle mushkil hai." |
| `stock_low_partial_only` | "Puri quantity nahi hai — {partial_quantity_available} pieces mil sakte hain." |
| `stock_zero` | "Yeh item abhi khatam hai. Nayi stock ka waqt {earliest_date} hai." |

---

## 3. Tool: `lookup_buyer_history`

**Purpose:** Retrieve past-order patterns for a buyer — count, avg order size, negotiated discount rate, common SKUs. Feeds the "agent remembers" wedge.

**Called when:** Buyer identifies (has a phone/session in system for ≥1 prior conversation), and planner needs context.

**Latency budget:** 300ms P95 (aggregation + Qdrant hit).

### Input

```python
class LookupBuyerHistoryInput(BaseModel):
    buyer_id: str
    include_semantic_context: bool = True  # query Qdrant for related notes
```

### Output

```python
class BuyerHistory(BaseModel):
    is_returning: bool
    total_past_orders: int
    total_lifetime_value: Decimal
    avg_order_quantity: int | None
    common_skus: list[str]                          # top 3 by frequency
    typical_discount_pct: Decimal | None            # 0..100
    last_order_at: str | None                       # ISO 8601
    semantic_notes: list[str]                       # Qdrant hits, each ≤200 chars

class LookupBuyerHistoryOutput(ToolSuccess[BuyerHistory]):
    ...
```

### Qdrant integration

- Collection: `sme_{sme_id}_memory` (per-SME scoping per ADR-005).
- Query embedding: Cohere `embed-multilingual-v3.0` (1024-dim) on the current buyer message. Call with `input_type='search_query'`. Ingestion uses `input_type='search_document'`. Both are required by Cohere v3 models.
- Filter: `payload.buyer_id == buyer_id`.
- Top-K: 3.
- Score threshold: 0.7 cosine similarity. Below threshold = empty `semantic_notes`.

### First-time buyer

Returns `is_returning=false` with empty aggregates and empty semantic notes. Narrator does NOT hallucinate history — this is the deterministic invariant.

### Privacy note

`semantic_notes` may contain owner-authored notes ("Ali always haggles for 5%"). This is SME-authored context, not fabricated. Displayed in audit drawer under `outputs`.

---

## 4. Tool: `record_order_intent`

**Purpose:** Persist a buyer's stated intent (SKU + quantity + agreed price) so the SME can act on it. Not a purchase — a lead the owner reviews.

**Called when:** Buyer confirms a quantity + price after the agent has answered stock + price.

**Latency budget:** 150ms P95 (single DB insert).

### Input

```python
class RecordOrderIntentInput(BaseModel):
    idempotency_key: str = Field(
        ...,
        description="Client-generated UUID from planner. Prevents duplicate writes on retry.",
    )
    buyer_id: str
    sku_canonical: str
    quantity: int = Field(..., gt=0)
    agreed_price_per_unit: Decimal
    delivery_date: date
    notes: str | None = Field(None, max_length=500)  # buyer-stated context, e.g., "purana customer"
```

### Output

```python
class OrderIntent(BaseModel):
    intent_id: str
    created_at: str  # ISO 8601
    total_amount: Decimal  # quantity * agreed_price_per_unit
    dashboard_url: str  # deep link — SME can tap to see the intent in their dashboard

class RecordOrderIntentOutput(ToolSuccess[OrderIntent]):
    ...
```

### Side effects

- Insert into `order_intents` table (see `db_schema.md`).
- Emit `order_intent_created` event on `sme_events_{sme_id}` channel — the dashboard uses this to badge a notification (Phase 1 — MVP shows in the recent conversations list).
- Log to audit trail — `dashboard_url` in output is the concrete artifact SME sees.

### Idempotency

Same `idempotency_key` within 24h → returns the previously-written `OrderIntent` unchanged. Second call does not double-insert, does not re-emit event.

---

## 5. Tool: `get_current_date`

**Purpose:** Return the current date + day of week in `Asia/Karachi`. LLMs don't have reliable clocks; this is the deterministic clock.

**Called when:** Any tool or narrator response needs "aaj" (today), "kal" (tomorrow), "is week" (this week).

**Latency budget:** 10ms (in-process, no I/O).

### Input

```python
class GetCurrentDateInput(BaseModel):
    """No inputs. Always returns Asia/Karachi 'now'."""
```

### Output

```python
class CurrentDate(BaseModel):
    date: date                       # 2026-07-23
    day_of_week: Literal[            # in Urdu convention (Sat=first, Fri=weekend end)
        "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
    ]
    is_business_day: bool            # false on Fri, Sat
    hijri_date: str | None           # optional, Phase 1
    current_time_hhmm: str           # "14:32"

class GetCurrentDateOutput(ToolSuccess[CurrentDate]):
    ...
```

### Why a tool and not a model prior

LLMs guess dates when asked. On stage during demo, a wrong date breaks the entire "reliable AI employee" pitch. Tool call → verifiable in the audit drawer.

---

## 6. Tool inventory summary

| # | Tool | Category | Idempotent | Budget | DB touch | Qdrant touch |
|---|---|---|---|---|---|---|
| 1 | `read_excel_stock` | Read | Yes | 250ms | Yes | No |
| 2 | `check_delivery_slot` | Read | Yes | 100ms | Yes | No |
| 3 | `lookup_buyer_history` | Read | Yes | 300ms | Yes | Yes |
| 4 | `record_order_intent` | Write | Key-based | 150ms | Yes | No |
| 5 | `get_current_date` | Pure | Yes | 10ms | No | No |

Total: 5 tools for MVP Stock Agent.

---

## 7. Tool call representation in audit drawer

Each entry in `AuditResponse.data.toolCalls[]` from `api-contract.md` §2.4 is populated by the orchestrator like this:

```python
audit_tool_call = {
    "name": "read_excel_stock",
    "inputs": input_pydantic_model.model_dump(mode="json"),
    "outputs": output_pydantic_model.model_dump(mode="json"),
    "latency_ms": elapsed_ms,
}
```

The dashboard renders `inputs` and `outputs` verbatim (pretty-printed JSON). No transformation, no redaction. This is what makes the audit drawer trustworthy.

---

## 8. What is NOT a tool in MVP

Deliberate scope calls:

| Not-a-tool | Reason | Where it goes |
|---|---|---|
| `send_whatsapp_message` | No WhatsApp API in MVP | Widget handles reply delivery |
| `send_sms_reminder` | Phase 1 (SMS to buyer for payment) | ADR-010 |
| `check_payment_status` | Phase 1 (manual toggle) | ADR-010 |
| `file_tax_return` | Never — regulatory | ADR-011 |
| `search_web` | Not needed for closed business context | — |
| `send_email` | SMEs don't run business by email | — |
| `read_pdf_invoice` | Phase 2 (buyer sends PO as PDF) | ADR TBD |
| `update_excel_stock` | Phase 2 — MVP is read-only against Excel | ADR TBD |

---

## 9. Handoff checklist

Before Claude Code implements tools:

- [ ] `db_schema.md` defines: `excel_snapshots`, `buyers`, `order_intents`, `qdrant_collections` config.
- [ ] `agent_prompts.md` includes tool descriptions for the planner (each tool needs a natural-language "when to use" the planner LLM reads).
- [ ] Baneen has curated eval cases exercising every tool at least twice (found + not-found paths).
- [ ] Seed data (`seeds/pilot_sme.py`) includes one buyer with history for `lookup_buyer_history` to actually return data.
- [ ] Registry file (`apps/backend/src/tools/registry.py`) wires all 5 tools with docstrings the planner can read.

---

## Change log

| Date | Change |
|---|---|
| 2026-07-23 | Initial draft. 5 tools for MVP Stock Agent. |
| 2026-07-23 | Swap embedding provider OpenAI → Cohere `embed-multilingual-v3.0` for `lookup_buyer_history`. |
