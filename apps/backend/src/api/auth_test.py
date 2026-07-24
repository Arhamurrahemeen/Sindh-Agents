from src.api.auth import mask_phone


def test_mask_phone_keeps_country_code_and_last_three_digits() -> None:
    assert mask_phone("+923005551234") == "+92 3XX ****234"
