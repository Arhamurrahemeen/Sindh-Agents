import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session
from src.ids import uuid7

PILOT_SME_PHONE = "+923005551234"
PILOT_SME_NAME = "Aslam Textiles"
PILOT_OWNER_NAME = "Aslam"

STOCK_AGENT_TOOL_BINDINGS = [
    "read_excel_stock",
    "check_delivery_slot",
    "lookup_buyer_history",
    "record_order_intent",
    "get_current_date",
]

# db_schema.md §4 — ~15 SKUs. denim-classic's stock/price match the worked
# example quoted throughout MVP_v1.md's P3 section (450 pieces, Rs. 1,200).
STOCK_ITEMS = [
    ("denim-classic", ["denim"], 450, "pieces", "1200.00", 50),
    ("denim-stretch", ["stretch denim"], 220, "pieces", "1350.00", 30),
    ("cotton-white", ["white cotton"], 800, "meters", "450.00", 100),
    ("cotton-black", ["black cotton"], 600, "meters", "460.00", 100),
    ("poly-blend", ["polyester blend"], 300, "meters", "380.00", 50),
    ("khaddar-plain", [], 150, "meters", "520.00", 20),
    ("khaddar-printed", [], 90, "meters", "610.00", 20),
    ("linen-natural", [], 40, "meters", "890.00", 15),
    ("silk-mix", [], 25, "meters", "1450.00", 10),
    ("jersey-cotton", [], 500, "kg", "700.00", 60),
    ("fleece-heavy", [], 180, "kg", "820.00", 25),
    ("chiffon-light", [], 70, "meters", "560.00", 15),
    ("velvet-classic", [], 15, "meters", "1900.00", 10),
    ("net-embroidered", [], 35, "meters", "1100.00", 10),
    ("canvas-heavy", [], 0, "meters", "640.00", 20),
]

BUYERS = [
    ("Ali Traders", "seed-ali-traders", True),
    ("Saleem Fabrics", "seed-saleem-fabrics", False),
    ("Khan Garments", "seed-khan-garments", False),
]


async def run() -> None:
    # db_schema.md §4 — idempotent: reruns are no-ops once the SME/agent exist.
    async with async_session() as session:
        existing = await session.execute(
            text("SELECT id FROM smes WHERE owner_phone = :phone"),
            {"phone": PILOT_SME_PHONE},
        )
        row = existing.first()

        if row is None:
            sme_id = str(uuid7())
            await session.execute(
                text(
                    "INSERT INTO smes (id, name, owner_name, owner_phone) "
                    "VALUES (:id, :name, :owner_name, :owner_phone)"
                ),
                {
                    "id": sme_id,
                    "name": PILOT_SME_NAME,
                    "owner_name": PILOT_OWNER_NAME,
                    "owner_phone": PILOT_SME_PHONE,
                },
            )
        else:
            sme_id = str(row.id)

        existing_agent = await session.execute(
            text("SELECT id FROM agents WHERE sme_id = :sme_id"),
            {"sme_id": sme_id},
        )
        agent_row = existing_agent.first()
        if agent_row is None:
            agent_id = str(uuid7())
            await session.execute(
                text(
                    "INSERT INTO agents "
                    "(id, sme_id, name, name_urdu, status, tool_bindings, system_prompt_key) "
                    "VALUES (:id, :sme_id, :name, :name_urdu, 'live', CAST(:tool_bindings AS jsonb), "
                    ":system_prompt_key)"
                ),
                {
                    "id": agent_id,
                    "sme_id": sme_id,
                    "name": "Stock Agent",
                    "name_urdu": "Stock Agent",
                    "tool_bindings": json.dumps(STOCK_AGENT_TOOL_BINDINGS),
                    "system_prompt_key": "stock_agent_v1",
                },
            )
        else:
            agent_id = str(agent_row.id)

        await _seed_excel_stock(session, sme_id)
        await _seed_buyers_and_history(session, sme_id, agent_id)

        await session.commit()


async def _seed_excel_stock(session: AsyncSession, sme_id: str) -> None:
    existing = await session.execute(
        text("SELECT id FROM excel_snapshots WHERE sme_id = :sme_id AND is_active = true"),
        {"sme_id": sme_id},
    )
    if existing.first() is not None:
        return

    snapshot_id = str(uuid7())
    await session.execute(
        text(
            "INSERT INTO excel_snapshots (id, sme_id, snapshot_hash, source_filename) "
            "VALUES (:id, :sme_id, :hash, :filename)"
        ),
        {
            "id": snapshot_id,
            "sme_id": sme_id,
            "hash": "seed-snapshot-hash",
            "filename": "seed_stock.xlsx",
        },
    )

    for sku, aliases, stock, unit, price, reorder in STOCK_ITEMS:
        await session.execute(
            text(
                "INSERT INTO excel_stock_items "
                "(id, sme_id, snapshot_id, sku_canonical, sku_aliases, stock, unit, "
                "price_per_unit, reorder_threshold) "
                "VALUES (:id, :sme_id, :snapshot_id, :sku, :aliases, :stock, :unit, "
                ":price, :reorder)"
            ),
            {
                "id": str(uuid7()),
                "sme_id": sme_id,
                "snapshot_id": snapshot_id,
                "sku": sku,
                "aliases": aliases,
                "stock": stock,
                "unit": unit,
                "price": price,
                "reorder": reorder,
            },
        )


async def _seed_buyers_and_history(session: AsyncSession, sme_id: str, agent_id: str) -> None:
    # per-buyer idempotency check, not "any buyer exists" — P2/manual testing
    # routinely creates unrelated buyer rows via the widget's own get_or_create,
    # and a blanket check here would permanently skip seeding these specific
    # buyers (found live: this exact bug silently skipped Ali Traders' order
    # history for the entire P3 build).
    for name, wa_id, is_returning in BUYERS:
        existing = await session.execute(
            text("SELECT id FROM buyers WHERE sme_id = :sme_id AND wa_id = :wa_id"),
            {"sme_id": sme_id, "wa_id": wa_id},
        )
        if existing.first() is not None:
            continue

        buyer_id = str(uuid7())
        await session.execute(
            text(
                "INSERT INTO buyers (id, sme_id, name, wa_id) VALUES (:id, :sme_id, :name, :wa_id)"
            ),
            {"id": buyer_id, "sme_id": sme_id, "name": name, "wa_id": wa_id},
        )

        if not is_returning:
            continue

        conversation_id = str(uuid7())
        await session.execute(
            text(
                "INSERT INTO conversations (id, sme_id, agent_id, buyer_id) "
                "VALUES (:id, :sme_id, :agent_id, :buyer_id)"
            ),
            {"id": conversation_id, "sme_id": sme_id, "agent_id": agent_id, "buyer_id": buyer_id},
        )

        message_id = str(uuid7())
        await session.execute(
            text(
                "INSERT INTO messages (id, sme_id, conversation_id, sender, text, is_pending) "
                "VALUES (:id, :sme_id, :conversation_id, 'buyer', :text, false)"
            ),
            {
                "id": message_id,
                "sme_id": sme_id,
                "conversation_id": conversation_id,
                "text": "denim-classic 100 pieces chahiye, purana rate pe",
            },
        )

        now = datetime.now(UTC)
        for i, (sku, qty, price) in enumerate(
            [("denim-classic", 100, "1140.00"), ("denim-classic", 150, "1140.00")]
        ):
            await session.execute(
                text(
                    "INSERT INTO order_intents "
                    "(id, sme_id, buyer_id, conversation_id, message_id, idempotency_key, "
                    "sku_canonical, quantity, agreed_price_per_unit, delivery_date, created_at) "
                    "VALUES (:id, :sme_id, :buyer_id, :conversation_id, :message_id, "
                    ":idempotency_key, :sku, :qty, :price, :delivery_date, :created_at)"
                ),
                {
                    "id": str(uuid7()),
                    "sme_id": sme_id,
                    "buyer_id": buyer_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "idempotency_key": f"seed-order-{buyer_id}-{i}",
                    "sku": sku,
                    "qty": qty,
                    "price": price,
                    "delivery_date": date.today() - timedelta(days=30 * (i + 1)),
                    "created_at": now - timedelta(days=30 * (i + 1)),
                },
            )
