from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.errors import ApiError
from src.middleware.auth import AuthSession, require_session
from src.repositories.audit_repository import AuditRepository

router = APIRouter()

AUDIT_RETENTION_DAYS = 90


class AuditBuyerMessage(BaseModel):
    text: str
    timestamp: str


class AuditToolCall(BaseModel):
    name: str
    inputs: dict[str, object]
    outputs: object
    latencyMs: int


class AuditAgentReply(BaseModel):
    text: str
    timestamp: str


class AuditData(BaseModel):
    messageId: str
    buyerMessage: AuditBuyerMessage
    parsedIntent: str
    toolCalls: list[AuditToolCall]
    agentReply: AuditAgentReply
    model: str
    totalLatencyMs: int


class AuditResponse(BaseModel):
    ok: bool = True
    data: AuditData


@router.get("/{message_id}")
async def get_audit_route(
    message_id: str,
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> AuditResponse:
    detail = await AuditRepository(db).get_by_message_id(message_id, session.sme_id)
    if detail is None:
        raise ApiError(404, "NOT_FOUND", "Audit record not found")

    if detail.created_at < datetime.now(UTC) - timedelta(days=AUDIT_RETENTION_DAYS):
        raise ApiError(410, "AUDIT_EXPIRED", "Audit record has expired")

    return AuditResponse(
        data=AuditData(
            messageId=detail.message_id,
            buyerMessage=AuditBuyerMessage(
                text=detail.buyer_message_text,
                timestamp=detail.buyer_message_timestamp.isoformat(),
            ),
            parsedIntent=detail.parsed_intent,
            toolCalls=[
                AuditToolCall(
                    name=cast(str, tc["name"]),
                    inputs=cast("dict[str, object]", tc["inputs"]),
                    outputs=tc["outputs"],
                    latencyMs=cast(int, tc["latency_ms"]),
                )
                for tc in detail.tool_calls
            ],
            agentReply=AuditAgentReply(
                text=detail.agent_reply_text,
                timestamp=detail.agent_reply_timestamp.isoformat(),
            ),
            model=detail.model,
            totalLatencyMs=detail.total_latency_ms,
        )
    )
