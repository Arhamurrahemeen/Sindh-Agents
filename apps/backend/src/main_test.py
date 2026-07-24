from httpx import ASGITransport, AsyncClient

from src.config import settings
from src.main import app


async def test_health_returns_200_with_request_id_header() -> None:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]  # httpx/Starlette ASGI type mismatch, not a bug
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert settings.REQUEST_ID_HEADER in response.headers
