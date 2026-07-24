import asyncio
import logging

from src.agents.orchestrator import process_buyer_message
from src.db import async_session
from src.repositories.message_repository import MessageRepository
from src.services.groq_client import GroqChatCompleter

logger = logging.getLogger(__name__)


async def _run(
    sme_id: str,
    agent_id: str,
    conversation_id: str,
    buyer_id: str,
    conversation_channel: str,
    buyer_message_id: str,
    buyer_message_text: str,
) -> None:
    async with async_session() as db:
        prior_messages = await MessageRepository(db).list_after(conversation_id, None)
        history = [
            {"role": "user" if m.sender == "buyer" else "assistant", "content": m.text}
            for m in prior_messages
            if m.id != buyer_message_id
        ]

        completer = GroqChatCompleter()
        try:
            await process_buyer_message(
                db=db,
                completer=completer,
                sme_id=sme_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                buyer_id=buyer_id,
                conversation_channel=conversation_channel,
                buyer_message_id=buyer_message_id,
                buyer_message_text=buyer_message_text,
                conversation_history=history,
                logger=logger,
            )
        except Exception:
            # MVP_v1.md P3 §Done-means — "When Groq is down, messages.is_pending=true
            # persists; agent retries on next Groq call." This is that boundary: the
            # buyer message row already has is_pending=true from insert, so a failure
            # here just leaves it pending rather than crashing the process. There is
            # no automatic retry scheduler yet (see phase/P3.md known gaps) — the next
            # actual retry is whenever this conversation gets a new inbound message.
            logger.exception(
                "agent_processing_failed conversation_id=%s message_id=%s",
                conversation_id,
                buyer_message_id,
            )


def enqueue(
    sme_id: str,
    agent_id: str,
    conversation_id: str,
    buyer_id: str,
    conversation_channel: str,
    buyer_message_id: str,
    buyer_message_text: str,
) -> None:
    # MVP: in-process asyncio task, no external queue — Phase 1 per MVP_v1.md P3.
    asyncio.create_task(
        _run(
            sme_id,
            agent_id,
            conversation_id,
            buyer_id,
            conversation_channel,
            buyer_message_id,
            buyer_message_text,
        )
    )
