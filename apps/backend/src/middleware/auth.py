import hashlib
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.errors import ApiError
from src.repositories.session_repository import SessionRepository

SESSION_COOKIE_NAME = "sa_session"


@dataclass
class AuthSession:
    sme_id: str
    session_id: str


def hash_cookie(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def require_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthSession:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise ApiError(401, "AUTH_REQUIRED", "No session cookie")

    session = await SessionRepository(db).get_by_cookie_hash(hash_cookie(token))
    if session is None:
        raise ApiError(401, "AUTH_REQUIRED", "Invalid or expired session")

    return AuthSession(sme_id=session.sme_id, session_id=session.id)
