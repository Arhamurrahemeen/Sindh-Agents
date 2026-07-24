from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.errors import ApiError
from src.middleware.auth import AuthSession, require_session
from src.repositories.conversation_repository import ConversationRepository, Tab
from src.repositories.message_repository import MessageRepository
from src.services.phone import mask_phone
from src.services.preview import truncate_preview

router = APIRouter()


class ConversationListItem(BaseModel):
    id: str
    buyerName: str
    buyerPhone: str
    lastMessagePreview: str
    lastMessageAt: str
    unread: bool
    flagged: bool
    agentName: str


class ConversationsData(BaseModel):
    conversations: list[ConversationListItem]
    total: int
    nextCursor: str | None


class ConversationsResponse(BaseModel):
    ok: bool = True
    data: ConversationsData


@router.get("")
async def list_conversations_route(
    tab: Tab = Query(default="all"),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> ConversationsResponse:
    try:
        items, total, next_cursor = await ConversationRepository(db).list_paginated(
            session.sme_id, tab, q, limit, cursor
        )
    except ValueError as exc:
        raise ApiError(400, "BAD_REQUEST", "Invalid cursor", field="cursor") from exc

    return ConversationsResponse(
        data=ConversationsData(
            conversations=[
                ConversationListItem(
                    id=item.id,
                    buyerName=item.buyer_name,
                    buyerPhone=mask_phone(item.buyer_phone),
                    lastMessagePreview=truncate_preview(item.last_message_preview or ""),
                    lastMessageAt=item.last_message_at.isoformat(),
                    unread=item.unread,
                    flagged=item.flagged,
                    agentName=item.agent_name,
                )
                for item in items
            ],
            total=total,
            nextCursor=next_cursor,
        )
    )


class ConversationBuyer(BaseModel):
    name: str
    phone: str
    firstSeenAt: str


class ConversationAgent(BaseModel):
    id: str
    nameUrdu: str


class ConversationMessage(BaseModel):
    id: str
    sender: str
    text: str
    textOriginal: str | None = None
    timestamp: str
    auditMessageId: str | None = None


class ConversationDetailData(BaseModel):
    id: str
    buyer: ConversationBuyer
    agent: ConversationAgent
    messages: list[ConversationMessage]


class ConversationDetailResponse(BaseModel):
    ok: bool = True
    data: ConversationDetailData


@router.get("/{conversation_id}")
async def get_conversation_route(
    conversation_id: str,
    before: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    convo_repo = ConversationRepository(db)
    detail = await convo_repo.get_detail(conversation_id, session.sme_id)
    if detail is None:
        raise ApiError(404, "NOT_FOUND", "Conversation not found")

    before_ts = None
    if before is not None:
        try:
            before_ts = datetime.fromisoformat(before)
        except ValueError as exc:
            raise ApiError(400, "BAD_REQUEST", "Invalid before timestamp", field="before") from exc

    messages = await MessageRepository(db).list_for_conversation(
        conversation_id, session.sme_id, before_ts, limit
    )
    await convo_repo.mark_read(conversation_id, session.sme_id)

    return ConversationDetailResponse(
        data=ConversationDetailData(
            id=detail.id,
            buyer=ConversationBuyer(
                name=detail.buyer_name,
                phone=mask_phone(detail.buyer_phone),
                firstSeenAt=detail.buyer_first_seen_at.isoformat(),
            ),
            agent=ConversationAgent(id=detail.agent_id, nameUrdu=detail.agent_name_urdu),
            messages=[
                ConversationMessage(
                    id=m.id,
                    sender=m.sender,
                    text=m.text,
                    textOriginal=m.text_original,
                    timestamp=m.timestamp_ts.isoformat(),
                    auditMessageId=m.id if m.sender == "agent" else None,
                )
                for m in messages
            ],
        )
    )


class FlagRequest(BaseModel):
    flagged: bool
    reason: str | None = Field(default=None, max_length=500)


class FlagData(BaseModel):
    id: str
    flagged: bool


class FlagResponse(BaseModel):
    ok: bool = True
    data: FlagData


@router.post("/{conversation_id}/flag")
async def flag_conversation_route(
    conversation_id: str,
    body: FlagRequest,
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    updated = await ConversationRepository(db).set_flag(
        conversation_id, session.sme_id, body.flagged, body.reason
    )
    if not updated:
        raise ApiError(404, "NOT_FOUND", "Conversation not found")
    return FlagResponse(data=FlagData(id=conversation_id, flagged=body.flagged))
