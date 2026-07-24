from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Sme:
    id: str
    name: str
    owner_name: str
    owner_phone: str


class SmeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_phone(self, owner_phone: str) -> Sme | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT id, name, owner_name, owner_phone FROM smes WHERE owner_phone = :phone"
                ),
                {"phone": owner_phone},
            )
        ).first()
        if row is None:
            return None
        return Sme(
            id=str(row.id), name=row.name, owner_name=row.owner_name, owner_phone=row.owner_phone
        )

    async def get_by_id(self, sme_id: str) -> Sme | None:
        row = (
            await self.db.execute(
                text("SELECT id, name, owner_name, owner_phone FROM smes WHERE id = :id"),
                {"id": sme_id},
            )
        ).first()
        if row is None:
            return None
        return Sme(
            id=str(row.id), name=row.name, owner_name=row.owner_name, owner_phone=row.owner_phone
        )
