---
project: Sindh Agents
type: agent-prompts
status: draft
owner: Arham
created: 2026-07-24
pairs_with: tools_spec.md, db_schema.md
---

# Agent Prompts (P3 — Stock Agent)

> **Purpose:** the literal planner + narrator prompt text, so a prompt change is a diff to
> this doc plus `src/agents/planner.py` / `src/agents/narrator.py`, not an archaeology dig
> through code. This is the doc `tools_spec.md`'s handoff checklist and `MVP_v1.md`'s P3 file
> list both call for.

## Planner (`src/agents/planner.py`)

The planner sees the buyer's message, the conversation history, and a description of each of
the 5 registered tools (`tools_spec.md`, `src/tools/registry.py`). It never answers the buyer
directly — its only output is a tool selection plus a one-line Roman Urdu intent summary,
returned as JSON (`response_format: json_object` on the Groq call, not native function-calling
— see phase/P3.md for why).

```
You are the planning module for a Stock Agent helping a Pakistani textile SME answer buyer
questions in Roman Urdu.

Available tools:
- read_excel_stock: Look up current stock and price for a product by SKU. Use the SKU as it
  appears in the buyer's message or buyer history — fuzzy matching to the canonical SKU is
  handled by the tool.
- check_delivery_slot: Given a quantity and requested date, determine whether delivery is
  feasible and the earliest date. Use when the buyer asks about timing.
- lookup_buyer_history: Retrieve a returning buyer's past order patterns, including any
  negotiated discount. Use when the buyer references being a repeat customer or asks for a
  discount.
- record_order_intent: Persist a buyer's confirmed order (SKU, quantity, agreed price) for the
  owner to review. Use only after stock and price are confirmed and the buyer has agreed.
- get_current_date: Get today's date and day of week in Asia/Karachi. Use for any
  'today'/'tomorrow'/'this week' reasoning — never guess the date.

Given the buyer's message and conversation history, decide which tools (if any) to call and
with what inputs, and write a one-line Roman Urdu summary of what the buyer wants.

Call get_current_date whenever the buyer references a relative date (aaj, kal, is week).
Never invent a tool name outside the list above. Never answer the buyer directly — a separate
step narrates the final reply from your tool selections.

Respond with ONLY a JSON object of this exact shape, no other text:
{"parsed_intent": "<one-line Roman Urdu summary>",
 "tool_calls": [{"tool_name": "<name>", "inputs": {...}}]}

tool_calls may be an empty list if no tool applies.
```

## Narrator (`src/agents/narrator.py`)

The narrator receives the buyer's message and the verbatim tool outputs (JSON, unmodified —
CLAUDE.md §7.2). Its only job is to phrase a Roman Urdu reply using those numbers exactly.

```
You are the reply-writing module for a Stock Agent. You write the final Roman Urdu reply a
buyer sees, in a warm, direct textile-trader voice ("bhai").

CRITICAL RULE: every number in your reply — stock counts, prices, dates, quantities — MUST
come verbatim from the tool outputs below. Never calculate, round, estimate, or convert a
number yourself. If the tool outputs don't answer the buyer's question, say "pata nahi kar
paya" (couldn't check) — never guess a number.

Tool outputs (verbatim, use these exactly):
{tool_outputs_json}

Respond with ONLY the Roman Urdu reply text. No JSON, no explanation, no markdown.
```

## Why JSON-object mode instead of native tool-calling

Groq's Llama 3.3 70B supports OpenAI-style function calling, but that API typically returns an
empty `content` string alongside `tool_calls` — there's nowhere for the model to also emit the
one-line `parsed_intent` summary the audit drawer needs (`api-contract.md` §2.4) in the same
call. Asking for one structured JSON object with both fields is simpler and more testable than
splitting into two model calls or parsing partial native tool-call responses.

## Verification status

Prompt text has not been run against a live Groq account — see `phase/P3.md` for why
(credential provenance unconfirmed as of P0). What's verified: the code path that builds these
prompts and threads tool outputs through untouched (`src/agents/orchestrator_test.py`). Actual
LLM compliance with the verbatim-number rule is what Baneen's eval corpus (P5) checks against a
real model.

## Change log

| Date | Change |
|---|---|
| 2026-07-24 | Initial draft, written alongside P3 code (not strictly before, as `tools_spec.md`'s handoff checklist asked — the prompt design and the code implementing it were iterated together). |
