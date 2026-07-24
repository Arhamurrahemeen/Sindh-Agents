from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.repositories.qdrant_registry_repository import QdrantRegistryRepository

# NOTE: unverified against a live Qdrant cluster — see embedding_service.py's
# note on credential provenance. Structurally correct per qdrant-client v1.18's
# async API surface as of this writing.

DIMENSION = 1024

_client: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return _client


def collection_name(sme_id: str) -> str:
    return f"sme_{sme_id}_memory"


async def ensure_collection(db: AsyncSession, sme_id: str) -> str:
    registry = QdrantRegistryRepository(db)
    name = collection_name(sme_id)
    if await registry.is_registered(sme_id):
        return name

    client = _get_client()
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=DIMENSION, distance=Distance.COSINE),
        )
    # found live: filtering by payload.buyer_id 400s without this — Qdrant
    # requires an explicit index on any field used in a query_filter. Runs
    # once per SME (gated by the registry check above, not collection_exists)
    # so it still applies to a collection that already existed without one.
    await client.create_payload_index(
        collection_name=name,
        field_name="buyer_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    await registry.register(sme_id, name, settings.COHERE_EMBEDDING_MODEL, DIMENSION)
    return name


async def upsert_note(
    db: AsyncSession, sme_id: str, point_id: str, buyer_id: str, note_text: str, vector: list[float]
) -> None:
    name = await ensure_collection(db, sme_id)
    await _get_client().upsert(
        collection_name=name,
        points=[
            PointStruct(
                id=point_id, vector=vector, payload={"buyer_id": buyer_id, "text": note_text}
            )
        ],
    )


async def query_buyer_notes(
    db: AsyncSession,
    sme_id: str,
    buyer_id: str,
    vector: list[float],
    top_k: int = 3,
    score_threshold: float = 0.7,
) -> list[str]:
    name = await ensure_collection(db, sme_id)
    results = await _get_client().query_points(
        collection_name=name,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="buyer_id", match=MatchValue(value=buyer_id))]
        ),
        limit=top_k,
        score_threshold=score_threshold,
    )
    return [str(point.payload.get("text", ""))[:200] for point in results.points if point.payload]
