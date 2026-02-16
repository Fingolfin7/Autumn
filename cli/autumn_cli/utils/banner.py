"""Utilities for rendering the Autumn CLI banner.

We need to measure *display width* in terminal cells, not Python's `len()`, since:
- emoji can be double-width
- Rich markup like `[bold]` has zero display width

This module intentionally stays tiny: only the helpers the CLI uses.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text


def cell_len_markup(s: str, *, console: Console) -> int:
    """Return the display width (cells) of a string containing Rich markup."""
    measurement = console.measure(Text.from_markup(s))
    return int(measurement.maximum)


def pad_right_markup(s: str, width: int, *, console: Console) -> str:
    """Pad a Rich-markup string on the right with spaces to reach a target cell width."""
    cur = cell_len_markup(s, console=console)
    if cur >= width:
        return s
    return s + (" " * (width - cur))
