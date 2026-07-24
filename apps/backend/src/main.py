import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.agents import router as agents_router
from src.api.auth import router as auth_router
from src.api.widget import router as widget_router
from src.config import settings
from src.errors import ApiError, api_error_handler, validation_error_handler
from src.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.DEV_AUTO_SEED:
        from seeds.pilot_sme import run as seed_pilot_sme

        await seed_pilot_sme()
    yield


app = FastAPI(title="Sindh Agents Backend", lifespan=lifespan)

app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

app.include_router(auth_router, prefix="/api/auth")
app.include_router(widget_router, prefix="/api/widget")
app.include_router(agents_router, prefix="/api/agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.widget_allowed_origins_list,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(settings.REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[settings.REQUEST_ID_HEADER] = request_id
        return response


app.add_middleware(RequestIdMiddleware)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
