from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from src.repositories.excel_stock_repository import ExcelStockRepository
from src.services.clock import now_in_karachi
from src.tools.sku_matching import find_sku_matches
from src.tools.types import ToolContext, ToolSuccess

FRIDAY = 4
SATURDAY = 5


class CheckDeliverySlotInput(BaseModel):
    sku: str
    quantity: int = Field(gt=0, le=100_000)
    requested_date: date


class DeliverySlot(BaseModel):
    feasible: bool
    earliest_date: date
    reason: Literal[
        "stock_ok_delivery_ok",
        "stock_ok_delivery_delayed",
        "stock_low_partial_only",
        "stock_zero",
    ]
    partial_quantity_available: int | None


CheckDeliverySlotOutput = ToolSuccess[DeliverySlot]


def _next_business_day(d: date) -> date:
    next_day = d + timedelta(days=1)
    while next_day.weekday() in (FRIDAY, SATURDAY):
        next_day += timedelta(days=1)
    return next_day


def _shift_off_weekend(d: date) -> date:
    if d.weekday() == FRIDAY:
        return d + timedelta(days=2)
    if d.weekday() == SATURDAY:
        return d + timedelta(days=1)
    return d


async def check_delivery_slot(
    inputs: CheckDeliverySlotInput, context: ToolContext
) -> CheckDeliverySlotOutput:
    items = await ExcelStockRepository(context.db).list_for_sme(context.sme_id)
    matches = find_sku_matches(inputs.sku, items)
    stock = matches[0].stock if len(matches) == 1 else 0

    now = now_in_karachi()
    today = now.date()

    if inputs.requested_date <= today:
        if now.hour < 11:
            earliest = today
            delayed = False
        else:
            earliest = _next_business_day(today)
            delayed = True
    else:
        earliest = _shift_off_weekend(inputs.requested_date)
        delayed = earliest != inputs.requested_date

    if stock <= 0:
        return ToolSuccess[DeliverySlot](
            data=DeliverySlot(
                feasible=False,
                earliest_date=_next_business_day(today),
                reason="stock_zero",
                partial_quantity_available=None,
            )
        )
    if stock < inputs.quantity:
        return ToolSuccess[DeliverySlot](
            data=DeliverySlot(
                feasible=False,
                earliest_date=earliest,
                reason="stock_low_partial_only",
                partial_quantity_available=stock,
            )
        )
    return ToolSuccess[DeliverySlot](
        data=DeliverySlot(
            feasible=True,
            earliest_date=earliest,
            reason="stock_ok_delivery_delayed" if delayed else "stock_ok_delivery_ok",
            partial_quantity_available=None,
        )
    )
