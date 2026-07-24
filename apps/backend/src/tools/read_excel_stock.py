from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.repositories.excel_stock_repository import ExcelStockRepository
from src.tools.sku_matching import find_sku_matches
from src.tools.types import ToolContext, ToolNotFound, ToolSuccess


class ReadExcelStockInput(BaseModel):
    sku: str = Field(min_length=1, max_length=64)


class StockItem(BaseModel):
    sku_canonical: str
    sku_matched_from: str
    stock: int
    unit: str
    price_per_unit: Decimal
    price_currency: Literal["PKR"]
    last_updated: str
    low_stock_flag: bool


ReadExcelStockOutput = ToolSuccess[StockItem] | ToolNotFound


async def read_excel_stock(
    inputs: ReadExcelStockInput, context: ToolContext
) -> ReadExcelStockOutput:
    items = await ExcelStockRepository(context.db).list_for_sme(context.sme_id)
    matches = find_sku_matches(inputs.sku, items)

    if len(matches) == 0:
        return ToolNotFound(detail=f"sku '{inputs.sku}' has no match in current stock")
    if len(matches) > 1:
        return ToolNotFound(detail=f"ambiguous: matched {len(matches)} SKUs, please clarify")

    item = matches[0]
    return ToolSuccess[StockItem](
        data=StockItem(
            sku_canonical=item.sku_canonical,
            sku_matched_from=inputs.sku,
            stock=item.stock,
            unit=item.unit,
            price_per_unit=item.price_per_unit,
            price_currency="PKR",
            last_updated=item.last_updated.isoformat(),
            low_stock_flag=item.stock <= item.reorder_threshold,
        )
    )
