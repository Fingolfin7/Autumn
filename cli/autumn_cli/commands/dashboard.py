from __future__ import annotations
import click
import threading
import time
from datetime import datetime

from rich.live import Live
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition

from ..api_client import APIClient
from ..utils.console import console as autumn_console
from ..utils.dashboard.state import DashboardState
from ..utils.dashboard.panels import render_dashboard
from ..utils.dashboard.shell import execute_command


@click.command()
def dash():
    """Launch the interactive Autumn Dashboard."""
    import os
    import sys

    # Force ANSI support on Windows if possible
    if os.name == "nt":
        # Enable VT mode in Windows 10+
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    from rich.console import Console
    from ..utils.console import THEME

    # Let Rich detect the terminal capabilities naturally
    dash_console = Console(theme=THEME, file=sys.stdout)

    client = APIClient()
    state = DashboardState(client)

    # Initial data fetch
    state.add_log("Dashboard starting...")
    try:
        state.refresh(force=True)
    except Exception as e:
        state.add_log(f"Startup Refresh Error: {str(e)}")

    # Define key bindings for hotkeys
    kb = KeyBindings()

    @Condition
    def is_buffer_empty():
        from prompt_toolkit.application import get_app

        return not get_app().current_buffer.text

    @kb.add("left", filter=is_buffer_empty)
    def _(event):
        state.week_offset -= 1
        state.refresh(force=True)

    @kb.add("right", filter=is_buffer_empty)
    def _(event):
        state.week_offset += 1
        state.refresh(force=True)

    @kb.add("[", filter=is_buffer_empty)
    def _(event):
        state.week_offset -= 1
        state.refresh(force=True)

    @kb.add("]", filter=is_buffer_empty)
    def _(event):
        state.week_offset += 1
        state.refresh(force=True)

    @kb.add("t", filter=is_buffer_empty)
    def _(event):
        state.week_offset = 0
        state.refresh(force=True)

    @kb.add("r", filter=is_buffer_empty)
    def _(event):
        state.refresh(force=True)

    @kb.add("q", filter=is_buffer_empty)
    def _(event):
        event.app.exit()

    session = PromptSession(history=InMemoryHistory(), key_bindings=kb)

    def data_refresh_loop():
        while True:
            try:
                # state.refresh handles its own 60s throttling internally
                state.refresh()
            except Exception:
                pass
            time.sleep(10)

    def ui_refresh_loop(live: Live):
        while True:
            try:
                # Update the display (rebuilds layout for ticking clock)
                live.update(render_dashboard(state))
            except Exception:
                pass
            time.sleep(0.5)  # 2 FPS is plenty for a ticking clock

    # Use patch_stdout to allow prompt_toolkit and rich to coexist
    with patch_stdout():
        # auto_refresh=False gives us manual control to reduce flickering
        with Live(
            render_dashboard(state),
            console=dash_console,
            auto_refresh=False,
            screen=True,
        ) as live:
            # Start background data thread
            data_thread = threading.Thread(target=data_refresh_loop, daemon=True)
            data_thread.start()

            # Start background UI thread
            ui_thread = threading.Thread(
                target=ui_refresh_loop, args=(live,), daemon=True
            )
            ui_thread.start()

            # Main input loop
            while True:
                try:
                    cmd = session.prompt("autumn> ")
                    if cmd.strip():
                        execute_command(cmd, state)
                        # Manual update after command execution
                        live.update(render_dashboard(state))
                except (KeyboardInterrupt, EOFError):
                    break
                except Exception as e:
                    state.add_log(f"Input Error: {str(e)}")

    click.echo("Dashboard closed.")
