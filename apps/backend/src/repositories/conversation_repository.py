import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7

Tab = Literal["all", "unread", "flagged"]


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


@dataclass
class ConversationListItem:
    id: str
    buyer_name: str
    buyer_phone: str | None
    last_message_preview: str | None
    last_message_at: datetime
    unread: bool
    flagged: bool
    agent_name: str


@dataclass
class ConversationDetail:
    id: str
    buyer_name: str
    buyer_phone: str | None
    buyer_first_seen_at: datetime
    agent_id: str
    agent_name_urdu: str
    channel: str


def _encode_cursor(last_message_at: datetime, conversation_id: str) -> str:
    raw = f"{last_message_at.isoformat()}|{conversation_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, conversation_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), conversation_id
    except (ValueError, UnicodeDecodeError):
        return None


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

    async def list_paginated(
        self, sme_id: str, tab: Tab, q: str | None, limit: int, cursor: str | None
    ) -> tuple[list[ConversationListItem], int, str | None]:
        base_conditions = ["c.sme_id = :sme_id"]
        params: dict[str, object] = {"sme_id": sme_id}

        if tab == "unread":
            base_conditions.append("c.is_unread = true")
        elif tab == "flagged":
            base_conditions.append("c.is_flagged = true")

        if q and len(q) >= 2:
            base_conditions.append(
                "(b.name ILIKE :q_pattern OR "
                "regexp_replace(coalesce(b.phone, ''), '[^0-9]', '', 'g') LIKE :q_digits)"
            )
            params["q_pattern"] = f"%{q}%"
            digits = "".join(ch for ch in q if ch.isdigit())
            params["q_digits"] = f"%{digits}%"

        base_where = " AND ".join(base_conditions)

        total_row = (
            await self.db.execute(
                text(
                    "SELECT count(*) AS n FROM conversations c "
                    f"JOIN buyers b ON b.id = c.buyer_id WHERE {base_where}"
                ),
                params,
            )
        ).first()
        total = int(total_row.n) if total_row is not None else 0

        list_conditions = list(base_conditions)
        list_params = dict(params)
        decoded_cursor = _decode_cursor(cursor) if cursor else None
        if cursor and decoded_cursor is None:
            raise ValueError("invalid cursor")
        if decoded_cursor is not None:
            cursor_ts, cursor_id = decoded_cursor
            list_conditions.append("(c.last_message_at, c.id) < (:cursor_ts, :cursor_id)")
            list_params["cursor_ts"] = cursor_ts
            list_params["cursor_id"] = cursor_id
        list_params["limit"] = limit + 1
        list_where = " AND ".join(list_conditions)

        rows = await self.db.execute(
            text(
                f"""
                SELECT c.id, b.name AS buyer_name, b.phone AS buyer_phone,
                       c.last_message_at, c.is_unread, c.is_flagged, a.name_urdu AS agent_name,
                       m.text AS last_message_text
                FROM conversations c
                JOIN buyers b ON b.id = c.buyer_id
                JOIN agents a ON a.id = c.agent_id
                LEFT JOIN LATERAL (
                    SELECT text FROM messages WHERE conversation_id = c.id
                    ORDER BY timestamp_ts DESC LIMIT 1
                ) m ON true
                WHERE {list_where}
                ORDER BY c.last_message_at DESC, c.id DESC
                LIMIT :limit
                """
            ),
            list_params,
        )
        all_rows = list(rows)
        has_more = len(all_rows) > limit
        page_rows = all_rows[:limit]

        items = [
            ConversationListItem(
                id=str(row.id),
                buyer_name=row.buyer_name,
                buyer_phone=row.buyer_phone,
                last_message_preview=row.last_message_text,
                last_message_at=row.last_message_at,
                unread=row.is_unread,
                flagged=row.is_flagged,
                agent_name=row.agent_name,
            )
            for row in page_rows
        ]

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(last.last_message_at, str(last.id))

        return items, total, next_cursor

    async def get_detail(self, conversation_id: str, sme_id: str) -> ConversationDetail | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT c.id, c.channel, b.name AS buyer_name, b.phone AS buyer_phone,
                           b.first_seen_at, a.id AS agent_id, a.name_urdu AS agent_name_urdu
                    FROM conversations c
                    JOIN buyers b ON b.id = c.buyer_id
                    JOIN agents a ON a.id = c.agent_id
                    WHERE c.id = :id AND c.sme_id = :sme_id
                    """
                ),
                {"id": conversation_id, "sme_id": sme_id},
            )
        ).first()
        if row is None:
            return None
        return ConversationDetail(
            id=str(row.id),
            buyer_name=row.buyer_name,
            buyer_phone=row.buyer_phone,
            buyer_first_seen_at=row.first_seen_at,
            agent_id=str(row.agent_id),
            agent_name_urdu=row.agent_name_urdu,
            channel=row.channel,
        )

    async def mark_read(self, conversation_id: str, sme_id: str) -> None:
        await self.db.execute(
            text("UPDATE conversations SET is_unread = false WHERE id = :id AND sme_id = :sme_id"),
            {"id": conversation_id, "sme_id": sme_id},
        )
        await self.db.commit()

    async def set_flag(
        self, conversation_id: str, sme_id: str, flagged: bool, reason: str | None
    ) -> bool:
        result = cast(
            "CursorResult[Any]",
            await self.db.execute(
                text(
                    "UPDATE conversations SET is_flagged = :flagged, flag_reason = :reason, "
                    "updated_at = now() WHERE id = :id AND sme_id = :sme_id"
                ),
                {"flagged": flagged, "reason": reason, "id": conversation_id, "sme_id": sme_id},
            ),
        )
        await self.db.commit()
        return result.rowcount > 0
