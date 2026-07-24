import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.errors import ApiError
from src.middleware.auth import SESSION_COOKIE_NAME, AuthSession, hash_cookie, require_session
from src.repositories.otp_repository import OtpRepository
from src.repositories.session_repository import SessionRepository
from src.repositories.sme_repository import SmeRepository
from src.services import otp_service
from src.services.phone import mask_phone

router = APIRouter()

PHONE_PATTERN = r"^\+923[0-9]{9}$"
OTP_PATTERN = r"^[0-9]{6}$"


class SendOtpRequest(BaseModel):
    phone: str = Field(pattern=PHONE_PATTERN)


class SendOtpData(BaseModel):
    expiresInSeconds: int
    resendAvailableInSeconds: int


class SendOtpResponse(BaseModel):
    ok: bool = True
    data: SendOtpData


class VerifyOtpRequest(BaseModel):
    phone: str = Field(pattern=PHONE_PATTERN)
    otp: str = Field(pattern=OTP_PATTERN)


class VerifyOtpData(BaseModel):
    smeId: str
    smeName: str
    ownerName: str


class VerifyOtpResponse(BaseModel):
    ok: bool = True
    data: VerifyOtpData


class LogoutResponse(BaseModel):
    ok: bool = True


class MeData(BaseModel):
    smeId: str
    smeName: str
    ownerName: str
    phone: str


class MeResponse(BaseModel):
    ok: bool = True
    data: MeData


@router.post("/send-otp")
async def send_otp_route(
    body: SendOtpRequest, db: AsyncSession = Depends(get_db)
) -> SendOtpResponse:
    expires_in, resend_in = await otp_service.send_otp(OtpRepository(db), body.phone)
    await db.commit()
    return SendOtpResponse(
        data=SendOtpData(expiresInSeconds=expires_in, resendAvailableInSeconds=resend_in)
    )


@router.post("/verify-otp")
async def verify_otp_route(
    body: VerifyOtpRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> VerifyOtpResponse:
    sme = await SmeRepository(db).get_by_phone(body.phone)
    if sme is None:
        raise ApiError(404, "SME_NOT_ENROLLED", "Phone is not registered to any pilot SME")

    await otp_service.verify_otp(OtpRepository(db), body.phone, body.otp)

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=settings.SESSION_MAX_AGE_HOURS)
    await SessionRepository(db).create(
        sme_id=sme.id,
        cookie_hash=hash_cookie(token),
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.NODE_ENV != "development",
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE_HOURS * 3600,
    )
    return VerifyOtpResponse(
        data=VerifyOtpData(smeId=sme.id, smeName=sme.name, ownerName=sme.owner_name)
    )


@router.post("/logout")
async def logout_route(
    request: Request,
    response: Response,
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        await SessionRepository(db).delete_by_cookie_hash(hash_cookie(token))
        await db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)
    return LogoutResponse()


@router.get("/me")
async def me_route(
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    sme = await SmeRepository(db).get_by_id(session.sme_id)
    if sme is None:
        raise ApiError(401, "AUTH_REQUIRED", "Session refers to a deleted SME")
    return MeResponse(
        data=MeData(
            smeId=sme.id,
            smeName=sme.name,
            ownerName=sme.owner_name,
            phone=mask_phone(sme.owner_phone),
        )
    )
