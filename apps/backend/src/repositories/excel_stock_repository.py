from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
