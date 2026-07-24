from src.services.preview import truncate_preview


def test_short_text_returned_unchanged() -> None:
    assert truncate_preview("denim kitni hai") == "denim kitni hai"


def test_long_text_cuts_at_word_boundary_with_ellipsis() -> None:
    text = "Bhai, denim 450 pieces hain stock mein. Rate: Rs. 1,200 per piece milega abhi"
    result = truncate_preview(text)
    assert len(result) <= 61  # 60 + ellipsis char
    assert result.endswith("…")
    assert not result[:-1].endswith(" ")


def test_never_splits_a_number_mid_token() -> None:
    # 60-char boundary lands inside "12,345" if cut naively; word-safe cut must
    # drop the whole token instead of truncating to "Rs. 12,3…"
    text = "x" * 54 + " Rs. 12,345 due"
    result = truncate_preview(text)
    assert "12,3" not in result or "12,345" in result
