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
    import os

    if os.name == "nt":
        # This enables VT100/ANSI processing on Windows consoles
        os.system("")

    # We use the configured console but ensure it's in terminal mode for the TUI
    from rich.console import Console
    from ..utils.console import THEME

    # Create a fresh console for the dashboard that forces terminal support
    dash_console = Console(theme=THEME, force_terminal=True)

    client = APIClient()
    state = DashboardState(client)

    # Initial data fetch
    state.add_log("Dashboard starting...")
    try:
        state.refresh(force=True)
    except Exception as e:
        state.add_log(f"Startup Refresh Error: {str(e)}")

    session = PromptSession(history=InMemoryHistory())

    def refresh_loop(live: Live):
        while True:
            try:
                state.refresh()
                live.update(render_dashboard(state))
            except Exception as e:
                # We don't want to crash the refresh thread
                pass
            time.sleep(1)

    # Use patch_stdout to allow prompt_toolkit and rich to coexist
    with patch_stdout():
        # We'll use screen=False first as it's more compatible with Legacy Windows terminals.
        # It will re-print the dashboard in the same spot.
        with Live(
            render_dashboard(state),
            console=dash_console,
            auto_refresh=True,
            refresh_per_second=4,
            screen=False,
        ) as live:
            # Start background refresh thread
            thread = threading.Thread(target=refresh_loop, args=(live,), daemon=True)
            thread.start()

            # Main input loop
            while True:
                try:
                    # session.prompt will show up below the dashboard
                    cmd = session.prompt("autumn> ")
                    if cmd.strip():
                        execute_command(cmd, state)
                        # The Live display will naturally pick up state changes via refresh_loop or manual trigger
                        live.update(render_dashboard(state))
                except (KeyboardInterrupt, EOFError):
                    break
                except Exception as e:
                    state.add_log(f"Input Error: {str(e)}")

    click.echo("Dashboard closed.")
