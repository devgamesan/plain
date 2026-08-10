"""Tests for the natural sort key helper."""

import pytest

from zivo.state.natural_sort import natural_sort_key


def _sorted(names):
    return sorted(names, key=natural_sort_key)


@pytest.mark.parametrize(
    "names,expected",
    [
        (["file10", "file2", "file1"], ["file1", "file2", "file10"]),
        (["10", "2", "1"], ["1", "2", "10"]),
        (["a10b10", "a10b2", "a2b1"], ["a2b1", "a10b2", "a10b10"]),
    ],
)
def test_natural_sort_key_orders_numeric_runs_by_value(names, expected):
    assert _sorted(names) == expected


def test_natural_sort_key_zero_pad_tiebreak():
    assert _sorted(["part2", "part01", "part1"]) == ["part01", "part1", "part2"]


def test_natural_sort_key_case_insensitive_with_deterministic_tiebreak():
    # 'File1' / 'file1' share the same segment key; the original text breaks
    # the tie by code point so the order never depends on scandir ordering.
    assert _sorted(["file1", "File1"]) == ["File1", "file1"]


def test_natural_sort_key_prefix_shorter_first():
    assert _sorted(["a1", "a", "a10", "a2"]) == ["a", "a1", "a2", "a10"]


def test_natural_sort_key_matches_casefold_order_for_digit_free_names():
    assert _sorted(["pyproject.toml", "tests", "README.md"]) == sorted(
        ["pyproject.toml", "tests", "README.md"], key=str.casefold
    )


def test_natural_sort_key_treats_only_ascii_digits_as_numbers():
    # The superscript ² is not an ASCII digit, so it must not raise and must
    # not be parsed as a number; 'a2' still sorts before 'a10'.
    result = _sorted(["a10", "a²", "a2"])
    assert result.index("a2") < result.index("a10")


def test_natural_sort_key_empty_string_orders_first():
    assert _sorted(["b", "", "a"]) == ["", "a", "b"]
