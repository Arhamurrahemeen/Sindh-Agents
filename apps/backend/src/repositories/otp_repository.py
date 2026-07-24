from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class OtpChallenge:
    id: str
    phone: str
    otp_hash: str
    expires_at: datetime
    attempts: int
    consumed_at: datetime | None
    created_at: datetime


class OtpRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, phone: str, otp_hash: str, expires_at: datetime) -> OtpChallenge:
        challenge_id = str(uuid7())
        row = (
            await self.db.execute(
                text(
                    "INSERT INTO otp_challenges (id, phone, otp_hash, expires_at) "
                    "VALUES (:id, :phone, :otp_hash, :expires_at) RETURNING created_at"
                ),
                {
                    "id": challenge_id,
                    "phone": phone,
                    "otp_hash": otp_hash,
                    "expires_at": expires_at,
                },
            )
        ).first()
        assert row is not None
        return OtpChallenge(
            id=challenge_id,
            phone=phone,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
            consumed_at=None,
            created_at=row.created_at,
        )

    async def get_active_by_phone(self, phone: str) -> OtpChallenge | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT id, phone, otp_hash, expires_at, attempts, consumed_at, created_at "
                    "FROM otp_challenges "
                    "WHERE phone = :phone AND consumed_at IS NULL AND expires_at > now() "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"phone": phone},
            )
        ).first()
        if row is None:
            return None
        return OtpChallenge(
            id=str(row.id),
            phone=row.phone,
            otp_hash=row.otp_hash,
            expires_at=row.expires_at,
            attempts=row.attempts,
            consumed_at=row.consumed_at,
            created_at=row.created_at,
        )

    async def count_recent(self, phone: str, since: datetime) -> int:
        row = (
            await self.db.execute(
                text(
                    "SELECT count(*) AS n FROM otp_challenges "
                    "WHERE phone = :phone AND created_at > :since"
                ),
                {"phone": phone, "since": since},
            )
        ).first()
        return int(row.n) if row is not None else 0

    async def increment_attempts(self, challenge_id: str) -> int:
        row = (
            await self.db.execute(
                text(
                    "UPDATE otp_challenges SET attempts = attempts + 1 "
                    "WHERE id = :id RETURNING attempts"
                ),
                {"id": challenge_id},
            )
        ).first()
        return int(row.attempts) if row is not None else 0

    async def consume(self, challenge_id: str) -> None:
        await self.db.execute(
            text("UPDATE otp_challenges SET consumed_at = now() WHERE id = :id"),
            {"id": challenge_id},
        )
