"""Shared Rich console and output helpers.

We centralize console + styles here so all commands have a consistent look.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.theme import Theme


THEME = Theme(
    {
        # Old CLI exact-ish mapping:
        # - [cyan] => cyan
        # - [bright red] => bright_red
        # - [yellow] => yellow
        # - [_text256_26_] => color(26)
        # - [_text256_34_] => color(34)
        "autumn.title": "bold",  # underline applied in markup
        "autumn.label": "yellow",
        "autumn.muted": "dim",
        "autumn.ok": "bright_green",
        "autumn.warn": "yellow",
        "autumn.err": "bright_red",
        "autumn.project": "bright_red",
        "autumn.subproject": "color(26)",
        "autumn.note": "yellow",
        "autumn.time": "color(34)",
        "autumn.id": "dim",
        # Project status colors
        "autumn.status.active": "bold bright_green",
        "autumn.status.paused": "bold yellow",
        "autumn.status.complete": "bold bright_blue",
        "autumn.status.archived": "dim",
        "autumn.description": "italic dim",
        "autumn.user": "bold color(208)",  # autumn-orange
    }
)


console = Console(theme=THEME)


@dataclass(frozen=True)
class StatusStyles:
    active: str = "autumn.ok"
    inactive: str = "autumn.muted"
    error: str = "autumn.err"


styles = StatusStyles()

