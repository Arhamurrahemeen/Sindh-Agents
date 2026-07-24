from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class BuyerAggregate:
    total_past_orders: int
    total_lifetime_value: Decimal
    avg_order_quantity: int | None
    last_order_at: datetime | None


@dataclass
class OrderIntent:
    id: str
    total_amount: Decimal
    created_at: datetime


class OrderIntentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_buyer_aggregate(self, sme_id: str, buyer_id: str) -> BuyerAggregate:
        row = (
            await self.db.execute(
                text(
                    "SELECT count(*) AS n, coalesce(sum(total_amount), 0) AS total_value, "
                    "avg(quantity) AS avg_qty, max(created_at) AS last_order_at "
                    "FROM order_intents WHERE sme_id = :sme_id AND buyer_id = :buyer_id"
                ),
                {"sme_id": sme_id, "buyer_id": buyer_id},
            )
        ).first()
        assert row is not None
        return BuyerAggregate(
            total_past_orders=int(row.n),
            total_lifetime_value=row.total_value,
            avg_order_quantity=int(row.avg_qty) if row.avg_qty is not None else None,
            last_order_at=row.last_order_at,
        )

    async def get_common_skus(self, sme_id: str, buyer_id: str, limit: int = 3) -> list[str]:
        rows = await self.db.execute(
            text(
                "SELECT sku_canonical FROM order_intents "
                "WHERE sme_id = :sme_id AND buyer_id = :buyer_id "
                "GROUP BY sku_canonical ORDER BY count(*) DESC LIMIT :limit"
            ),
            {"sme_id": sme_id, "buyer_id": buyer_id, "limit": limit},
        )
        return [row.sku_canonical for row in rows]

    async def get_avg_discount_pct(self, sme_id: str, buyer_id: str) -> Decimal | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT avg(
                        CASE WHEN s.price_per_unit > 0
                            THEN (1 - (oi.agreed_price_per_unit / s.price_per_unit)) * 100
                            ELSE NULL
                        END
                    ) AS avg_discount_pct
                    FROM order_intents oi
                    JOIN excel_stock_items s
                        ON s.sme_id = oi.sme_id AND s.sku_canonical = oi.sku_canonical
                    JOIN excel_snapshots snap
                        ON snap.id = s.snapshot_id AND snap.is_active = true
                    WHERE oi.sme_id = :sme_id AND oi.buyer_id = :buyer_id
                    """
                ),
                {"sme_id": sme_id, "buyer_id": buyer_id},
            )
        ).first()
        if row is None or row.avg_discount_pct is None:
            return None
        return Decimal(row.avg_discount_pct).quantize(Decimal("0.1"))

    async def get_by_idempotency_key(self, sme_id: str, idempotency_key: str) -> OrderIntent | None:
        row = (
            await self.db.execute(
                text(
                    "SELECT id, total_amount, created_at FROM order_intents "
                    "WHERE sme_id = :sme_id AND idempotency_key = :idempotency_key"
                ),
                {"sme_id": sme_id, "idempotency_key": idempotency_key},
            )
        ).first()
        if row is None:
            return None
        return OrderIntent(id=str(row.id), total_amount=row.total_amount, created_at=row.created_at)

    async def create(
        self,
        sme_id: str,
        buyer_id: str,
        conversation_id: str,
        message_id: str,
        idempotency_key: str,
        sku_canonical: str,
        quantity: int,
        agreed_price_per_unit: Decimal,
        delivery_date: date,
        notes: str | None,
    ) -> OrderIntent:
        intent_id = str(uuid7())
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO order_intents
                        (id, sme_id, buyer_id, conversation_id, message_id, idempotency_key,
                         sku_canonical, quantity, agreed_price_per_unit, delivery_date, notes)
                    VALUES
                        (:id, :sme_id, :buyer_id, :conversation_id, :message_id, :idempotency_key,
                         :sku_canonical, :quantity, :agreed_price_per_unit, :delivery_date, :notes)
                    RETURNING total_amount, created_at
                    """
                ),
                {
                    "id": intent_id,
                    "sme_id": sme_id,
                    "buyer_id": buyer_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "idempotency_key": idempotency_key,
                    "sku_canonical": sku_canonical,
                    "quantity": quantity,
                    "agreed_price_per_unit": agreed_price_per_unit,
                    "delivery_date": delivery_date,
                    "notes": notes,
                },
            )
        ).first()
        assert row is not None
        return OrderIntent(id=intent_id, total_amount=row.total_amount, created_at=row.created_at)
