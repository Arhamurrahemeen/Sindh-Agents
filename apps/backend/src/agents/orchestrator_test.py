import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel

from src.agents.orchestrator import process_buyer_message
from src.repositories.audit_repository import AgentReplyResult, ToolCallRecord
from src.tools.registry import ToolSpec
from src.tools.types import ToolContext, ToolSuccess


class FakeToolInput(BaseModel):
    sku: str


class FakeToolOutputData(BaseModel):
    stock: int
    price_per_unit: str


async def _fake_tool(
    inputs: FakeToolInput, context: ToolContext
) -> ToolSuccess[FakeToolOutputData]:
    # a known, exact number the test asserts survives untouched end-to-end
    return ToolSuccess[FakeToolOutputData](
        data=FakeToolOutputData(stock=450, price_per_unit="1200.00")
    )


FAKE_TOOLS = {
    "fake_tool": ToolSpec(
        name="fake_tool", description="test tool", input_model=FakeToolInput, func=_fake_tool
    )
}


class FakeChatCompleter:
    def __init__(self, planner_json: dict[str, object], narrator_reply: str) -> None:
        self.planner_json = planner_json
        self.narrator_reply = narrator_reply
        self.narrator_calls: list[list[dict[str, str]]] = []
        self.narrator_system_prompts: list[str] = []

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        response_format_json: bool,
    ) -> str:
        if response_format_json:
            return json.dumps(self.planner_json)
        self.narrator_calls.append(messages)
        self.narrator_system_prompts.append(system_prompt)
        return self.narrator_reply


@dataclass
class RecordedAuditCall:
    tool_calls: list[ToolCallRecord]
    agent_reply_text: str


class FakeAuditWriter:
    def __init__(self) -> None:
        self.calls: list[RecordedAuditCall] = []

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
    ) -> AgentReplyResult:
        self.calls.append(
            RecordedAuditCall(tool_calls=tool_calls, agent_reply_text=agent_reply_text)
        )
        return AgentReplyResult(message_id="agent-msg-1", audit_id="audit-1")


async def test_tool_output_reaches_narrator_verbatim() -> None:
    completer = FakeChatCompleter(
        planner_json={
            "parsed_intent": "denim stock puch rahe hain",
            "tool_calls": [{"tool_name": "fake_tool", "inputs": {"sku": "denim"}}],
        },
        narrator_reply="Bhai, 450 pieces hain, Rs. 1200.00 per piece.",
    )
    audit_writer = FakeAuditWriter()

    result = await process_buyer_message(
        db=None,  # type: ignore[arg-type]  # never touched — audit_writer/tools_by_name are faked
        completer=completer,
        sme_id="sme-1",
        agent_id="agent-1",
        buyer_id="buyer-1",
        conversation_id="convo-1",
        buyer_message_id="msg-1",
        buyer_message_text="denim kitni hai",
        conversation_history=[],
        logger=logging.getLogger("test"),
        tools_by_name=FAKE_TOOLS,
        audit_writer=audit_writer,
    )

    # the exact number the tool returned must appear, untouched, in what the
    # narrator was shown — this is the deterministic invariant at the code level
    narrator_prompt = audit_writer.calls[0].tool_calls[0].outputs
    data = narrator_prompt["data"]
    assert isinstance(data, dict)
    assert data["stock"] == 450
    assert "450" in completer.narrator_system_prompts[0]
    assert result.reply_text == "Bhai, 450 pieces hain, Rs. 1200.00 per piece."


async def test_unknown_tool_name_is_skipped_not_fatal() -> None:
    completer = FakeChatCompleter(
        planner_json={
            "parsed_intent": "kuch puch rahe hain",
            "tool_calls": [{"tool_name": "does_not_exist", "inputs": {}}],
        },
        narrator_reply="Pata nahi kar paya.",
    )
    audit_writer = FakeAuditWriter()

    result = await process_buyer_message(
        db=None,  # type: ignore[arg-type]
        completer=completer,
        sme_id="sme-1",
        agent_id="agent-1",
        buyer_id="buyer-1",
        conversation_id="convo-1",
        buyer_message_id="msg-1",
        buyer_message_text="kuch bhi",
        conversation_history=[],
        logger=logging.getLogger("test"),
        tools_by_name=FAKE_TOOLS,
        audit_writer=audit_writer,
    )

    assert audit_writer.calls[0].tool_calls == []
    assert result.reply_text == "Pata nahi kar paya."


async def test_invalid_tool_input_is_skipped_not_fatal() -> None:
    completer = FakeChatCompleter(
        planner_json={
            "parsed_intent": "kuch puch rahe hain",
            "tool_calls": [{"tool_name": "fake_tool", "inputs": {"wrong_field": 1}}],
        },
        narrator_reply="Pata nahi kar paya.",
    )
    audit_writer = FakeAuditWriter()

    await process_buyer_message(
        db=None,  # type: ignore[arg-type]
        completer=completer,
        sme_id="sme-1",
        agent_id="agent-1",
        buyer_id="buyer-1",
        conversation_id="convo-1",
        buyer_message_id="msg-1",
        buyer_message_text="kuch bhi",
        conversation_history=[],
        logger=logging.getLogger("test"),
        tools_by_name=FAKE_TOOLS,
        audit_writer=audit_writer,
    )

    assert audit_writer.calls[0].tool_calls == []
