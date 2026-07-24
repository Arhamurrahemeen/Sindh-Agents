from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class Session:
    id: str
    sme_id: str
    expires_at: datetime


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        sme_id: str,
        cookie_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> Session:
        session_id = str(uuid7())
        await self.db.execute(
            text(
                "INSERT INTO sessions (id, sme_id, cookie_hash, expires_at, user_agent, ip_address) "
                "VALUES (:id, :sme_id, :cookie_hash, :expires_at, :user_agent, :ip_address)"
            ),
            {
                "id": session_id,
                "sme_id": sme_id,
                "cookie_hash": cookie_hash,
                "expires_at": expires_at,
                "user_agent": user_agent,
                "ip_address": ip_address,
            },
        )
        return Session(id=session_id, sme_id=sme_id, expires_at=expires_at)

    async def get_by_cookie_hash(self, cookie_hash: str) -> Session | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT id, sme_id, expires_at FROM sessions "
                    "WHERE cookie_hash = :cookie_hash AND expires_at > now()"
                ),
                {"cookie_hash": cookie_hash},
            )
        ).first()
        if row is None:
            return None
        return Session(id=str(row.id), sme_id=str(row.sme_id), expires_at=row.expires_at)

    async def delete_by_cookie_hash(self, cookie_hash: str) -> None:
        await self.db.execute(
            text("DELETE FROM sessions WHERE cookie_hash = :cookie_hash"),
            {"cookie_hash": cookie_hash},
        )
