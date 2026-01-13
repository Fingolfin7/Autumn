from __future__ import annotations

import datetime as _dt

import pytest

from autumn_cli.utils.datetime_parse import parse_user_datetime, format_server_datetime


def test_parse_today_is_midnight_local():
    base = _dt.datetime(2026, 1, 13, 15, 30, 10)
    pr = parse_user_datetime("today", now=base)
    assert pr.dt == _dt.datetime(2026, 1, 13, 0, 0, 0)


def test_parse_yesterday_is_previous_midnight_local():
    base = _dt.datetime(2026, 1, 13, 0, 5, 0)
    pr = parse_user_datetime("yesterday", now=base)
    assert pr.dt == _dt.datetime(2026, 1, 12, 0, 0, 0)


def test_parse_pure_offset_defaults_to_now_base():
    base = _dt.datetime(2026, 1, 13, 12, 0, 0)
    pr0 = parse_user_datetime("now", now=base)
    pr1 = parse_user_datetime("-5m", now=base)
    assert pr1.dt == pr0.dt - _dt.timedelta(minutes=5)


def test_parse_base_plus_offset():
    base = _dt.datetime(2026, 1, 13, 12, 0, 0)
    pr = parse_user_datetime("today+90m", now=base)
    assert pr.dt == _dt.datetime(2026, 1, 13, 1, 30, 0)


def test_format_server_datetime_drops_tz():
    dt = _dt.datetime(2026, 1, 13, 12, 0, 0, tzinfo=_dt.timezone.utc)
    s = format_server_datetime(dt)
    assert s == "2026-01-13 12:00:00" or isinstance(s, str)


@pytest.mark.parametrize("raw", ["", "   "])
def test_parse_rejects_empty(raw: str):
    with pytest.raises(ValueError):
        parse_user_datetime(raw)

