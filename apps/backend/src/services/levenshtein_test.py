from src.services.levenshtein import levenshtein_distance


def test_identical_strings_are_zero_distance() -> None:
    assert levenshtein_distance("denim", "denim") == 0


def test_one_substitution() -> None:
    assert levenshtein_distance("denim", "denin") == 1


def test_empty_string_distance_is_length() -> None:
    assert levenshtein_distance("", "abc") == 3
    assert levenshtein_distance("abc", "") == 3


def test_typo_within_two_edits() -> None:
    assert levenshtein_distance("denim-clasic", "denim-classic") <= 2
