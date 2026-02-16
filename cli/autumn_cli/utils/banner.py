"""Utilities for rendering the Autumn CLI banner.

We need to measure *display width* in terminal cells (not Python's len()), since
emoji and some Unicode characters are wider than one column.

Important: when strings include Rich markup (e.g. "[bold]"), we must measure the
*rendered* width, not the raw text width.
"""

from __future__ import annotations

from rich.console import Console
from rich.measure import Measurement
from rich.text import Text


def cell_len(s: str, *, console: Console) -> int:
    """Return the display width of a *plain* string in terminal cells."""
    measurement = console.measure(Text(s))
    return int(measurement.maximum)


def cell_len_markup(s: str, *, console: Console) -> int:
    """Return the display width (cells) of a string containing Rich markup."""
    text = Text.from_markup(s)
    measurement: Measurement = console.measure(text)
    return int(measurement.maximum)


def pad_right(s: str, width: int, *, console: Console) -> str:
    """Pad a plain string on the right with spaces to reach a target cell width."""
    cur = cell_len(s, console=console)
    if cur >= width:
        return s
    return s + (" " * (width - cur))


def pad_right_markup(s: str, width: int, *, console: Console) -> str:
    """Pad a Rich-markup string on the right with spaces to reach a target cell width."""
    cur = cell_len_markup(s, console=console)
    if cur >= width:
        return s
    return s + (" " * (width - cur))
