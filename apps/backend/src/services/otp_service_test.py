from datetime import UTC, datetime, timedelta

import pytest

from src.errors import ApiError
from src.repositories.otp_repository import OtpChallenge
from src.services import otp_service


class FakeOtpRepository:
    def __init__(self) -> None:
        self.challenges: dict[str, OtpChallenge] = {}
        self._next_id = 0

    async def create(self, phone: str, otp_hash: str, expires_at: datetime) -> OtpChallenge:
        self._next_id += 1
        challenge = OtpChallenge(
            id=str(self._next_id),
            phone=phone,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
            consumed_at=None,
            created_at=datetime.now(UTC),
        )
        self.challenges[challenge.id] = challenge
        return challenge

    async def get_active_by_phone(self, phone: str) -> OtpChallenge | None:
        now = datetime.now(UTC)
        candidates = [
            c
            for c in self.challenges.values()
            if c.phone == phone and c.consumed_at is None and c.expires_at > now
        ]
        return max(candidates, key=lambda c: c.created_at) if candidates else None

    async def count_recent(self, phone: str, since: datetime) -> int:
        return sum(1 for c in self.challenges.values() if c.phone == phone and c.created_at > since)

    async def increment_attempts(self, challenge_id: str) -> int:
        challenge = self.challenges[challenge_id]
        challenge.attempts += 1
        return challenge.attempts

    async def consume(self, challenge_id: str) -> None:
        self.challenges[challenge_id].consumed_at = datetime.now(UTC)


PHONE = "+923005551234"


async def test_send_otp_creates_a_challenge() -> None:
    repo = FakeOtpRepository()
    expires_in, resend_in = await otp_service.send_otp(repo, PHONE)
    assert expires_in == 300
    assert resend_in == 60
    assert len(repo.challenges) == 1


async def test_send_otp_returns_cached_expiry_within_cooldown() -> None:
    repo = FakeOtpRepository()
    await otp_service.send_otp(repo, PHONE)
    expires_in, resend_in = await otp_service.send_otp(repo, PHONE)
    assert len(repo.challenges) == 1  # no second challenge created
    assert resend_in <= 60


async def test_send_otp_rate_limited_after_three_in_an_hour() -> None:
    repo = FakeOtpRepository()
    now = datetime.now(UTC)
    for i in range(3):
        repo.challenges[str(i)] = OtpChallenge(
            id=str(i),
            phone=PHONE,
            otp_hash="x",
            expires_at=now - timedelta(minutes=1),  # already expired, so cooldown doesn't apply
            attempts=0,
            consumed_at=None,
            created_at=now - timedelta(minutes=10),
        )
    with pytest.raises(ApiError) as exc_info:
        await otp_service.send_otp(repo, PHONE)
    assert exc_info.value.code == "RATE_LIMITED"


async def test_verify_otp_wrong_code_increments_attempts_and_raises() -> None:
    repo = FakeOtpRepository()
    challenge = await repo.create(
        PHONE, otp_service.hash_otp("111111"), datetime.now(UTC) + timedelta(minutes=5)
    )
    with pytest.raises(ApiError) as exc_info:
        await otp_service.verify_otp(repo, PHONE, "000000")
    assert exc_info.value.code == "OTP_INVALID"
    assert repo.challenges[challenge.id].attempts == 1


async def test_verify_otp_correct_code_consumes_challenge() -> None:
    repo = FakeOtpRepository()
    challenge = await repo.create(
        PHONE, otp_service.hash_otp("111111"), datetime.now(UTC) + timedelta(minutes=5)
    )
    await otp_service.verify_otp(repo, PHONE, "111111")
    assert repo.challenges[challenge.id].consumed_at is not None


async def test_verify_otp_locks_out_after_max_attempts() -> None:
    repo = FakeOtpRepository()
    challenge = await repo.create(
        PHONE, otp_service.hash_otp("111111"), datetime.now(UTC) + timedelta(minutes=5)
    )
    repo.challenges[challenge.id].attempts = 5  # OTP_MAX_ATTEMPTS
    with pytest.raises(ApiError) as exc_info:
        await otp_service.verify_otp(repo, PHONE, "111111")
    assert exc_info.value.code == "RATE_LIMITED"


async def test_verify_otp_expired_raises() -> None:
    repo = FakeOtpRepository()
    with pytest.raises(ApiError) as exc_info:
        await otp_service.verify_otp(repo, PHONE, "111111")
    assert exc_info.value.code == "OTP_EXPIRED"
