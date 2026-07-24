---
project: Sindh Agents
type: spec
status: draft
owner: Baneen (owns corpus content + pass/fail calls)
created: 2026-07-24
pairs_with: CLAUDE.md, tools_spec.md, agent_prompts.md
---

# Roman Urdu Eval Spec (P5)

> **Purpose:** defines the corpus format and gate math for `apps/backend/evals/roman_urdu/`,
> so a case can be added or a threshold argued about without re-deriving the harness from code.

## 1. What this eval actually checks

CLAUDE.md §7.2's deterministic-narrator invariant is the whole reason this exists: the
narrator LLM must never invent a number. Each corpus case sends a real Roman Urdu buyer
message through the real, un-mocked stack — real Groq call (planner + narrator), real
Postgres (seeded stock/buyer data), real tool execution — and checks three things about
what actually happened:

1. **Tool selection** — did the planner call the tool(s) the case expects?
2. **Verbatim numeric propagation** — do the exact strings the seeded data would produce
   (e.g. `"450"`, `"1200.00"`) appear character-for-character in the final narrated reply?
3. **No leakage / no fabrication** — for cases with nothing to report (unknown SKU,
   ambiguous SKU), does the reply say `"pata nahi"` rather than guessing, and does it avoid
   leaking an unrelated SKU's numbers?

This is why the eval must run against real infrastructure, not fakes — `orchestrator_test.py`
already proves the *code path* preserves tool output verbatim (see its
`test_tool_output_reaches_narrator_verbatim`); what this eval proves is that the *live model*,
given the real prompt, actually behaves that way. That's a probabilistic property, which is
why the gate is 80%, not 100%.

## 2. Corpus format

`apps/backend/evals/roman_urdu/corpus.jsonl` — one JSON object per line:

```json
{
  "id": "stock-denim-classic",
  "buyer_key": "fresh",
  "buyer_message": "denim kitni hai bhai, aur rate kya hai?",
  "expect_tool_calls": ["read_excel_stock"],
  "expect_verbatim": ["450", "1200.00"],
  "forbid_substrings": [],
  "dynamic_check": null
}
```

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique, kebab-case, human-readable in a failure log. |
| `buyer_key` | string | `"fresh"` — a new buyer is created per case (unique `wa_id`), so `lookup_buyer_history` sees `is_returning=false`. Otherwise one of `"ali-traders"`, `"saleem-fabrics"`, `"khan-garments"` — maps to `seeds/pilot_sme.py`'s seeded `wa_id`s, so history-dependent cases can exercise the returning-buyer path. |
| `buyer_message` | string | The literal Roman Urdu text sent as the buyer's message. |
| `expect_tool_calls` | string[] | Tool names that **must** appear among the tools the planner actually invoked. Subset check, not exact-set — the planner calling one extra tool doesn't fail the case. |
| `expect_verbatim` | string[] | Substrings that **must** appear character-for-character in the narrator's final reply text. This is the hard-fail numeric check. |
| `forbid_substrings` | string[] | Substrings that must **not** appear — guards against a specific known-wrong number leaking in (e.g. a different SKU's price). |
| `dynamic_check` | `"current_weekday" \| null` | For cases whose expected value depends on when the eval runs (e.g. "aaj kaunsa din hai") — the harness computes the real expected value at run time (`now_in_karachi().strftime("%A")`) instead of a hardcoded string that would go stale. |

A case **passes** only if every `expect_tool_calls` entry was called, every
`expect_verbatim` entry is present, no `forbid_substrings` entry is present, and the
`dynamic_check` (if any) matches. Any single miss fails the whole case — there's no partial
credit within a case, only across the corpus.

## 3. Gate math

```
pass_rate = (cases where passed == true) / (total cases) * 100
hard_fail = pass_rate < 80.0
```

- 30 cases in the current corpus (`apps/backend/evals/roman_urdu/corpus.jsonl`).
- Below 80% (i.e. more than 6 of 30 failing) → `python -m evals.roman_urdu` exits 1 → CI
  blocks the PR per `.github/workflows/ci.yml`.
- The 80% figure comes from `CLAUDE.md` §8 and `MVP_v1.md`'s P5 done-means directly — not
  re-derived here.
- **Who calls it:** per `CLAUDE.md` §8's test-rule spirit ("below 80% hard-fail rate = PR
  does not merge") and `MVP_v1.md`'s ownership sketch, Baneen owns the actual "is 78% okay
  this week" judgment call, not whoever last tuned the prompt. The harness only reports the
  number and the exit code — it doesn't waive the threshold.

## 4. Why some cases have weak (or no) `expect_verbatim`

Not every case can assert a hard number without becoming brittle or, worse, testing the LLM's
own math instead of the invariant:

- **Delivery-slot feasibility** depends on the real clock (`now.hour < 11` changes the
  `earliest_date`/`delayed` outcome) — asserting an exact date would make the case flaky by
  time-of-day, not by regression. The one delivery case that *does* assert a hard number
  (`delivery-partial-stretch-denim`, expecting `"220"`) picks a scenario whose numeric output
  (`partial_quantity_available`) is independent of the clock — requested quantity (300)
  exceeds seeded stock (220) regardless of what time the eval runs.
- **Buyer-history cases for non-returning buyers** have nothing to assert positively — the
  correct behavior is "don't invent a discount," which isn't a substring you can require.
  These cases still check `expect_tool_calls` (did `lookup_buyer_history` actually get
  called), which is real signal even without a verbatim check.
- **Out-of-stock case** (`canvas-heavy`, seeded `stock=0`) deliberately does **not** require
  `"0"` to appear — a natural Roman Urdu reply for zero stock says something like "stock
  khatam hai," not the literal digit. Forcing `"0"` into the assertion would fail *correct*
  narrator behavior. Instead it asserts the SKU's own numbers don't get confused with another
  SKU's (`forbid_substrings`).

## 5. Running it

```bash
# Inside the backend container (needs the seeded pilot SME + a real GROQ_API_KEY)
cd apps/backend
python -m evals.roman_urdu
```

Prints one `PASS`/`FAIL` line per case (with reasons on failure), then the summary line and
exit code. See `phase/P5.md` for what a real run against live credentials returned.

## 6. Adding a case

1. Confirm the expected tool output against the seed data directly
   (`apps/backend/seeds/pilot_sme.py` or a live `psql` query) — never guess a number.
2. Prefer a Roman Urdu phrasing that unambiguously names one SKU/buyer — the planner is a
   real LLM and will sometimes under- or over-specify a fuzzy match; vague phrasing produces
   a flaky case, not a meaningful one.
3. If the case's correct answer can't be pinned to a fixed string (a live clock, an LLM
   wording choice), don't force `expect_verbatim` — use `expect_tool_calls` alone, or add a
   `forbid_substrings` negative check instead. A weak case that's honestly weak is better
   than a strong-looking case that's actually testing today's date.

## Change log

| Date | Change |
|---|---|
| 2026-07-24 | Initial draft, written alongside the P5 harness implementation. |
