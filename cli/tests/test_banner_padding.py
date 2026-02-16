from __future__ import annotations

from rich.console import Console

from autumn_cli.utils.banner import cell_len_markup, pad_right_markup


def test_pad_right_markup_produces_exact_cell_width_for_emoji_and_markup() -> None:
    console = Console(width=120, force_terminal=True, color_system=None)

    title_line = "  🍁 [bold]autumn[/]"
    greeting_line = "  Good afternoon [bold]Henry[/]! Back to Daily Summaries."

    width = max(
        cell_len_markup(title_line, console=console),
        cell_len_markup(greeting_line, console=console),
    )

    padded_title = pad_right_markup(title_line, width, console=console)
    padded_greeting = pad_right_markup(greeting_line, width, console=console)

    assert cell_len_markup(padded_title, console=console) == width
    assert cell_len_markup(padded_greeting, console=console) == width


def test_pad_right_markup_handles_apostrophes() -> None:
    console = Console(width=200, force_terminal=True, color_system=None)

    s = "  Afternoon Henry! Daily Summaries time. Let's go!"
    width = cell_len_markup(s, console=console) + 5

    padded = pad_right_markup(s, width, console=console)
    assert cell_len_markup(padded, console=console) == width
