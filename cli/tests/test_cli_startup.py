"""Regression tests for lightweight CLI startup imports."""

from __future__ import annotations

import json
import builtins
from pathlib import Path
import subprocess
import sys

from click.testing import CliRunner

from autumn_cli.commands.charts import chart


HEAVY_CHART_MODULES = ("matplotlib", "numpy", "pandas", "seaborn")
CLI_ROOT = Path(__file__).resolve().parents[1]


def _modules_loaded_by(statement: str) -> set[str]:
    script = (
        "import json, sys; "
        f"{statement}; "
        "print(json.dumps(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=CLI_ROOT,
    )
    return set(json.loads(result.stdout))


def test_importing_cli_does_not_load_plotting_stack() -> None:
    loaded = _modules_loaded_by("import autumn_cli.cli")

    for module_name in HEAVY_CHART_MODULES:
        assert module_name not in loaded


def test_chart_help_does_not_load_plotting_stack() -> None:
    loaded = _modules_loaded_by(
        "from click.testing import CliRunner; "
        "from autumn_cli.commands.charts import chart; "
        "result = CliRunner().invoke(chart, ['--help']); "
        "assert result.exit_code == 0"
    )

    for module_name in HEAVY_CHART_MODULES:
        assert module_name not in loaded


def test_chart_missing_extra_fails_before_api_request(monkeypatch) -> None:
    class _UnexpectedClient:
        def __init__(self):
            raise AssertionError("chart tried the API before checking dependencies")

    real_import = builtins.__import__

    def import_without_matplotlib(name, *args, **kwargs):
        if name == "utils.charts":
            raise ModuleNotFoundError(
                "No module named 'matplotlib'", name="matplotlib"
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_matplotlib)
    monkeypatch.setattr("autumn_cli.commands.charts.APIClient", _UnexpectedClient)

    result = CliRunner().invoke(chart)

    assert result.exit_code == 1
    assert 'python -m pip install -e ".[charts]"' in result.output
    assert "Traceback" not in result.output


def test_chart_does_not_mask_internal_missing_module(monkeypatch) -> None:
    real_import = builtins.__import__

    def import_with_internal_failure(name, *args, **kwargs):
        if name == "utils.charts":
            raise ModuleNotFoundError(
                "No module named 'autumn_cli.utils.chart_bug'",
                name="autumn_cli.utils.chart_bug",
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_with_internal_failure)

    result = CliRunner().invoke(chart)

    assert result.exit_code == 1
    assert isinstance(result.exception, ModuleNotFoundError)
    assert "optional dependencies" not in result.output
