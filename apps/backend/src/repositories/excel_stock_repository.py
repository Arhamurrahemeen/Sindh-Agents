from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ids import uuid7


@dataclass
class StockItemRow:
    id: str
    sku_canonical: str
    sku_aliases: list[str]
    stock: int
    unit: str
    price_per_unit: Decimal
    price_currency: str
    reorder_threshold: int
    last_updated: datetime


@dataclass
class ActiveSnapshot:
    id: str
    snapshot_hash: str
    item_count: int
    ingested_at: datetime


@dataclass
class ParsedStockRow:
    sku_canonical: str
    sku_aliases: list[str]
    stock: int
    unit: str
    price_per_unit: Decimal
    reorder_threshold: int


class ExcelStockRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_sme(self, sme_id: str) -> list[StockItemRow]:
        # tools_spec.md §1 — fuzzy matching runs in Python over this (small) list;
        # no fuzzystrmatch extension is enabled, and pilot-scale SKU counts (~15-20
        # per SME) make an in-Python scan simpler than adding one.
        rows = await self.db.execute(
            text(
                """
                SELECT i.id, i.sku_canonical, i.sku_aliases, i.stock, i.unit,
                       i.price_per_unit, i.price_currency, i.reorder_threshold,
                       s.ingested_at
                FROM excel_stock_items i
                JOIN excel_snapshots s ON s.id = i.snapshot_id AND s.is_active = true
                WHERE i.sme_id = :sme_id
                """
            ),
            {"sme_id": sme_id},
        )
        return [
            StockItemRow(
                id=str(row.id),
                sku_canonical=row.sku_canonical,
                sku_aliases=list(row.sku_aliases),
                stock=row.stock,
                unit=row.unit,
                price_per_unit=row.price_per_unit,
                price_currency=row.price_currency,
                reorder_threshold=row.reorder_threshold,
                last_updated=row.ingested_at,
            )
            for row in rows
        ]

    async def get_active_snapshot(self, sme_id: str) -> ActiveSnapshot | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT s.id, s.snapshot_hash, s.ingested_at, count(i.id) AS item_count
                    FROM excel_snapshots s
                    LEFT JOIN excel_stock_items i ON i.snapshot_id = s.id
                    WHERE s.sme_id = :sme_id AND s.is_active = true
                    GROUP BY s.id, s.snapshot_hash, s.ingested_at
                    """
                ),
                {"sme_id": sme_id},
            )
        ).first()
        if row is None:
            return None
        return ActiveSnapshot(
            id=str(row.id),
            snapshot_hash=row.snapshot_hash,
            item_count=row.item_count,
            ingested_at=row.ingested_at,
        )

    async def replace_snapshot(
        self,
        sme_id: str,
        snapshot_hash: str,
        source_filename: str,
        rows: list[ParsedStockRow],
    ) -> ActiveSnapshot:
        # db_schema.md §1.9 — ux_excel_active_per_sme allows only one active
        # snapshot per SME, so the old one must be deactivated before the new
        # row is inserted, in the same transaction as the bulk item insert.
        await self.db.execute(
            text(
                "UPDATE excel_snapshots SET is_active = false "
                "WHERE sme_id = :sme_id AND is_active = true"
            ),
            {"sme_id": sme_id},
        )

        snapshot_id = str(uuid7())
        inserted = (
            await self.db.execute(
                text(
                    "INSERT INTO excel_snapshots (id, sme_id, snapshot_hash, source_filename) "
                    "VALUES (:id, :sme_id, :snapshot_hash, :source_filename) "
                    "RETURNING ingested_at"
                ),
                {
                    "id": snapshot_id,
                    "sme_id": sme_id,
                    "snapshot_hash": snapshot_hash,
                    "source_filename": source_filename,
                },
            )
        ).one()

        for parsed_row in rows:
            await self.db.execute(
                text(
                    """
                    INSERT INTO excel_stock_items
                        (id, sme_id, snapshot_id, sku_canonical, sku_aliases, stock,
                         unit, price_per_unit, reorder_threshold)
                    VALUES
                        (:id, :sme_id, :snapshot_id, :sku_canonical, :sku_aliases, :stock,
                         :unit, :price_per_unit, :reorder_threshold)
                    """
                ),
                {
                    "id": str(uuid7()),
                    "sme_id": sme_id,
                    "snapshot_id": snapshot_id,
                    "sku_canonical": parsed_row.sku_canonical,
                    "sku_aliases": parsed_row.sku_aliases,
                    "stock": parsed_row.stock,
                    "unit": parsed_row.unit,
                    "price_per_unit": parsed_row.price_per_unit,
                    "reorder_threshold": parsed_row.reorder_threshold,
                },
            )

        await self.db.commit()
        return ActiveSnapshot(
            id=snapshot_id,
            snapshot_hash=snapshot_hash,
            item_count=len(rows),
            ingested_at=inserted.ingested_at,
        )
