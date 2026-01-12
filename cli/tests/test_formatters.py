from autumn_cli.utils.console import console
from autumn_cli.utils.log_render import render_sessions_list, render_active_timers_list


def test_logs_match_old_style_and_include_notes():
    sessions = [
        {
            "id": 1,
            "project": "Project A",
            "subprojects": ["Sub1"],
            "start_time": "2026-01-01T10:00:00",
            "end_time": "2026-01-01T11:00:00",
            "duration_minutes": 60,
            "note": "Did some work\nwith a newline",
        },
        {
            "id": 2,
            "project": "Project A",
            "subprojects": [],
            "start_time": "2026-01-01T12:00:00",
            "end_time": "2026-01-01T12:30:00",
            "duration_minutes": 30,
            "note": "",
        },
    ]

    with console.capture() as capture:
        console.print(render_sessions_list(sessions))
    rendered = capture.get()

    # Date header is plain and underlined; ensure it appears.
    assert "Thursday 01 January 2026" in rendered

    # Line format: HH:MM:SS to HH:MM:SS \t <dur>  <project> <subs> -> <note>
    assert "10:00:00" in rendered and "11:00:00" in rendered
    assert "Project A" in rendered
    assert "Sub1" in rendered

    # Notes included + sanitized + uses arrow
    assert "->" in rendered
    assert "Did some work with a newline" in rendered
    assert "Did some work\nwith a newline" not in rendered

    # Subprojects are bracketed
    assert "[Sub1]" in rendered


def test_status_matches_old_style_without_end_and_with_duration():
    active_sessions = [
        {
            "id": 10,
            "p": "Project Active",
            "subs": ["SubX"],
            "start": "2026-01-03T10:00:00",
            "elapsed": 125,
            "note": "Still going",
        }
    ]

    with console.capture() as capture:
        console.print(render_active_timers_list(active_sessions))
    rendered = capture.get()

    assert "Started" in rendered
    assert "Project Active" in rendered
    assert "[SubX]" in rendered
    assert " ago" in rendered
    assert "2h" in rendered and "5m" in rendered
    assert "End" not in rendered
