from __future__ import annotations

import pytest

from autumn_cli.utils.duration_parse import parse_duration_to_seconds


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("5s", 5),
        ("5m", 300),
        ("2h", 7200),
        ("1d", 86400),
        ("1w", 604800),
        ("1h30m", 5400),
        ("2h5m10s", 2 * 3600 + 5 * 60 + 10),
        ("1w2d", 7 * 86400 + 2 * 86400),
        ("1h 30m", 5400),
    ],
)
def test_parse_duration_to_seconds(raw: str, expected: int):
    assert parse_duration_to_seconds(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "abc", "1x", "1h30", "-5m"])
def test_parse_duration_rejects_invalid(raw: str):
    with pytest.raises(ValueError):
        parse_duration_to_seconds(raw)
