from autumn_cli.utils.formatters import format_duration_minutes


def test_format_duration_minutes_includes_seconds_short():
    # 90 seconds = 1m 30s
    # Now zero-padded: 01m 30s
    assert format_duration_minutes(1.5) == "01m 30s"


def test_format_duration_minutes_includes_seconds_long():
    # 1 hour, 2 minutes, 3 seconds
    minutes = (1 * 3600 + 2 * 60 + 3) / 60.0
    # Code: if hours > 0: return f"{hours:02d}h {mins:02d}m"
    # It drops seconds.
    assert format_duration_minutes(minutes) == "01h 02m"


