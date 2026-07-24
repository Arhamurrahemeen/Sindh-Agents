from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.tools.check_delivery_slot import CheckDeliverySlotInput, check_delivery_slot
from src.tools.get_current_date import GetCurrentDateInput, get_current_date
from src.tools.lookup_buyer_history import LookupBuyerHistoryInput, lookup_buyer_history
from src.tools.read_excel_stock import ReadExcelStockInput, read_excel_stock
from src.tools.record_order_intent import RecordOrderIntentInput, record_order_intent
from src.tools.types import ToolContext


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[[Any, ToolContext], Awaitable[BaseModel]]


# tools_spec.md §0.2 — the planner LLM sees only these five tools. No global exposure.
STOCK_AGENT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="read_excel_stock",
        description=(
            "Look up current stock and price for a product by SKU. Use the SKU as it "
            "appears in the buyer's message or buyer history — fuzzy matching to the "
            "canonical SKU is handled by the tool."
        ),
        input_model=ReadExcelStockInput,
        func=read_excel_stock,
    ),
    ToolSpec(
        name="check_delivery_slot",
        description=(
            "Given a quantity and requested date, determine whether delivery is "
            "feasible and the earliest date. Use when the buyer asks about timing."
        ),
        input_model=CheckDeliverySlotInput,
        func=check_delivery_slot,
    ),
    ToolSpec(
        name="lookup_buyer_history",
        description=(
            "Retrieve a returning buyer's past order patterns, including any "
            "negotiated discount. Use when the buyer references being a repeat "
            "customer or asks for a discount."
        ),
        input_model=LookupBuyerHistoryInput,
        func=lookup_buyer_history,
    ),
    ToolSpec(
        name="record_order_intent",
        description=(
            "Persist a buyer's confirmed order (SKU, quantity, agreed price) for the "
            "owner to review. Use only after stock and price are confirmed and the "
            "buyer has agreed."
        ),
        input_model=RecordOrderIntentInput,
        func=record_order_intent,
    ),
    ToolSpec(
        name="get_current_date",
        description=(
            "Get today's date and day of week in Asia/Karachi. Use for any "
            "'today'/'tomorrow'/'this week' reasoning — never guess the date."
        ),
        input_model=GetCurrentDateInput,
        func=get_current_date,
    ),
]

TOOLS_BY_NAME: dict[str, ToolSpec] = {tool.name: tool for tool in STOCK_AGENT_TOOLS}
