from autumn_cli.utils.formatters import format_duration_minutes


def test_format_duration_minutes_includes_seconds_short():
    # 90 seconds
    assert format_duration_minutes(1.5) == "1m 30s"


def test_format_duration_minutes_includes_seconds_long():
    # 1 hour, 2 minutes, 3 seconds
    minutes = (1 * 3600 + 2 * 60 + 3) / 60.0
    assert format_duration_minutes(minutes) == "1h 02m 03s"

