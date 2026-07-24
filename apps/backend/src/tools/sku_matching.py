from src.repositories.excel_stock_repository import StockItemRow
from src.services.levenshtein import levenshtein_distance


def find_sku_matches(query: str, items: list[StockItemRow]) -> list[StockItemRow]:
    # tools_spec.md §1 — exact match first, then case-insensitive substring,
    # then Levenshtein <= 2. Each tier short-circuits if it finds anything.
    q = query.strip().lower()

    exact = [
        item
        for item in items
        if item.sku_canonical.lower() == q or q in (alias.lower() for alias in item.sku_aliases)
    ]
    if exact:
        return exact

    substring = [item for item in items if q in item.sku_canonical.lower()]
    if substring:
        return substring

    return [item for item in items if levenshtein_distance(q, item.sku_canonical.lower()) <= 2]
