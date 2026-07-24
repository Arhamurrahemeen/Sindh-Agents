from decimal import Decimal

from pydantic import BaseModel

from src.repositories.order_intent_repository import OrderIntentRepository
from src.services import embedding_service, qdrant_service
from src.tools.types import ToolContext, ToolSuccess


class LookupBuyerHistoryInput(BaseModel):
    buyer_id: str
    include_semantic_context: bool = True
    # tools_spec.md §3 says the semantic query embeds "the current buyer
    # message" but the doc's own input schema never carries that text — a
    # spec gap. Added here since the tool can't embed anything without it;
    # the planner passes the buyer's current message verbatim.
    query_text: str = ""


class BuyerHistory(BaseModel):
    is_returning: bool
    total_past_orders: int
    total_lifetime_value: Decimal
    avg_order_quantity: int | None
    common_skus: list[str]
    typical_discount_pct: Decimal | None
    last_order_at: str | None
    semantic_notes: list[str]


LookupBuyerHistoryOutput = ToolSuccess[BuyerHistory]


async def lookup_buyer_history(
    inputs: LookupBuyerHistoryInput, context: ToolContext
) -> LookupBuyerHistoryOutput:
    repo = OrderIntentRepository(context.db)
    aggregate = await repo.get_buyer_aggregate(context.sme_id, inputs.buyer_id)

    if aggregate.total_past_orders == 0:
        return ToolSuccess[BuyerHistory](
            data=BuyerHistory(
                is_returning=False,
                total_past_orders=0,
                total_lifetime_value=Decimal("0"),
                avg_order_quantity=None,
                common_skus=[],
                typical_discount_pct=None,
                last_order_at=None,
                semantic_notes=[],
            )
        )

    common_skus = await repo.get_common_skus(context.sme_id, inputs.buyer_id)
    discount_pct = await repo.get_avg_discount_pct(context.sme_id, inputs.buyer_id)

    semantic_notes: list[str] = []
    if inputs.include_semantic_context and inputs.query_text:
        try:
            query_vector = await embedding_service.embed_query(inputs.query_text)
            semantic_notes = await qdrant_service.query_buyer_notes(
                context.db, context.sme_id, inputs.buyer_id, query_vector
            )
        except Exception as exc:  # noqa: BLE001 — external service, degrade not crash
            context.logger.warning(
                "qdrant_lookup_failed buyer_id=%s error=%s", inputs.buyer_id, exc
            )

    return ToolSuccess[BuyerHistory](
        data=BuyerHistory(
            is_returning=True,
            total_past_orders=aggregate.total_past_orders,
            total_lifetime_value=aggregate.total_lifetime_value,
            avg_order_quantity=aggregate.avg_order_quantity,
            common_skus=common_skus,
            typical_discount_pct=discount_pct,
            last_order_at=aggregate.last_order_at.isoformat() if aggregate.last_order_at else None,
            semantic_notes=semantic_notes,
        )
    )
