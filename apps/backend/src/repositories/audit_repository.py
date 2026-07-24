import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class ToolCallRecord:
    name: str
    inputs: dict[str, object]
    outputs: dict[str, object]
    latency_ms: int


@dataclass
class AgentReplyResult:
    message_id: str
    audit_id: str


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def write_agent_reply_with_audit(
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
        # CLAUDE.md §7.3 — audit write is in the SAME transaction as the
        # agent-message write. No commit happens until both succeed.
        message_id = str(uuid7())
        audit_id = str(uuid7())

        await self.db.execute(
            text(
                "INSERT INTO messages (id, sme_id, conversation_id, sender, text, timestamp_ts) "
                "VALUES (:id, :sme_id, :conversation_id, 'agent', :text, now())"
            ),
            {
                "id": message_id,
                "sme_id": sme_id,
                "conversation_id": conversation_id,
                "text": agent_reply_text,
            },
        )

        tool_calls_json = json.dumps(
            [
                {
                    "name": tc.name,
                    "inputs": tc.inputs,
                    "outputs": tc.outputs,
                    "latency_ms": tc.latency_ms,
                }
                for tc in tool_calls
            ]
        )
        await self.db.execute(
            text(
                "INSERT INTO audit_entries "
                "(id, sme_id, message_id, buyer_message_id, parsed_intent, tool_calls, "
                "agent_reply_text, model, total_latency_ms) "
                "VALUES (:id, :sme_id, :message_id, :buyer_message_id, :parsed_intent, "
                "CAST(:tool_calls AS jsonb), :agent_reply_text, :model, :total_latency_ms)"
            ),
            {
                "id": audit_id,
                "sme_id": sme_id,
                "message_id": message_id,
                "buyer_message_id": buyer_message_id,
                "parsed_intent": parsed_intent,
                "tool_calls": tool_calls_json,
                "agent_reply_text": agent_reply_text,
                "model": model,
                "total_latency_ms": total_latency_ms,
            },
        )

        await self.db.execute(
            text("UPDATE messages SET audit_entry_id = :audit_id WHERE id = :id"),
            {"audit_id": audit_id, "id": message_id},
        )
        await self.db.execute(
            text("UPDATE messages SET is_pending = false WHERE id = :id"),
            {"id": buyer_message_id},
        )

        await self.db.commit()
        return AgentReplyResult(message_id=message_id, audit_id=audit_id)
