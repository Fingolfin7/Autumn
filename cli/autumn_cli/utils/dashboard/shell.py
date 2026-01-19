from __future__ import annotations
import io
import sys
import shlex
from typing import TYPE_CHECKING
import click

if TYPE_CHECKING:
    from .state import DashboardState


def execute_command(command_str: str, state: DashboardState):
    """Execute an autumn command string and capture its output."""
    if not command_str.strip():
        return

    # Special case: quit
    if command_str.strip() in ("q", "quit", "exit"):
        sys.exit(0)

    # Split command into tokens
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        state.add_log(f"Error parsing command: {str(e)}")
        return

    # Handle 'autumn ' prefix if present
    if args and args[0] == "autumn":
        args = args[1:]

    from ...cli import cli

    # Redirect stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    try:
        # Run the command
        # standalone_mode=False prevents click from calling sys.exit() on completion
        cli.main(args=args, prog_name="autumn", standalone_mode=False)

        # Capture output
        output = sys.stdout.getvalue().strip()
        if output:
            for line in output.splitlines():
                if line.strip():
                    state.add_log(line)

        # Capture errors
        errors = sys.stderr.getvalue().strip()
        if errors:
            for line in errors.splitlines():
                if line.strip():
                    state.add_log(f"Error: {line}")

        # Trigger an immediate refresh for state-changing commands
        state.refresh(force=True)

    except click.ClickException as e:
        state.add_log(f"Error: {e.format_message()}")
    except click.Abort:
        state.add_log("Aborted.")
    except Exception as e:
        state.add_log(f"System Error: {str(e)}")
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
