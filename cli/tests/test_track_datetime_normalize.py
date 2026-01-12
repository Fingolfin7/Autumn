from __future__ import annotations

import re

import pytest

from autumn_cli.commands.sessions import _normalize_datetime


def _has_tz(s: str) -> bool:
    # Server expects no timezone; ensure we *don't* include one.
    return bool(re.search(r"(Z|[+-]\d\d:\d\d)$", s))


@pytest.mark.parametrize(
    "raw",
    [
        "2026-01-11T22:18:11",
        "2026-01-11 22:18:11",
        "2026-01-11T22:18:11.123456",
        "2026-01-11",
    ],
)
def test_normalize_datetime_outputs_server_format(raw: str):
    normalized = _normalize_datetime(raw)
    assert normalized.endswith(":00") or normalized.count(":") == 2
    assert "T" not in normalized
    assert not _has_tz(normalized)


@pytest.mark.parametrize(
    "raw",
    [
        "2026-01-11T22:18:11Z",
        "2026-01-11T22:18:11+00:00",
        "2026-01-11T22:18:11-05:00",
    ],
)
def test_normalize_datetime_accepts_timezone_inputs(raw: str):
    normalized = _normalize_datetime(raw)
    assert "T" not in normalized
    assert not _has_tz(normalized)


def test_normalize_datetime_rejects_gibberish():
    with pytest.raises(ValueError):
        _normalize_datetime("not a date")
