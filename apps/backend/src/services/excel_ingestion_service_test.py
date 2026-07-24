from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from src.errors import ApiError
from src.services.excel_ingestion_service import _parse_rows


def _workbook_bytes(header: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parses_valid_rows_with_defaults_and_aliases() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Aliases", "Stock", "Unit", "Price", "Reorder Threshold"],
        [
            ["denim-classic", "denim, jeans", 450, "pieces", 1200, 50],
            ["cotton-white", "", 20, "meters", 300.5, ""],
        ],
    )
    rows = _parse_rows(file_bytes)
    assert len(rows) == 2
    assert rows[0].sku_canonical == "denim-classic"
    assert rows[0].sku_aliases == ["denim", "jeans"]
    assert rows[0].price_per_unit == Decimal("1200.00")
    assert rows[1].sku_aliases == []
    assert rows[1].reorder_threshold == 0
    assert rows[1].price_per_unit == Decimal("300.50")


def test_skips_blank_rows() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Unit", "Price"],
        [
            ["denim-classic", 450, "pieces", 1200],
            [None, None, None, None],
        ],
    )
    rows = _parse_rows(file_bytes)
    assert len(rows) == 1


def test_missing_required_column_rejects_whole_file() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Price"],
        [["denim-classic", 450, 1200]],
    )
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert exc_info.value.status_code == 400
    assert "unit" in exc_info.value.message.lower()


def test_bad_unit_rejects_whole_file() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Unit", "Price"],
        [["denim-classic", 450, "bags", 1200]],
    )
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert exc_info.value.field == "unit"


def test_negative_price_rejects_whole_file() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Unit", "Price"],
        [["denim-classic", 450, "pieces", -5]],
    )
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert exc_info.value.field == "price"


def test_non_integer_stock_rejects_whole_file() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Unit", "Price"],
        [["denim-classic", 450.5, "pieces", 1200]],
    )
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert exc_info.value.status_code == 400


def test_empty_file_rejected() -> None:
    file_bytes = _workbook_bytes(["SKU", "Stock", "Unit", "Price"], [])
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert exc_info.value.status_code == 400


def test_too_many_rows_rejected() -> None:
    file_bytes = _workbook_bytes(
        ["SKU", "Stock", "Unit", "Price"],
        [[f"sku-{i}", 1, "pieces", 1] for i in range(501)],
    )
    with pytest.raises(ApiError) as exc_info:
        _parse_rows(file_bytes)
    assert "500" in exc_info.value.message
