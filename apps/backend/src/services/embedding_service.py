import cohere

from src.config import settings

# NOTE: unverified against a live Cohere account — credentials in .env are of
# unconfirmed provenance (see phase/P0.md known gaps). Structurally correct
# per the Cohere Python SDK v7 async client surface as of this writing.

_client: cohere.AsyncClient | None = None


def _get_client() -> cohere.AsyncClient:
    global _client
    if _client is None:
        _client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
    return _client


def _first_embedding(embeddings: object) -> list[float]:
    # embeddings is a plain list[list[float]] whenever embedding_types isn't
    # passed (we never pass it) — the SDK's type still unions in the
    # structured EmbedByTypeResponseEmbeddings shape used by that other path.
    if not isinstance(embeddings, list):
        raise TypeError(f"expected list of embeddings, got {type(embeddings)}")
    return list(embeddings[0])


async def embed_query(text: str) -> list[float]:
    response = await _get_client().embed(
        texts=[text],
        model=settings.COHERE_EMBEDDING_MODEL,
        input_type=settings.COHERE_INPUT_TYPE_QUERY,
    )
    return _first_embedding(response.embeddings)


async def embed_document(text: str) -> list[float]:
    response = await _get_client().embed(
        texts=[text],
        model=settings.COHERE_EMBEDDING_MODEL,
        input_type=settings.COHERE_INPUT_TYPE_INGEST,
    )
    return _first_embedding(response.embeddings)
