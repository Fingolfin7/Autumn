"""Tests for the import command."""

import json

from click.testing import CliRunner

from autumn_cli.commands.import_cmd import import_cmd


class _ImportClient:
    calls = []
    summary = {
        "projects_processed": 1,
        "projects_created": 1,
        "projects_updated": 0,
        "sessions_imported": 2,
        "skipped": [],
    }

    def __init__(self, *args, **kwargs):
        pass

    def import_data(self, **kwargs):
        type(self).calls.append(kwargs)
        return {"ok": True, "summary": type(self).summary}


def test_import_plain_json_posts_data_and_options(monkeypatch):
    _ImportClient.calls = []
    monkeypatch.setattr("autumn_cli.commands.import_cmd.APIClient", _ImportClient)
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("export.json", "w", encoding="utf-8") as export_file:
            json.dump({"Project A": {"Session History": []}}, export_file)
        result = runner.invoke(
            import_cmd,
            ["export.json", "--force", "--tolerance", "5", "--autumn-format", "--context", "Work", "--yes"],
        )

    assert result.exit_code == 0
    assert "Importing 1 projects from" in result.output
    assert _ImportClient.calls == [{
        "data": {"Project A": {"Session History": []}},
        "data_compressed": None,
        "force": True,
        "merge": False,
        "tolerance": 5,
        "autumn_import": True,
        "context": "Work",
    }]


def test_import_non_json_posts_compressed_data(monkeypatch):
    _ImportClient.calls = []
    monkeypatch.setattr("autumn_cli.commands.import_cmd.APIClient", _ImportClient)
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("export.txt", "w", encoding="utf-8") as export_file:
            export_file.write("compressed-export-payload")
        result = runner.invoke(import_cmd, ["export.txt", "--merge", "--yes"])

    assert result.exit_code == 0
    assert "Importing compressed export" in result.output
    assert _ImportClient.calls == [{
        "data": None,
        "data_compressed": "compressed-export-payload",
        "force": False,
        "merge": True,
        "tolerance": 2,
        "autumn_import": False,
        "context": None,
    }]


def test_import_rejects_force_and_merge_before_api_call(monkeypatch):
    _ImportClient.calls = []
    monkeypatch.setattr("autumn_cli.commands.import_cmd.APIClient", _ImportClient)
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("export.json", "w", encoding="utf-8") as export_file:
            export_file.write("{}")
        result = runner.invoke(import_cmd, ["export.json", "--force", "--merge"])

    assert result.exit_code != 0
    assert "cannot be used together" in result.output
    assert _ImportClient.calls == []


def test_import_summary_lists_skipped_projects(monkeypatch):
    _ImportClient.calls = []
    _ImportClient.summary = {
        "projects_processed": 2,
        "projects_created": 1,
        "projects_updated": 1,
        "sessions_imported": 4,
        "skipped": ["Existing Project"],
    }
    monkeypatch.setattr("autumn_cli.commands.import_cmd.APIClient", _ImportClient)
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("export.json", "w", encoding="utf-8") as export_file:
            export_file.write("{}")
        result = runner.invoke(import_cmd, ["export.json", "--yes"])

    assert result.exit_code == 0
    assert "Projects created: 1" in result.output
    assert "Projects updated: 1" in result.output
    assert "Sessions imported: 4" in result.output
    assert "Skipped projects:" in result.output
    assert "Existing Project" in result.output
    assert "--merge or --force" in result.output


def test_import_confirmation_can_abort_or_be_skipped(monkeypatch):
    _ImportClient.calls = []
    _ImportClient.summary = {
        "projects_processed": 0,
        "projects_created": 0,
        "projects_updated": 0,
        "sessions_imported": 0,
        "skipped": [],
    }
    monkeypatch.setattr("autumn_cli.commands.import_cmd.APIClient", _ImportClient)
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("export.json", "w", encoding="utf-8") as export_file:
            export_file.write("{}")
        aborted = runner.invoke(import_cmd, ["export.json"], input="n\n")
        confirmed = runner.invoke(import_cmd, ["export.json", "--yes"])

    assert aborted.exit_code == 0
    assert "Cancelled." in aborted.output
    assert confirmed.exit_code == 0
    assert _ImportClient.calls == [{
        "data": {},
        "data_compressed": None,
        "force": False,
        "merge": False,
        "tolerance": 2,
        "autumn_import": False,
        "context": None,
    }]
