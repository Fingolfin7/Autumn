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
    cmd = command_str.strip()
    if not cmd:
        return

    # Special case: quit
    if cmd in ("q", "quit", "exit"):
        sys.exit(0)

    # Dashboard-specific commands
    if cmd in ("prev", "p", "["):
        state.week_offset -= 1
        state.add_log(f"Viewing week offset: {state.week_offset}")
        state.refresh(force=True)
        return
    if cmd in ("next", "n", "]"):
        state.week_offset += 1
        state.add_log(f"Viewing week offset: {state.week_offset}")
        state.refresh(force=True)
        return
    if cmd in ("today", "t", "."):
        state.week_offset = 0
        state.add_log("Viewing current week")
        state.refresh(force=True)
        return

    # Split command into tokens
    try:
        args = shlex.split(cmd)
    except ValueError as e:
        state.add_log(f"Error parsing command: {str(e)}")
        return

    # Handle 'autumn ' prefix if present
    if args and args[0] == "autumn":
        args = args[1:]

    from ...cli import cli

    # Redirect stdout and stderr
    # We use a wrapper that captures but also strips ANSI codes if we want clean logs,
    # or keeps them if the log panel can render them.
    # For now, let's just capture everything.
    buf = io.StringIO()

    # We use click's BaseCommand.main which handles the execution flow
    try:
        # We wrap the call in a way that captures output correctly
        with click.Context(cli, terminal_width=80) as ctx:
            # We need to mock the stdout for the click context
            # Click commands often use click.echo which uses the context's stdout
            with patch_click_echo(buf):
                try:
                    cli.main(args=args, prog_name="autumn", standalone_mode=False)
                except SystemExit:
                    # click commands sometimes call sys.exit
                    pass

        # Capture output from our buffer
        output = buf.getvalue().strip()
        if output:
            state.add_log(output)

        # Trigger an immediate refresh for state-changing commands
        # (Wait a tiny bit for the server to process if it's a start/stop)
        time.sleep(0.1)
        state.refresh(force=True)

    except click.ClickException as e:
        state.add_log(f"Error: {e.format_message()}")
    except click.Abort:
        state.add_log("Aborted.")
    except Exception as e:
        state.add_log(f"System Error: {str(e)}")


def patch_click_echo(stream):
    """A context manager to patch click.echo's destination."""
    import contextlib

    original_echo = click.echo

    def mocked_echo(message=None, file=None, nl=True, err=False, color=None):
        # Always write to our stream instead of the original destination
        original_echo(message, file=stream, nl=nl, err=err, color=color)

    @contextlib.contextmanager
    def patch():
        click.echo = mocked_echo
        try:
            yield
        finally:
            click.echo = original_echo

    return patch()
