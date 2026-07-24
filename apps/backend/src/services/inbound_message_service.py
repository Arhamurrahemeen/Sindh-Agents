from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.errors import ApiError
from src.repositories.agent_repository import AgentRepository
from src.repositories.buyer_repository import Buyer, BuyerRepository
from src.repositories.conversation_repository import Conversation, ConversationRepository
from src.repositories.message_repository import MessageRepository
from src.repositories.sme_repository import Sme, SmeRepository
from src.services import idempotency
from src.workers import agent_worker

# MVP: single pilot SME per widget instance (api-contract.md §3.1) — the real
# phone_number_id -> sme_id lookup table is Phase 2. Must match seeds/pilot_sme.py.
PILOT_SME_PHONE = "+923005551234"


@dataclass
class InboundResult:
    message_id: str


async def resolve_pilot_sme(db: AsyncSession) -> Sme:
    sme = await SmeRepository(db).get_by_phone(PILOT_SME_PHONE)
    if sme is None:
        raise ApiError(
            400, "BAD_REQUEST", "No pilot SME enrolled", field="metadata.phone_number_id"
        )
    return sme


async def resolve_pilot_agent_id(db: AsyncSession, sme_id: str) -> str:
    agents = await AgentRepository(db).list_for_sme(sme_id)
    if not agents:
        raise ApiError(500, "SERVER_ERROR", "No agent provisioned for this SME")
    return agents[0].id


async def resolve_conversation(db: AsyncSession, wa_id: str) -> tuple[Buyer, Conversation] | None:
    """For the outbound poll: only resolves conversations that already exist."""
    sme = await resolve_pilot_sme(db)
    buyer = await BuyerRepository(db).get_existing(sme.id, wa_id)
    if buyer is None:
        return None
    agent_id = await resolve_pilot_agent_id(db, sme.id)
    conversation = await ConversationRepository(db).get_or_create(sme.id, buyer.id, agent_id)
    return buyer, conversation


async def ingest_inbound_message(
    db: AsyncSession,
    *,
    idempotency_key: str | None,
    wa_id: str,
    buyer_name: str,
    channel: str,
    text_body: str,
    timestamp_unix: str,
) -> InboundResult:
    if idempotency_key is not None:
        cached = idempotency.get_cached(idempotency_key)
        if cached is not None:
            return InboundResult(message_id=cached)

    sme = await resolve_pilot_sme(db)
    agent_id = await resolve_pilot_agent_id(db, sme.id)
    buyer = await BuyerRepository(db).get_or_create(sme.id, wa_id, buyer_name)
    conversation = await ConversationRepository(db).get_or_create(
        sme.id, buyer.id, agent_id, channel
    )

    timestamp_ts = datetime.fromtimestamp(int(timestamp_unix), tz=UTC)
    message = await MessageRepository(db).insert_buyer_message(
        sme.id, conversation.id, text_body, timestamp_ts
    )
    await ConversationRepository(db).mark_unread_on_inbound(conversation.id)
    await db.commit()

    if idempotency_key is not None:
        idempotency.store(idempotency_key, message.id)

    agent_worker.enqueue(
        sme.id, agent_id, conversation.id, buyer.id, conversation.channel, message.id, text_body
    )

    return InboundResult(message_id=message.id)
