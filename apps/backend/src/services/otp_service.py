import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from src.config import settings
from src.errors import ApiError
from src.repositories.otp_repository import OtpChallenge
from src.services.sms_service import send_otp_sms


class OtpRepositoryProtocol(Protocol):
    # matches repositories.otp_repository.OtpRepository — a Protocol here (rather than
    # importing the concrete class) lets tests substitute an in-memory fake for Neon
    # per CLAUDE.md §8 ("mock only external services... Neon in unit tests").
    async def create(self, phone: str, otp_hash: str, expires_at: datetime) -> OtpChallenge: ...
    async def get_active_by_phone(self, phone: str) -> OtpChallenge | None: ...
    async def count_recent(self, phone: str, since: datetime) -> int: ...
    async def increment_attempts(self, challenge_id: str) -> int: ...
    async def consume(self, challenge_id: str) -> None: ...


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_otp(repo: OtpRepositoryProtocol, phone: str) -> tuple[int, int]:
    now = datetime.now(UTC)

    active = await repo.get_active_by_phone(phone)
    if active is not None:
        age_seconds = (now - active.created_at).total_seconds()
        if age_seconds < settings.OTP_RESEND_COOLDOWN_SECONDS:
            expires_in = int((active.expires_at - now).total_seconds())
            resend_in = settings.OTP_RESEND_COOLDOWN_SECONDS - int(age_seconds)
            return expires_in, resend_in

    recent_count = await repo.count_recent(phone, now - timedelta(hours=1))
    if recent_count >= settings.RATE_LIMIT_OTP_PER_HOUR:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many OTP requests for this phone",
            "Ek minute rukein, phir try karein.",
        )

    otp = generate_otp()
    expires_at = now + timedelta(seconds=settings.OTP_TTL_SECONDS)
    await repo.create(phone, hash_otp(otp), expires_at)
    await send_otp_sms(phone, otp, settings.OTP_TTL_SECONDS)

    return settings.OTP_TTL_SECONDS, settings.OTP_RESEND_COOLDOWN_SECONDS


async def verify_otp(repo: OtpRepositoryProtocol, phone: str, otp: str) -> None:
    if settings.DEV_SKIP_OTP_VERIFY and otp == "123456":
        return

    active = await repo.get_active_by_phone(phone)
    if active is None:
        raise ApiError(
            401, "OTP_EXPIRED", "OTP has expired or was never sent", "OTP expire ho gaya hai."
        )

    if active.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many failed OTP attempts",
            "Bohat dafa ghalat OTP daala. Thori dair baad try karein.",
        )

    if hash_otp(otp) != active.otp_hash:
        await repo.increment_attempts(active.id)
        raise ApiError(401, "OTP_INVALID", "Incorrect OTP", "OTP galat hai. Dobara try karein.")

    await repo.consume(active.id)
