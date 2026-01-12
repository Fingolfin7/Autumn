"""Interactive pickers for optional CLI prompting.

These are *opt-in* (used only when commands pass pick=True).
We keep it simple and dependency-free (Click prompts + numbered lists).
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import click


def pick_from_names(
    *,
    label: str,
    names: Sequence[str],
    default: Optional[str] = None,
) -> Optional[str]:
    """Prompt user to pick a value from a list.

    Returns the selected name or None if no options.
    """
    cleaned = [n for n in names if n]
    if not cleaned:
        return None

    # Print numbered list
    click.echo(f"Select {label}:")
    for i, n in enumerate(cleaned, start=1):
        click.echo(f"  {i}) {n}")

    while True:
        raw = click.prompt(
            f"{label} number",
            default=str(cleaned.index(default) + 1) if default in cleaned else None,
            show_default=default in cleaned,
        )
        try:
            idx = int(str(raw).strip())
            if 1 <= idx <= len(cleaned):
                return cleaned[idx - 1]
        except Exception:
            pass
        click.echo(f"Please enter a number between 1 and {len(cleaned)}")


def normalize_repeatable(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        s = str(v).strip()
        if s:
            out.append(s)
    return out

