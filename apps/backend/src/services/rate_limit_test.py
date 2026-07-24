from src.services import rate_limit


def test_allows_up_to_limit_then_blocks() -> None:
    key = "test-key-1"
    for _ in range(3):
        assert rate_limit.is_allowed(key, limit=3) is True
    assert rate_limit.is_allowed(key, limit=3) is False


def test_different_keys_are_independent() -> None:
    assert rate_limit.is_allowed("test-key-a", limit=1) is True
    assert rate_limit.is_allowed("test-key-b", limit=1) is True
