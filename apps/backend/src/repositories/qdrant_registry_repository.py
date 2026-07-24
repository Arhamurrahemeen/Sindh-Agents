from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class QdrantRegistryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def is_registered(self, sme_id: str) -> bool:
        row = (
            await self.db.execute(
                text("SELECT 1 FROM qdrant_collection_registry WHERE sme_id = :sme_id"),
                {"sme_id": sme_id},
            )
        ).first()
        return row is not None

    async def register(
        self, sme_id: str, collection_name: str, embedding_model: str, dimension: int
    ) -> None:
        await self.db.execute(
            text(
                "INSERT INTO qdrant_collection_registry "
                "(sme_id, collection_name, embedding_model, dimension) "
                "VALUES (:sme_id, :collection_name, :embedding_model, :dimension) "
                "ON CONFLICT (sme_id) DO NOTHING"
            ),
            {
                "sme_id": sme_id,
                "collection_name": collection_name,
                "embedding_model": embedding_model,
                "dimension": dimension,
            },
        )
        await self.db.commit()
