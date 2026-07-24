from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class Buyer:
    id: str
    sme_id: str
    name: str
    wa_id: str


class BuyerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_existing(self, sme_id: str, wa_id: str) -> Buyer | None:
        row = (
            await self.db.execute(
                text("SELECT id, name FROM buyers WHERE sme_id = :sme_id AND wa_id = :wa_id"),
                {"sme_id": sme_id, "wa_id": wa_id},
            )
        ).first()
        if row is None:
            return None
        return Buyer(id=str(row.id), sme_id=sme_id, name=row.name, wa_id=wa_id)

    async def get_or_create(self, sme_id: str, wa_id: str, name: str) -> Buyer:
        row = (
            await self.db.execute(
                text(
                    "UPDATE buyers SET last_seen_at = now() "
                    "WHERE sme_id = :sme_id AND wa_id = :wa_id "
                    "RETURNING id, name"
                ),
                {"sme_id": sme_id, "wa_id": wa_id},
            )
        ).first()
        if row is not None:
            return Buyer(id=str(row.id), sme_id=sme_id, name=row.name, wa_id=wa_id)

        buyer_id = str(uuid7())
        await self.db.execute(
            text(
                "INSERT INTO buyers (id, sme_id, name, wa_id) "
                "VALUES (:id, :sme_id, :name, :wa_id)"
            ),
            {"id": buyer_id, "sme_id": sme_id, "name": name, "wa_id": wa_id},
        )
        return Buyer(id=buyer_id, sme_id=sme_id, name=name, wa_id=wa_id)
