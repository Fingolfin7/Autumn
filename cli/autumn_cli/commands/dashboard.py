from __future__ import annotations
import click
import threading
import time
from datetime import datetime

from rich.live import Live
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.history import InMemoryHistory

from ..api_client import APIClient
from ..utils.console import console as autumn_console
from ..utils.dashboard.state import DashboardState
from ..utils.dashboard.panels import render_dashboard
from ..utils.dashboard.shell import execute_command


@click.command()
def dash():
    """Launch the interactive Autumn Dashboard."""
    client = APIClient()
    state = DashboardState(client)

    # Initial data fetch
    state.add_log("Dashboard starting...")
    state.refresh(force=True)

    session = PromptSession(history=InMemoryHistory())

    def refresh_loop(live: Live):
        while True:
            try:
                state.refresh()
                live.update(render_dashboard(state))
            except Exception as e:
                state.add_log(f"UI Error: {str(e)}")
            time.sleep(1)

    with patch_stdout():
        # Pass the themed autumn_console to Live
        with Live(
            render_dashboard(state),
            console=autumn_console,
            auto_refresh=False,
            screen=True,
        ) as live:
            # Start background refresh thread
            thread = threading.Thread(target=refresh_loop, args=(live,), daemon=True)
            thread.start()

            # Main input loop
            while True:
                try:
                    # session.prompt will show up at the bottom
                    cmd = session.prompt("autumn> ")
                    if cmd.strip():
                        execute_command(cmd, state)
                        # Immediate update after command
                        live.update(render_dashboard(state))
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
                except Exception as e:
                    state.add_log(f"Input Error: {str(e)}")

    click.echo("Dashboard closed.")
