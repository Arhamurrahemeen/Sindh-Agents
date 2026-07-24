import json
from dataclasses import dataclass

from src.services.groq_client import ChatCompleter
from src.tools.registry import STOCK_AGENT_TOOLS

PLANNER_SYSTEM_PROMPT_TEMPLATE = """You are the planning module for a Stock Agent helping a \
Pakistani textile SME answer buyer questions in Roman Urdu.

Available tools (name, description, and the exact JSON schema "inputs" must match — field \
names are case-sensitive, use them exactly as given):
{tool_descriptions}

Given the buyer's message and conversation history, decide which tools (if any) to call and \
with what inputs, and write a one-line Roman Urdu summary of what the buyer wants.

Call get_current_date whenever the buyer references a relative date (aaj, kal, is week).
Never invent a tool name outside the list above. Never answer the buyer directly — a separate \
step narrates the final reply from your tool selections.

Respond with ONLY a JSON object of this exact shape, no other text:
{{"parsed_intent": "<one-line Roman Urdu summary>", \
"tool_calls": [{{"tool_name": "<name>", "inputs": {{...}}}}]}}

tool_calls may be an empty list if no tool applies."""


@dataclass
class PlannedToolCall:
    tool_name: str
    inputs: dict[str, object]


@dataclass
class PlanResult:
    parsed_intent: str
    tool_calls: list[PlannedToolCall]


def _build_system_prompt() -> str:
    descriptions = "\n".join(
        f"- {tool.name}: {tool.description}\n"
        f"  inputs schema: {json.dumps(tool.input_model.model_json_schema())}"
        for tool in STOCK_AGENT_TOOLS
    )
    return PLANNER_SYSTEM_PROMPT_TEMPLATE.format(tool_descriptions=descriptions)


async def plan(
    completer: ChatCompleter,
    model: str,
    buyer_message: str,
    conversation_history: list[dict[str, str]],
) -> PlanResult:
    raw = await completer.complete(
        model=model,
        system_prompt=_build_system_prompt(),
        messages=[*conversation_history, {"role": "user", "content": buyer_message}],
        response_format_json=True,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return PlanResult(parsed_intent="samajh nahi aaya", tool_calls=[])

    tool_calls = [
        PlannedToolCall(tool_name=str(tc.get("tool_name", "")), inputs=dict(tc.get("inputs", {})))
        for tc in parsed.get("tool_calls", [])
        if isinstance(tc, dict)
    ]
    return PlanResult(parsed_intent=str(parsed.get("parsed_intent", "")), tool_calls=tool_calls)
