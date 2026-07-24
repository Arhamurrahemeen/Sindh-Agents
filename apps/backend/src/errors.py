from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        message_urdu: str | None = None,
        field: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.message_urdu = message_urdu
        self.field = field


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    body: dict[str, object] = {
        "code": exc.code,
        "message": exc.message,
        "requestId": getattr(request.state, "request_id", ""),
    }
    if exc.message_urdu is not None:
        body["messageUrdu"] = exc.message_urdu
    if exc.field is not None:
        body["field"] = exc.field
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": body})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(part) for part in first.get("loc", ()) if part != "body") or None
    return await api_error_handler(
        request,
        ApiError(400, "BAD_REQUEST", str(first.get("msg", "Invalid request")), field=field),
    )
