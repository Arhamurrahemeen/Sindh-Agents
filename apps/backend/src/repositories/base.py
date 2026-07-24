from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ScopedQuery:
    def __init__(self, db: AsyncSession, sme_id: str) -> None:
        self.db = db
        self.sme_id = sme_id

    async def set_rls_context(self) -> None:
        # db_schema.md §0.3 — RLS defense-in-depth reads this on every scoped query.
        await self.db.execute(
            text("SELECT set_config('app.current_sme_id', :sme_id, true)"),
            {"sme_id": self.sme_id},
        )


class BaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def scoped(self, sme_id: str) -> ScopedQuery:
        return ScopedQuery(self.db, sme_id)
