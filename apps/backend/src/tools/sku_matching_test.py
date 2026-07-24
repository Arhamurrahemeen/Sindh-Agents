from datetime import UTC, datetime
from decimal import Decimal

from src.repositories.excel_stock_repository import StockItemRow
from src.tools.sku_matching import find_sku_matches


def _item(sku: str, aliases: list[str] | None = None) -> StockItemRow:
    return StockItemRow(
        id=sku,
        sku_canonical=sku,
        sku_aliases=aliases or [],
        stock=100,
        unit="pieces",
        price_per_unit=Decimal("1200"),
        price_currency="PKR",
        reorder_threshold=10,
        last_updated=datetime.now(UTC),
    )


ITEMS = [_item("denim-classic"), _item("denim-stretch"), _item("cotton-white")]


def test_exact_match() -> None:
    matches = find_sku_matches("denim-classic", ITEMS)
    assert [m.sku_canonical for m in matches] == ["denim-classic"]


def test_substring_match_when_no_exact() -> None:
    matches = find_sku_matches("denim", ITEMS)
    assert {m.sku_canonical for m in matches} == {"denim-classic", "denim-stretch"}


def test_typo_falls_back_to_levenshtein() -> None:
    matches = find_sku_matches("cotton-whte", ITEMS)
    assert [m.sku_canonical for m in matches] == ["cotton-white"]


def test_no_match_returns_empty() -> None:
    assert find_sku_matches("silk", ITEMS) == []
