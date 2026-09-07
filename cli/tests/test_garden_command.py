from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from click.testing import CliRunner
from rich.cells import cell_len

from autumn_cli.cli import cli


def _session(
    uuid: str = "session-1",
    *,
    start: str = "2026-01-10T10:00:00Z",
    end: str = "2026-01-10T11:00:00Z",
    note: str | None = None,
) -> dict[str, object]:
    return {"uuid": uuid, "start": start, "end": end, "note": note}


def _project(
    name: str,
    *,
    status: str = "active",
    start_date: str | None = "2026-01-01",
    sessions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "start_date": start_date,
        "sessions": sessions or [],
    }


def _export(*projects: dict[str, object]) -> dict[str, object]:
    return {"format": 2, "projects": list(projects)}


class _ReadOnlyGardenClient:
    """A deliberately tiny client: garden may only perform its two GET reads."""

    data: dict[str, object] = _export(
        _project("Alpha Project", sessions=[_session()]),
        _project(
            "Alpha Planning",
            sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
        ),
        _project("Dormant Seed"),
    )
    calls: list[object] = []

    def __init__(self, *args, **kwargs):
        type(self).calls = [("construct", args, kwargs)]

    def export_data(self):
        type(self).calls.append("export_data")
        return self.data

    def list_projects_flat(self, *, compact=True, **kwargs):
        type(self).calls.append(("list_projects_flat", compact, kwargs))
        return {
            "projects": [
                {"name": "Alpha Project", "id": 101},
                {"name": "Alpha Planning", "id": 102},
                {"name": "Dormant Seed", "id": 103},
            ]
        }

    def __getattr__(self, name):
        raise AssertionError(f"garden attempted a non-read API call: {name}")


def _invoke_live(monkeypatch, args: list[str]):
    _ReadOnlyGardenClient.calls = []
    monkeypatch.setattr(
        "autumn_cli.commands.garden.APIClient", _ReadOnlyGardenClient
    )
    return CliRunner().invoke(cli, ["garden", *args])


def test_garden_is_registered_and_help_exposes_display_options():
    runner = CliRunner()

    root = runner.invoke(cli, ["--help"])
    help_result = runner.invoke(cli, ["garden", "--help"])

    assert root.exit_code == 0
    assert "garden" in root.output
    assert help_result.exit_code == 0
    assert "--from-file" in help_result.output
    assert "--save" in help_result.output
    assert "--no-color" in help_result.output


def test_live_garden_uses_only_export_and_project_metadata_reads(monkeypatch):
    result = _invoke_live(monkeypatch, ["--no-color", "--width", "80"])

    assert result.exit_code == 0, result.output
    assert _ReadOnlyGardenClient.calls[1:] == [
        "export_data",
        ("list_projects_flat", False, {}),
    ]
    assert "Alpha Project" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["--at", "2026-9-01"],
        ["--at", "not-a-date"],
        ["--species", "oak"],
        ["--project", "Alpha", "--all"],
        ["--save", "garden.csv"],
        ["--page", "2", "--all"],
        ["--page", "2", "--project", "Alpha"],
    ],
)
def test_invalid_dates_and_option_combinations_reject_before_network(monkeypatch, args):
    constructed = False

    def fail_constructor(*unused_args, **unused_kwargs):
        nonlocal constructed
        constructed = True
        raise AssertionError("invalid garden options must not construct APIClient")

    monkeypatch.setattr("autumn_cli.commands.garden.APIClient", fail_constructor)
    result = CliRunner().invoke(cli, ["garden", *args])

    assert result.exit_code != 0
    assert not constructed


def test_future_date_rejects_before_network(monkeypatch):
    constructed = False

    def fail_constructor(*unused_args, **unused_kwargs):
        nonlocal constructed
        constructed = True
        raise AssertionError("future garden dates must not construct APIClient")

    monkeypatch.setattr("autumn_cli.commands.garden.APIClient", fail_constructor)
    future = (date.today() + timedelta(days=1)).isoformat()
    result = CliRunner().invoke(cli, ["garden", "--at", future])

    assert result.exit_code != 0
    assert "future growth" in result.output
    assert not constructed


def test_project_partial_match_is_ambiguous_but_exact_match_focuses(monkeypatch):
    ambiguous = _invoke_live(monkeypatch, ["--project", "Alpha", "--no-color"])
    assert ambiguous.exit_code != 0
    assert "Several projects match" in ambiguous.output
    assert "Alpha Project" in ambiguous.output
    assert "Alpha Planning" in ambiguous.output

    exact = _invoke_live(monkeypatch, ["--project", "Alpha Project", "--no-color"])
    assert exact.exit_code == 0, exact.output
    assert "1 saved session" in exact.output
    assert "Alpha Planning" not in exact.output


def test_from_file_is_offline_and_does_not_construct_client(tmp_path, monkeypatch):
    source = tmp_path / "garden-export.json"
    source.write_text(
        json.dumps(_export(_project("Offline", sessions=[_session()])),
                   ensure_ascii=False),
        encoding="utf-8",
    )

    def fail_constructor(*unused_args, **unused_kwargs):
        raise AssertionError("--from-file must not construct APIClient")

    monkeypatch.setattr("autumn_cli.commands.garden.APIClient", fail_constructor)
    result = CliRunner().invoke(
        cli, ["garden", "--from-file", str(source), "--no-color"]
    )

    assert result.exit_code == 0, result.output
    assert "Offline" in result.output


def test_no_color_and_no_color_environment_strip_control_sequences_and_markup(monkeypatch):
    unsafe = _export(
        _project(
            "[bold]<Long Project>\x1b[31m",
            sessions=[_session(note="note [italic]<tag>\x1b[2J")],
        )
    )
    _ReadOnlyGardenClient.data = unsafe

    try:
        no_color = _invoke_live(monkeypatch, ["--project", "Long Project", "--no-color"])
        assert no_color.exit_code == 0, no_color.output
        assert "\x1b" not in no_color.output
        assert "[bold]" in no_color.output
        assert "[italic]" in no_color.output
        assert "<Long Project>" in no_color.output

        monkeypatch.setenv("NO_COLOR", "1")
        env_no_color = _invoke_live(monkeypatch, ["--project", "Long Project"])
        assert env_no_color.exit_code == 0, env_no_color.output
        assert "\x1b" not in env_no_color.output
    finally:
        _ReadOnlyGardenClient.data = _export(
            _project("Alpha Project", sessions=[_session()]),
            _project(
                "Alpha Planning",
                sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
            ),
            _project("Dormant Seed"),
        )


@pytest.mark.parametrize("extension", [".svg", ".html", ".txt"])
def test_save_formats_preserve_literal_user_text_and_escape_markup(tmp_path, monkeypatch, extension):
    _ReadOnlyGardenClient.data = _export(
        _project(
            "<Oak & [bold]>\x1b[31m",
            status="complete",
            sessions=[
                _session(
                    end="2026-01-12T11:00:00Z",
                    note="note <tag> & [italic]\x1b[2J",
                )
            ],
        )
    )
    try:
        destination = tmp_path / f"woodland{extension}"
        result = _invoke_live(
            monkeypatch,
            ["--project", "<Oak & [bold]>", "--no-color", "--save", str(destination)],
        )

        assert result.exit_code == 0, result.output
        content = destination.read_text(encoding="utf-8")
        assert "note" in content
        assert "\x1b" not in content
        assert "<script>" not in content
        if extension == ".txt":
            assert "<Oak & [bold]>" in content
            assert "note <tag> & [italic]" in content
        else:
            assert "&lt;" in content
            assert "&amp;" in content
            assert "<Oak & [bold]>" not in content
            assert "cdnjs.cloudflare.com" not in content
    finally:
        _ReadOnlyGardenClient.data = _export(
            _project("Alpha Project", sessions=[_session()]),
            _project(
                "Alpha Planning",
                sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
            ),
            _project("Dormant Seed"),
        )


@pytest.mark.parametrize("width", [32, 80, 120])
def test_long_unicode_names_stay_within_requested_scene_width(monkeypatch, width):
    _ReadOnlyGardenClient.data = _export(
        _project(
            "長いプロジェクト名🌲" * 8,
            sessions=[_session()],
        )
    )
    try:
        result = _invoke_live(monkeypatch, ["--all", "--no-color", "--width", str(width)])
        assert result.exit_code == 0, result.output
        assert max(cell_len(line) for line in result.output.splitlines()) <= width
    finally:
        _ReadOnlyGardenClient.data = _export(
            _project("Alpha Project", sessions=[_session()]),
            _project(
                "Alpha Planning",
                sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
            ),
            _project("Dormant Seed"),
        )


@pytest.mark.parametrize("species", ["oak", "pine", "birch", "willow", "flowers", "fern"])
def test_each_species_can_render_a_mature_focused_plant(monkeypatch, species):
    _ReadOnlyGardenClient.data = _export(
        _project(
            "Mature",
            sessions=[
                _session(
                    end="2026-01-12T03:00:00Z",
                )
            ],
        )
    )
    try:
        result = _invoke_live(
            monkeypatch,
            ["--project", "Mature", "--species", species, "--ascii", "--no-color"],
        )
        assert result.exit_code == 0, result.output
        assert f"mature {('wildflowers' if species == 'flowers' else species)}" in result.output
        assert "\x1b" not in result.output
    finally:
        _ReadOnlyGardenClient.data = _export(
            _project("Alpha Project", sessions=[_session()]),
            _project(
                "Alpha Planning",
                sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
            ),
            _project("Dormant Seed"),
        )


@pytest.mark.parametrize("season", ["spring", "summer", "autumn", "winter"])
def test_stage_and_explicit_season_are_visible(monkeypatch, season):
    _ReadOnlyGardenClient.data = _export(
        _project(
            "Seasonal",
            sessions=[_session(end="2026-01-12T03:00:00Z")],
        )
    )
    try:
        result = _invoke_live(
            monkeypatch,
            ["--project", "Seasonal", "--species", "oak", "--season", season, "--no-color"],
        )
        assert result.exit_code == 0, result.output
        assert f"{season}" in result.output
        assert "mature oak" in result.output
    finally:
        _ReadOnlyGardenClient.data = _export(
            _project("Alpha Project", sessions=[_session()]),
            _project(
                "Alpha Planning",
                sessions=[_session("planning", end="2026-01-10T12:00:00Z")],
            ),
            _project("Dormant Seed"),
        )


def test_ascii_art_uses_ascii_glyphs_and_dormant_seed_and_empty_history_are_clear(monkeypatch):
    result = _invoke_live(monkeypatch, ["--all", "--ascii", "--no-color"])
    assert result.exit_code == 0, result.output
    assert "seed" in result.output
    assert "─" not in result.output
    assert "◦" not in result.output

    empty = _invoke_live(monkeypatch, ["--all", "--at", "2025-01-01", "--no-color"])
    assert empty.exit_code == 0, empty.output
    assert "A quiet patch of earth." in empty.output
    assert "No projects to show for this view." in empty.output


def test_paging_visits_each_project_without_overlap(monkeypatch):
    first = _invoke_live(monkeypatch, ["--limit", "1", "--no-color"])
    second = _invoke_live(monkeypatch, ["--limit", "1", "--page", "2", "--no-color"])
    last = _invoke_live(monkeypatch, ["--limit", "1", "--page", "3", "--no-color"])
    beyond = _invoke_live(monkeypatch, ["--limit", "1", "--page", "4", "--no-color"])
    assert first.exit_code == second.exit_code == last.exit_code == 0
    assert "Alpha Planning" in first.output and "Alpha Project" not in first.output
    assert "Alpha Project" in second.output and "Alpha Planning" not in second.output
    assert "Dormant Seed" in last.output
    assert "Projects 2-2 of 3" in second.output
    assert "--page 3 --limit 1" in second.output
    assert "Next:" not in last.output
    assert beyond.exit_code == 1
    assert "No clearing on page 4" in beyond.output


def test_historical_page_hint_preserves_date(monkeypatch):
    result = _invoke_live(monkeypatch, ["--limit", "1", "--at", "2026-01-10", "--width", "120"])
    assert result.exit_code == 0
    assert "--page 2 --limit 1 --at 2026-01-10" in result.output


def test_forced_colour_can_override_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("autumn_cli.commands.garden.APIClient", _ReadOnlyGardenClient)
    result = CliRunner().invoke(cli, ["garden", "--color"], color=True)
    assert result.exit_code == 0
    assert "\x1b[" in result.output
