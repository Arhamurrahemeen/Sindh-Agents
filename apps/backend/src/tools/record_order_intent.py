from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from src.config import settings
from src.repositories.order_intent_repository import OrderIntentRepository
from src.tools.types import ToolContext, ToolSuccess


class RecordOrderIntentInput(BaseModel):
    idempotency_key: str
    buyer_id: str
    sku_canonical: str
    quantity: int = Field(gt=0)
    agreed_price_per_unit: Decimal
    delivery_date: date
    notes: str | None = Field(default=None, max_length=500)


class OrderIntentResult(BaseModel):
    intent_id: str
    created_at: str
    total_amount: Decimal
    dashboard_url: str


RecordOrderIntentOutput = ToolSuccess[OrderIntentResult]


async def record_order_intent(
    inputs: RecordOrderIntentInput, context: ToolContext
) -> RecordOrderIntentOutput:
    repo = OrderIntentRepository(context.db)

    existing = await repo.get_by_idempotency_key(context.sme_id, inputs.idempotency_key)
    if existing is not None:
        return ToolSuccess[OrderIntentResult](
            data=OrderIntentResult(
                intent_id=existing.id,
                created_at=existing.created_at.isoformat(),
                total_amount=existing.total_amount,
                dashboard_url=f"{settings.NEXT_PUBLIC_APP_URL}/conversations/{context.conversation_id}",
            )
        )

    intent = await repo.create(
        sme_id=context.sme_id,
        buyer_id=inputs.buyer_id,
        conversation_id=context.conversation_id,
        message_id=context.message_id,
        idempotency_key=inputs.idempotency_key,
        sku_canonical=inputs.sku_canonical,
        quantity=inputs.quantity,
        agreed_price_per_unit=inputs.agreed_price_per_unit,
        delivery_date=inputs.delivery_date,
        notes=inputs.notes,
    )
    await context.db.commit()

    return ToolSuccess[OrderIntentResult](
        data=OrderIntentResult(
            intent_id=intent.id,
            created_at=intent.created_at.isoformat(),
            total_amount=intent.total_amount,
            dashboard_url=f"{settings.widget_allowed_origins_list[0]}/conversations/{context.conversation_id}",
        )
    )
