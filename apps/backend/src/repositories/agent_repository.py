from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Agent:
    id: str
    name: str
    name_urdu: str
    status: str


class AgentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_sme(self, sme_id: str) -> list[Agent]:
        rows = await self.db.execute(
            text(
                "SELECT id, name, name_urdu, status FROM agents "
                "WHERE sme_id = :sme_id ORDER BY created_at ASC"
            ),
            {"sme_id": sme_id},
        )
        return [
            Agent(id=str(row.id), name=row.name, name_urdu=row.name_urdu, status=row.status)
            for row in rows
        ]
