from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.cli import cli


class _EmptyMetadataClient:
    def list_contexts(self, *, compact: bool):
        return {"contexts": []}

    def list_tags(self, *, compact: bool):
        return {"tags": []}


def test_context_without_subcommand_lists_contexts(monkeypatch) -> None:
    monkeypatch.setattr(
        "autumn_cli.utils.reminders_registry.check_reminders_health", lambda: []
    )
    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _EmptyMetadataClient)

    result = CliRunner().invoke(cli, ["context"])

    assert result.exit_code == 0
    assert "No contexts found." in result.output


def test_tag_without_subcommand_lists_tags(monkeypatch) -> None:
    monkeypatch.setattr(
        "autumn_cli.utils.reminders_registry.check_reminders_health", lambda: []
    )
    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _EmptyMetadataClient)

    result = CliRunner().invoke(cli, ["tag"])

    assert result.exit_code == 0
    assert "No tags found." in result.output
