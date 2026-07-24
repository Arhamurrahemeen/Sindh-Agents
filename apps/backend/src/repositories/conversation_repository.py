from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class Conversation:
    id: str
    sme_id: str
    agent_id: str
    buyer_id: str
    channel: str


@dataclass
class RecentConversation:
    id: str
    buyer_name: str
    last_message_preview: str | None
    last_message_at: datetime
    unread: bool


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(
        self, sme_id: str, buyer_id: str, agent_id: str, channel: str = "widget"
    ) -> Conversation:
        row = (
            await self.db.execute(
                text(
                    "SELECT id FROM conversations "
                    "WHERE sme_id = :sme_id AND buyer_id = :buyer_id AND agent_id = :agent_id"
                ),
                {"sme_id": sme_id, "buyer_id": buyer_id, "agent_id": agent_id},
            )
        ).first()
        if row is not None:
            return Conversation(
                id=str(row.id), sme_id=sme_id, agent_id=agent_id, buyer_id=buyer_id, channel=channel
            )

        conversation_id = str(uuid7())
        await self.db.execute(
            text(
                "INSERT INTO conversations (id, sme_id, agent_id, buyer_id, channel) "
                "VALUES (:id, :sme_id, :agent_id, :buyer_id, :channel)"
            ),
            {
                "id": conversation_id,
                "sme_id": sme_id,
                "agent_id": agent_id,
                "buyer_id": buyer_id,
                "channel": channel,
            },
        )
        return Conversation(
            id=conversation_id, sme_id=sme_id, agent_id=agent_id, buyer_id=buyer_id, channel=channel
        )

    async def mark_unread_on_inbound(self, conversation_id: str) -> None:
        await self.db.execute(
            text(
                "UPDATE conversations SET last_message_at = now(), is_unread = true, "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": conversation_id},
        )

    async def list_recent(self, sme_id: str, limit: int = 5) -> list[RecentConversation]:
        rows = await self.db.execute(
            text(
                """
                SELECT c.id, b.name AS buyer_name, c.last_message_at, c.is_unread,
                       m.text AS last_message_text
                FROM conversations c
                JOIN buyers b ON b.id = c.buyer_id
                LEFT JOIN LATERAL (
                    SELECT text FROM messages
                    WHERE conversation_id = c.id
                    ORDER BY timestamp_ts DESC LIMIT 1
                ) m ON true
                WHERE c.sme_id = :sme_id
                ORDER BY c.last_message_at DESC
                LIMIT :limit
                """
            ),
            {"sme_id": sme_id, "limit": limit},
        )
        return [
            RecentConversation(
                id=str(row.id),
                buyer_name=row.buyer_name,
                last_message_preview=row.last_message_text,
                last_message_at=row.last_message_at,
                unread=row.is_unread,
            )
            for row in rows
        ]
