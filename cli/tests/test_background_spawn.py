from __future__ import annotations

from autumn_cli.utils.background import spawn_detached_python_module


def test_spawn_detached_returns_pid():
    # Spawn a trivial module that exits immediately.
    p = spawn_detached_python_module("autumn_cli.commands.reminder_daemon", ["--help"])
    assert hasattr(p, "pid")
    assert isinstance(p.pid, int)

