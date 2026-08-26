"""Regression tests for lightweight CLI startup imports."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


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
