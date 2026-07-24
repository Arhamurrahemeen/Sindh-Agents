import json

from src.services.groq_client import ChatCompleter

# CLAUDE.md §7.2 — the narrator must not invent numbers. Tool outputs are
# inserted verbatim below; the eval corpus (P5) asserts numeric equality
# against them. This prompt is the enforcement point for that invariant.
NARRATOR_SYSTEM_PROMPT_TEMPLATE = """You are the reply-writing module for a Stock Agent. You \
write the final Roman Urdu reply a buyer sees, in a warm, direct textile-trader voice ("bhai").

CRITICAL RULE: every number in your reply — stock counts, prices, dates, quantities — MUST \
come verbatim from the tool outputs below. Never calculate, round, estimate, or convert a \
number yourself. If the tool outputs don't answer the buyer's question, say "pata nahi kar \
paya" (couldn't check) — never guess a number.

Tool outputs (verbatim, use these exactly):
{tool_outputs_json}

Respond with ONLY the Roman Urdu reply text. No JSON, no explanation, no markdown."""


def _build_system_prompt(tool_outputs: list[dict[str, object]]) -> str:
    return NARRATOR_SYSTEM_PROMPT_TEMPLATE.format(tool_outputs_json=json.dumps(tool_outputs))


async def narrate(
    completer: ChatCompleter,
    model: str,
    buyer_message: str,
    tool_outputs: list[dict[str, object]],
) -> str:
    reply = await completer.complete(
        model=model,
        system_prompt=_build_system_prompt(tool_outputs),
        messages=[{"role": "user", "content": buyer_message}],
        response_format_json=False,
    )
    return reply.strip()
