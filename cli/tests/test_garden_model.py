"""Tests for deterministic Autumn garden history modeling."""

import re
from datetime import date, datetime
from dateutil.tz import gettz

import pytest

from autumn_cli.utils.garden_model import (
    build_garden,
    sanitize_text,
    stage_for_seconds,
)


PRAGUE = gettz("Europe/Prague")


def _session(uuid, start, end, note=None):
    return {"uuid": uuid, "start": start, "end": end, "note": note, "links": []}


def _project(name="Alpha", *, status="active", start_date="2026-01-01", sessions=None):
    return {
        "name": name,
        "status": status,
        "start_date": start_date,
        "context": None,
        "tags": [],
        "sessions": sessions or [],
    }


def _export(*projects):
    return {"format": 2, "projects": list(projects)}


def test_historical_day_is_inclusive_and_clips_at_dst_local_midnight():
    data = _export(
        _project(
            sessions=[
                _session(
                    "known-note",
                    "2026-03-28T10:00:00+00:00",
                    "2026-03-28T11:00:00+00:00",
                    "known note",
                ),
                # Europe/Prague switches to summer time on this date.  Local
                # midnight after the requested day is 22:00 UTC, not 23:00 UTC.
                _session(
                    "crosses-cutoff",
                    "2026-03-29T20:00:00+00:00",
                    "2026-03-29T23:00:00+00:00",
                    "future note",
                ),
                _session(
                    "next-day",
                    "2026-03-29T22:00:00+00:00",
                    "2026-03-29T23:00:00+00:00",
                    "too late",
                ),
            ]
        )
    )

    snapshot = build_garden(
        data,
        at=date(2026, 3, 29),
        now=datetime(2026, 9, 7, 12, tzinfo=PRAGUE),
    )

    plant = snapshot.plants[0]
    assert snapshot.historical is True
    assert plant.total_seconds == 3 * 3600
    assert plant.session_count == 2
    assert plant.last_session == datetime(2026, 3, 30, 0, tzinfo=PRAGUE)
    assert plant.latest_note == "known note"


def test_duplicate_uuids_are_counted_once_per_project_and_not_across_projects():
    repeated = _session(
        "same-uuid", "2026-01-02T10:00:00+00:00", "2026-01-02T11:00:00+00:00"
    )
    snapshot = build_garden(
        _export(
            _project("Alpha", sessions=[repeated, dict(repeated)]),
            _project("Beta", sessions=[dict(repeated)]),
        ),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
    )

    assert snapshot.skipped_sessions == 1
    assert {plant.name: plant.session_count for plant in snapshot.plants} == {
        "Alpha": 1,
        "Beta": 1,
    }


def test_current_snapshot_stops_at_now_and_hides_notes_from_future_ends():
    snapshot = build_garden(
        _export(
            _project(
                sessions=[
                    _session(
                        "past",
                        "2026-07-01T08:00:00+00:00",
                        "2026-07-01T09:00:00+00:00",
                        "known note",
                    ),
                    _session(
                        "crosses-now",
                        "2026-07-01T09:00:00+00:00",
                        "2026-07-01T11:00:00+00:00",
                        "future note",
                    ),
                    _session(
                        "future-start",
                        "2026-07-01T10:30:00+00:00",
                        "2026-07-01T11:30:00+00:00",
                        "later note",
                    ),
                ]
            )
        ),
        now=datetime(2026, 7, 1, 12, tzinfo=PRAGUE),  # 10:00 UTC
    )

    plant = snapshot.plants[0]
    assert snapshot.historical is False
    assert plant.total_seconds == 2 * 3600
    assert plant.session_count == 2
    assert plant.last_session == datetime(2026, 7, 1, 12, tzinfo=PRAGUE)
    assert plant.latest_note == "known note"


def test_explicit_today_cannot_include_future_time():
    snapshot = build_garden(
        _export(_project(sessions=[
            _session("future", "2026-07-01T11:00:00Z", "2026-07-01T14:00:00Z"),
        ])),
        at=date(2026, 7, 1),
        now=datetime(2026, 7, 1, 12, tzinfo=PRAGUE),
    )
    assert snapshot.plants[0].total_seconds == 0


def test_naive_now_and_naive_session_times_use_the_same_system_local_zone():
    plant = build_garden(
        _export(
            _project(
                sessions=[
                    _session(
                        "local",
                        "2026-07-01T10:00:00",
                        "2026-07-01T13:00:00",
                    )
                ]
            )
        ),
        now=datetime(2026, 7, 1, 12),
    ).plants[0]

    assert plant.total_seconds == 2 * 3600
    assert plant.last_session is not None
    assert plant.last_session.tzinfo is not None


def test_malformed_open_and_nonpositive_sessions_are_skipped():
    snapshot = build_garden(
        _export(
            _project(
                sessions=[
                    {"uuid": "not-a-record"},
                    _session("open", "2026-01-01T10:00:00Z", None),
                    _session("backwards", "2026-01-01T11:00:00Z", "2026-01-01T10:00:00Z"),
                    _session("zero", "2026-01-01T10:00:00Z", "2026-01-01T10:00:00Z"),
                    _session("valid", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z"),
                    "bad shape",
                ]
            )
        ),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
    )

    assert snapshot.skipped_sessions == 5
    assert snapshot.plants[0].session_count == 1
    assert snapshot.plants[0].total_seconds == 1800


@pytest.mark.parametrize(
    ("seconds", "stage"),
    [
        (0, 0),
        (1, 1),
        (2 * 3600 - 1, 1),
        (2 * 3600, 2),
        (10 * 3600, 3),
        (40 * 3600, 4),
    ],
)
def test_growth_stage_thresholds_are_stable(seconds, stage):
    assert stage_for_seconds(seconds) == stage


def test_idle_time_does_not_decay_growth():
    data = _export(
        _project(
            sessions=[
                _session("one", "2026-01-01T10:00:00Z", "2026-01-01T13:00:00Z")
            ]
        )
    )

    early = build_garden(data, now=datetime(2026, 1, 2, tzinfo=PRAGUE)).plants[0]
    late = build_garden(data, now=datetime(2036, 1, 2, tzinfo=PRAGUE)).plants[0]

    assert (early.stage, early.seed, early.species) == (
        late.stage,
        late.seed,
        late.species,
    )


def test_totals_dates_notes_and_visits_come_only_from_sessions():
    project = _project(
        sessions=[
            _session(
                "first",
                "2026-01-01T23:30:00+00:00",
                "2026-01-02T00:30:00+00:00",
                "first\nline",
            ),
            _session(
                "latest",
                "2026-01-03T10:00:00+00:00",
                "2026-01-03T12:30:00+00:00",
                "\x1b[31mred\x1b[0m\ttext",
            ),
        ]
    )
    project["total_time"] = 999999
    project["session_count"] = 999

    plant = build_garden(
        _export(project), now=datetime(2026, 9, 7, tzinfo=PRAGUE)
    ).plants[0]

    assert plant.total_seconds == 3.5 * 3600
    assert plant.session_count == 2
    assert plant.first_session == datetime(2026, 1, 2, 0, 30, tzinfo=PRAGUE)
    assert plant.last_session == datetime(2026, 1, 3, 13, 30, tzinfo=PRAGUE)
    assert plant.latest_note == "red text"
    assert plant.visit_days == 2


def test_identity_keeps_seed_and_species_stable_across_rename():
    sessions = [
        _session("one", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z")
    ]
    before = build_garden(
        _export(_project("Old Name", sessions=sessions)),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
        identities={"Old Name": 42},
    ).plants[0]
    after = build_garden(
        _export(_project("New Name", sessions=sessions)),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
        identities={"New Name": 42},
    ).plants[0]

    assert before.key == after.key == "42"
    assert before.seed == after.seed
    assert before.species == after.species


def test_historical_project_existence_and_completion_are_conservative():
    snapshot = build_garden(
        _export(
            _project("Known", status="complete", start_date="2026-01-01"),
            _project("Unknown", start_date=None),
            _project("Future", start_date="2026-02-01"),
        ),
        at=date(2026, 1, 15),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
    )

    assert [plant.name for plant in snapshot.plants] == ["Known"]
    assert snapshot.plants[0].completed is False


def test_projects_sort_by_latest_activity_then_clean_name_and_key():
    snapshot = build_garden(
        _export(
            _project("Zed", sessions=[]),
            _project(
                " Beta\nProject\x00 ",
                sessions=[
                    _session("new", "2026-01-03T10:00:00Z", "2026-01-03T11:00:00Z")
                ],
            ),
            _project(
                "Alpha",
                sessions=[
                    _session("old", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z")
                ],
            ),
        ),
        now=datetime(2026, 9, 7, tzinfo=PRAGUE),
    )

    assert [plant.name for plant in snapshot.plants] == ["Beta Project", "Alpha", "Zed"]
    assert sanitize_text("a\n\x1b[31mb\x1b[0m") == "a b"


@pytest.mark.parametrize(
    "data, message",
    [
        ({}, "format 2"),
        ({"format": 1, "projects": []}, "format 2"),
        ({"format": 2, "projects": {}}, "projects list"),
        ({"format": 2, "projects": ["bad"]}, "projects[0] must be a mapping"),
    ],
)
def test_malformed_export_envelope_has_clear_errors(data, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        build_garden(data)
