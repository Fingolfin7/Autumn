from __future__ import annotations

import pytest
from click.testing import CliRunner

from autumn_cli.cli import cli


def test_root_help_groups_commands_and_lists_aliases_once() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    for heading in (
        "Timers:",
        "Sessions:",
        "Projects:",
        "Reminders:",
        "Data and reports:",
        "Metadata:",
        "Setup:",
        "Advanced operations:",
    ):
        assert heading in result.output
    assert "Short aliases: cmt=commitments, ls=log, n=note, p=projects," in result.output
    assert "\n  ls " not in result.output
    assert "\n  p  " not in result.output


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (
        ("cmt", "commitments"),
        ("ls", "log"),
        ("n", "note"),
        ("p", "projects"),
        ("subs", "subprojects"),
    ),
)
def test_short_alias_resolves_to_canonical_command(alias: str, canonical: str) -> None:
    runner = CliRunner()

    alias_result = runner.invoke(cli, [alias, "--help"])
    canonical_result = runner.invoke(cli, [canonical, "--help"])

    assert alias_result.exit_code == 0
    assert canonical_result.exit_code == 0
    assert alias_result.output.splitlines()[1:] == canonical_result.output.splitlines()[1:]
