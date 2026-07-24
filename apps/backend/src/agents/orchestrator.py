import logging
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents import narrator, planner
from src.channels.base import resolve_channel
from src.config import settings
from src.repositories.audit_repository import AgentReplyResult, AuditRepository, ToolCallRecord
from src.services.groq_client import ChatCompleter
from src.tools.registry import TOOLS_BY_NAME, ToolSpec
from src.tools.types import ToolContext


@dataclass
class OrchestrationResult:
    message_id: str
    audit_id: str
    reply_text: str


class AuditWriter(Protocol):
    async def __call__(
        self,
        sme_id: str,
        conversation_id: str,
        buyer_message_id: str,
        parsed_intent: str,
        tool_calls: list[ToolCallRecord],
        agent_reply_text: str,
        model: str,
        total_latency_ms: int,
    ) -> AgentReplyResult: ...


def _default_audit_writer(db: AsyncSession) -> AuditWriter:
    return AuditRepository(db).write_agent_reply_with_audit


async def process_buyer_message(
    db: AsyncSession,
    completer: ChatCompleter,
    *,
    sme_id: str,
    agent_id: str,
    conversation_id: str,
    buyer_id: str,
    conversation_channel: str = "widget",
    buyer_message_id: str,
    buyer_message_text: str,
    conversation_history: list[dict[str, str]],
    logger: logging.Logger,
    tools_by_name: dict[str, ToolSpec] = TOOLS_BY_NAME,
    audit_writer: AuditWriter | None = None,
) -> OrchestrationResult:
    writer = audit_writer or _default_audit_writer(db)
    start = time.monotonic()

    plan_result = await planner.plan(
        completer, settings.GROQ_MODEL, buyer_message_text, conversation_history
    )

    context = ToolContext(
        sme_id=sme_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        buyer_id=buyer_id,
        message_id=buyer_message_id,
        request_id=buyer_message_id,
        db=db,
        logger=logger,
    )

    tool_call_records: list[ToolCallRecord] = []
    tool_outputs_for_narrator: list[dict[str, object]] = []

    for call in plan_result.tool_calls:
        spec = tools_by_name.get(call.tool_name)
        if spec is None:
            logger.warning("planner_selected_unknown_tool tool_name=%s", call.tool_name)
            continue

        tool_inputs = call.inputs
        if call.tool_name == "lookup_buyer_history":
            # the planner LLM has no way to know the real buyer_id UUID from
            # conversation text (observed live: it hallucinated "current buyer") —
            # override with what the orchestrator already resolved, same spirit
            # as sme_id/agent_id never coming from the planner either.
            tool_inputs = {**call.inputs, "buyer_id": context.buyer_id}

        try:
            tool_input = spec.input_model.model_validate(tool_inputs)
        except ValidationError as exc:
            # tools_spec.md §0.4 — tools never raise, but the planner (an LLM) can
            # hand back malformed args; skip that call rather than crash the turn.
            logger.warning(
                "planner_gave_invalid_tool_input tool_name=%s inputs=%s error=%s",
                call.tool_name,
                call.inputs,
                exc,
            )
            continue

        tool_start = time.monotonic()
        output = await spec.func(tool_input, context)
        latency_ms = int((time.monotonic() - tool_start) * 1000)

        output_dict = output.model_dump(mode="json")
        tool_call_records.append(
            ToolCallRecord(
                name=call.tool_name, inputs=tool_inputs, outputs=output_dict, latency_ms=latency_ms
            )
        )
        tool_outputs_for_narrator.append({"tool": call.tool_name, "output": output_dict})

    reply_text = await narrator.narrate(
        completer, settings.GROQ_MODEL, buyer_message_text, tool_outputs_for_narrator
    )

    total_latency_ms = int((time.monotonic() - start) * 1000)

    result = await writer(
        sme_id=sme_id,
        conversation_id=conversation_id,
        buyer_message_id=buyer_message_id,
        parsed_intent=plan_result.parsed_intent,
        tool_calls=tool_call_records,
        agent_reply_text=reply_text,
        model=settings.GROQ_MODEL,
        total_latency_ms=total_latency_ms,
    )

    # CLAUDE.md §7.5 — actual delivery goes through the channel abstraction, not
    # a direct DB write here. For widget this is a no-op (the row writer already
    # committed above); for whatsapp (P6) this is where the real Twilio send happens.
    channel = resolve_channel(conversation_channel)
    await channel.send(conversation_id=conversation_id, text=reply_text)

    return OrchestrationResult(
        message_id=result.message_id, audit_id=result.audit_id, reply_text=reply_text
    )
