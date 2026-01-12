"""Open the AutumnWeb UI in a browser."""

from __future__ import annotations

import webbrowser

import click

from ..config import get_base_url


@click.command("open")
@click.option("--path", "path_", default="/", help="Path to open (default: /)")
def open_cmd(path_: str) -> None:
    """Open the configured AutumnWeb base URL in your default browser."""
    base = get_base_url().rstrip("/")
    path_ = "/" + str(path_).lstrip("/")
    url = f"{base}{path_}"
    webbrowser.open(url)
    click.echo(url)

