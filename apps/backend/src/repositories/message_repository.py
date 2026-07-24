from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class Message:
    id: str
    conversation_id: str
    sender: str
    text: str
    timestamp_ts: datetime
    is_pending: bool


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def insert_buyer_message(
        self, sme_id: str, conversation_id: str, text_body: str, timestamp_ts: datetime
    ) -> Message:
        message_id = str(uuid7())
        await self.db.execute(
            text(
                "INSERT INTO messages (id, sme_id, conversation_id, sender, text, "
                "timestamp_ts, is_pending) "
                "VALUES (:id, :sme_id, :conversation_id, 'buyer', :text, :timestamp_ts, true)"
            ),
            {
                "id": message_id,
                "sme_id": sme_id,
                "conversation_id": conversation_id,
                "text": text_body,
                "timestamp_ts": timestamp_ts,
            },
        )
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            sender="buyer",
            text=text_body,
            timestamp_ts=timestamp_ts,
            is_pending=True,
        )

    async def list_after(self, conversation_id: str, after_id: str | None) -> list[Message]:
        if after_id is None:
            rows = await self.db.execute(
                text(
                    "SELECT id, conversation_id, sender, text, timestamp_ts, is_pending "
                    "FROM messages WHERE conversation_id = :conversation_id "
                    "ORDER BY id ASC LIMIT 20"
                ),
                {"conversation_id": conversation_id},
            )
        else:
            rows = await self.db.execute(
                text(
                    "SELECT id, conversation_id, sender, text, timestamp_ts, is_pending "
                    "FROM messages WHERE conversation_id = :conversation_id AND id > :after_id "
                    "ORDER BY id ASC"
                ),
                {"conversation_id": conversation_id, "after_id": after_id},
            )
        return [
            Message(
                id=str(row.id),
                conversation_id=str(row.conversation_id),
                sender=row.sender,
                text=row.text,
                timestamp_ts=row.timestamp_ts,
                is_pending=row.is_pending,
            )
            for row in rows
        ]

    async def count_today_for_agent(self, sme_id: str, agent_id: str) -> int:
        row = (
            await self.db.execute(
                text(
                    "SELECT count(*) AS n FROM messages msg "
                    "JOIN conversations c ON c.id = msg.conversation_id "
                    "WHERE msg.sme_id = :sme_id AND c.agent_id = :agent_id "
                    "AND msg.sender = 'buyer' "
                    "AND msg.timestamp_ts >= date_trunc('day', now() AT TIME ZONE 'Asia/Karachi')"
                ),
                {"sme_id": sme_id, "agent_id": agent_id},
            )
        ).first()
        return int(row.n) if row is not None else 0

    async def last_active_for_agent(self, sme_id: str, agent_id: str) -> datetime | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT max(msg.timestamp_ts) AS last_active FROM messages msg "
                    "JOIN conversations c ON c.id = msg.conversation_id "
                    "WHERE msg.sme_id = :sme_id AND c.agent_id = :agent_id"
                ),
                {"sme_id": sme_id, "agent_id": agent_id},
            )
        ).first()
        return row.last_active if row is not None else None
