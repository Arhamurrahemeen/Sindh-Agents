import json
from dataclasses import dataclass
from datetime import datetime

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


@dataclass
class AuditDetail:
    message_id: str
    buyer_message_text: str
    buyer_message_timestamp: datetime
    parsed_intent: str
    tool_calls: list[dict[str, object]]
    agent_reply_text: str
    agent_reply_timestamp: datetime
    model: str
    total_latency_ms: int
    created_at: datetime


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

    async def get_by_message_id(self, message_id: str, sme_id: str) -> AuditDetail | None:
        # ae.message_id references the AGENT reply only (audit_only_for_agent constraint),
        # so a buyer message_id naturally yields no row here — matches api-contract.md §2.4's
        # "belongs to a buyer message" 404 case without a separate check.
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT ae.message_id, ae.parsed_intent, ae.tool_calls, ae.agent_reply_text,
                           ae.model, ae.total_latency_ms, ae.created_at,
                           agent_msg.timestamp_ts AS agent_reply_timestamp,
                           buyer_msg.text AS buyer_message_text,
                           buyer_msg.timestamp_ts AS buyer_message_timestamp
                    FROM audit_entries ae
                    JOIN messages agent_msg ON agent_msg.id = ae.message_id
                    JOIN messages buyer_msg ON buyer_msg.id = ae.buyer_message_id
                    WHERE ae.message_id = :message_id AND ae.sme_id = :sme_id
                    """
                ),
                {"message_id": message_id, "sme_id": sme_id},
            )
        ).first()
        if row is None:
            return None
        return AuditDetail(
            message_id=str(row.message_id),
            buyer_message_text=row.buyer_message_text,
            buyer_message_timestamp=row.buyer_message_timestamp,
            parsed_intent=row.parsed_intent,
            tool_calls=row.tool_calls,
            agent_reply_text=row.agent_reply_text,
            agent_reply_timestamp=row.agent_reply_timestamp,
            model=row.model,
            total_latency_ms=row.total_latency_ms,
            created_at=row.created_at,
        )
