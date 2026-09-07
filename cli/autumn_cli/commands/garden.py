"""Read-only project woodland, drawn with Rich and the standard library."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

import click
from rich.console import Console

from ..api_client import APIClient, APIError


def _parse_day(ctx, param, value):
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError:
        raise click.BadParameter("use YYYY-MM-DD", ctx=ctx, param=param) from None


@click.command()
@click.option("--project", "-p", help="Focus on one project (exact name or unique partial name).")
@click.option("--at", callback=_parse_day, metavar="YYYY-MM-DD", help="Grow only from saved history through this local date.")
@click.option("--all", "show_all", is_flag=True, help="Walk the entire woodland, including seeds and dormant projects.")
@click.option("--limit", type=click.IntRange(1, 200), default=8, show_default=True, help="Number of recently visited projects to show.")
@click.option("--page", type=click.IntRange(1), default=1, show_default=True, help="Walk to another clearing, ordered by recent visits.")
@click.option("--season", type=click.Choice(["auto", "spring", "summer", "autumn", "winter"]), default="auto", show_default=True, help="Override the seasonal palette.")
@click.option("--hemisphere", type=click.Choice(["north", "south"]), default="north", show_default=True, help="Calendar used by the automatic season.")
@click.option("--species", type=click.Choice(["oak", "pine", "birch", "willow", "flowers", "fern"]), help="Try a different plant in a --project view (this display only).")
@click.option("--width", type=click.IntRange(32, 180), help="Scene width in terminal columns (otherwise fits the terminal).")
@click.option("--ascii", "ascii_only", is_flag=True, help="Use ASCII characters for the illustration.")
@click.option("--color/--no-color", default=None, help="Force or disable colour; by default follow the terminal and NO_COLOR.")
@click.option("--save", type=click.Path(path_type=Path, dir_okay=False), metavar="PATH", help="Also save this view as .svg, .html, or .txt.")
@click.option("--from-file", "source", type=click.Path(exists=True, dir_okay=False, path_type=Path), metavar="EXPORT.json", help="Use a format-2 export offline instead of fetching live history.")
def garden(project, at, show_all, limit, page, season, hemisphere, species, width,
           ascii_only, color, save, source):
    """Visit a colourful woodland grown from your project history.

    Saved time grows six kinds of plants. Older projects keep their growth;
    completed projects receive a small keepsake. No AI, new dependencies, or
    changes to your Autumn data. The default clearing contains eight projects.

    Examples:

      autumn garden

      autumn garden --project AutumnWeb

      autumn garden --at 2026-01-01 --season winter

      autumn garden --all --save woodland.svg
    """
    if species and not project:
        raise click.UsageError("--species needs --project so it changes only one plant.")
    if project and show_all:
        raise click.UsageError("Choose either --project or --all.")
    if page != 1 and (project or show_all):
        raise click.UsageError("--page cannot be combined with --project or --all.")
    if at and at > date.today():
        raise click.BadParameter("choose today or an earlier date; future growth is unknown", param_hint="--at")
    if save and save.suffix.lower() not in (".svg", ".html", ".txt"):
        raise click.BadParameter("use a .svg, .html, or .txt filename", param_hint="--save")

    # Keep routine CLI startup small. This feature has no chart-extra imports.
    from ..utils.garden_model import build_garden, sanitize_text
    from ..utils.garden_render import GARDEN_THEME, render_garden, season_for

    try:
        identities = None
        if source:
            with source.open(encoding="utf-8-sig") as stream:
                data = json.load(stream)
        else:
            client = APIClient()
            data = client.export_data()
            # Export v2 preserves session UUIDs but omits project IDs. A small
            # second GET supplies identities so renaming a project keeps its tree.
            metadata = client.list_projects_flat(compact=False)
            identities = {
                item["name"]: item["id"] for item in metadata.get("projects", [])
                if isinstance(item, dict) and item.get("id") is not None and item.get("name")
            }
        # A naive local "now" lets each historical timestamp resolve through
        # the OS timezone rules, instead of freezing today's UTC/DST offset.
        snapshot = build_garden(data, at=at, now=datetime.now(), identities=identities)
    except (APIError, ValueError, OSError) as error:
        raise click.ClickException(sanitize_text(str(error))) from None

    plants = snapshot.plants
    if project:
        query = sanitize_text(project).casefold()
        exact = [plant for plant in plants if plant.name.casefold() == query]
        matches = exact or [plant for plant in plants if query in plant.name.casefold()]
        if not matches:
            raise click.ClickException(f"No project matching '{sanitize_text(project)}' in this view.")
        if len(matches) > 1:
            names = ", ".join(plant.name for plant in matches[:8])
            raise click.ClickException(f"Several projects match: {names}. Use an exact name.")
        plants = matches
    elif not show_all:
        offset = (page - 1) * limit
        if page > 1 and offset >= len(plants):
            raise click.ClickException(f"No clearing on page {page}; this view has {len(plants)} projects.")
        plants = plants[offset:offset + limit]

    # Unlike the shared report console (fixed at 200), a garden should fit the
    # actual viewport. Redirection uses a predictable 80-column default.
    natural_width = Console().width
    scene_width = width or min(132, max(32, natural_width))
    use_color = color if color is not None else (False if "NO_COLOR" in os.environ else None)
    output = Console(width=scene_width, record=bool(save),
                     force_terminal=use_color, no_color=use_color is False,
                     color_system="truecolor" if use_color is True else "auto")
    chosen_season = season_for(snapshot.day, hemisphere) if season == "auto" else season
    render_garden(output, snapshot, plants, season=chosen_season,
                  ascii_only=ascii_only, total=len(snapshot.plants),
                  focused=bool(project), species_override=species, hemisphere=hemisphere,
                  offset=(page - 1) * limit, page_size=limit)

    if save:
        try:
            if save.suffix.lower() == ".svg":
                svg = output.export_svg(title="Autumn / Garden", theme=GARDEN_THEME)
                # Rich's default SVG embeds a CDN font URL. Keep this keepsake
                # fully offline and use the viewer's installed monospace font.
                svg = re.sub(r"\s*@font-face\s*\{.*?\}", "", svg, flags=re.S)
                svg = svg.replace("Fira Code, monospace", "'Cascadia Mono', Consolas, monospace")
                save.write_text(svg, encoding="utf-8")
            elif save.suffix.lower() == ".html":
                output.save_html(str(save), theme=GARDEN_THEME, inline_styles=True)
            else:
                output.save_text(str(save))
        except OSError as error:
            raise click.ClickException(f"Could not save garden: {sanitize_text(str(error))}") from None
        # Keep the path literal and unwrapped, and outside the picture itself.
        click.echo(f"Saved garden to {sanitize_text(str(save.resolve()))}", err=True)
