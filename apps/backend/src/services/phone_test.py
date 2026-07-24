from src.services.phone import mask_phone


def test_masks_middle_digits_keeps_country_code_and_last_three() -> None:
    assert mask_phone("+923005551234") == "+92 3XX ****234"


def test_returns_placeholder_for_missing_phone() -> None:
    assert mask_phone(None) == "—"
