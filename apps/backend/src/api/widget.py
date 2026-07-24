import asyncio
import time
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.errors import ApiError
from src.repositories.message_repository import MessageRepository
from src.services import inbound_message_service, rate_limit

router = APIRouter()


class WidgetMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class ContactProfile(BaseModel):
    name: str


class Contact(BaseModel):
    profile: ContactProfile
    wa_id: str


class MessageText(BaseModel):
    body: str = Field(min_length=1, max_length=4096)


class InboundMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    text: MessageText
    type: Literal["text"]


class WidgetInboundRequest(BaseModel):
    messaging_product: Literal["widget", "whatsapp"]
    metadata: WidgetMetadata
    contacts: list[Contact]
    messages: list[InboundMessage]


class WidgetInboundData(BaseModel):
    accepted: Literal[True] = True
    messageId: str


class WidgetInboundResponse(BaseModel):
    ok: bool = True
    data: WidgetInboundData


@router.post("/inbound")
async def widget_inbound_route(
    body: WidgetInboundRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
) -> WidgetInboundResponse:
    if body.messaging_product == "whatsapp" and not settings.FEATURE_WHATSAPP:
        raise ApiError(
            400, "BAD_REQUEST", "whatsapp channel is disabled", field="messaging_product"
        )

    if len(body.contacts) != 1:
        raise ApiError(400, "BAD_REQUEST", "contacts must have exactly 1 entry", field="contacts")
    if len(body.messages) != 1:
        raise ApiError(400, "BAD_REQUEST", "messages must have exactly 1 entry", field="messages")

    contact = body.contacts[0]
    message = body.messages[0]
    if message.from_ != contact.wa_id:
        raise ApiError(
            400,
            "BAD_REQUEST",
            "messages[0].from must equal contacts[0].wa_id",
            field="messages[0].from",
        )
    if not message.text.body.strip():
        raise ApiError(
            400, "BAD_REQUEST", "text.body must be non-empty", field="messages[0].text.body"
        )

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"widget-inbound:{contact.wa_id}:{client_ip}"
    if not rate_limit.is_allowed(rate_key, settings.RATE_LIMIT_WIDGET_INBOUND_PER_MIN):
        raise ApiError(429, "RATE_LIMITED", "Too many messages, slow down")

    result = await inbound_message_service.ingest_inbound_message(
        db,
        idempotency_key=idempotency_key,
        wa_id=contact.wa_id,
        buyer_name=contact.profile.name,
        channel=body.messaging_product,
        text_body=message.text.body,
        timestamp_unix=message.timestamp,
    )

    return WidgetInboundResponse(data=WidgetInboundData(messageId=result.message_id))


class OutboundMessage(BaseModel):
    id: str
    timestamp: str
    text: MessageText


class WidgetOutboundResponse(BaseModel):
    messages: list[OutboundMessage]
    hasMore: bool = False


@router.get("/outbound")
async def widget_outbound_route(
    wa_id: str = Query(...),
    after: str | None = Query(default=None),
    wait: int = Query(default=25, le=25, ge=0),
    db: AsyncSession = Depends(get_db),
) -> WidgetOutboundResponse:
    if not rate_limit.is_allowed(
        f"widget-outbound:{wa_id}", settings.RATE_LIMIT_WIDGET_OUTBOUND_PER_MIN
    ):
        raise ApiError(429, "RATE_LIMITED", "Polling too fast")

    resolved = await inbound_message_service.resolve_conversation(db, wa_id)
    if resolved is None:
        await db.rollback()
        return WidgetOutboundResponse(messages=[], hasMore=False)
    _buyer, conversation = resolved

    deadline = time.monotonic() + wait
    while True:
        messages = await MessageRepository(db).list_after(conversation.id, after)
        agent_messages = [m for m in messages if m.sender == "agent"]
        if agent_messages:
            return WidgetOutboundResponse(
                messages=[
                    OutboundMessage(
                        id=m.id,
                        timestamp=str(int(m.timestamp_ts.timestamp())),
                        text=MessageText(body=m.text),
                    )
                    for m in agent_messages
                ],
                hasMore=False,
            )
        await db.rollback()
        if time.monotonic() >= deadline:
            return WidgetOutboundResponse(messages=[], hasMore=False)
        await asyncio.sleep(0.5)
