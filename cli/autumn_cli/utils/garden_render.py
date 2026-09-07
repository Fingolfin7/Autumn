"""A tiny, deterministic woodland drawn entirely in terminal cells.

No plotting stack, image assets, saved game state, or random global state. The
same plant identity, growth stage, and season produce the same tree.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text
from rich.terminal_theme import TerminalTheme

if TYPE_CHECKING:
    from .garden_model import GardenSnapshot, Plant


GARDEN_THEME = TerminalTheme(
    (19, 28, 29), (222, 223, 202),
    [(19, 28, 29), (194, 104, 76), (135, 163, 109), (231, 182, 98),
     (135, 170, 184), (183, 154, 182), (143, 183, 170), (222, 223, 202)],
)


@dataclass(frozen=True)
class Palette:
    leaves: tuple[str, ...]
    evergreen: tuple[str, ...]
    bloom: str
    earth: str
    accent: str
    sky: str
    line: str


PALETTES = {
    "spring": Palette(("#729660", "#93b773", "#b4cc88", "#d3dda4"),
                      ("#507f70", "#679f7b", "#91b693"), "#e1a5b3",
                      "#a79573", "#bbcf89", "#b4ced0", "#64796a"),
    "summer": Palette(("#4f805d", "#6b9a63", "#8ab373", "#b1c887"),
                      ("#467a67", "#639577", "#8bae80"), "#edd188",
                      "#ac9472", "#b6cc8c", "#a7c6d5", "#637966"),
    "autumn": Palette(("#987c4d", "#be8c4c", "#e3ab59", "#edc981", "#b96849"),
                      ("#557d69", "#779271", "#a7b183"), "#eccb83",
                      "#ad9072", "#e3b46e", "#b0bec6", "#727b64"),
    "winter": Palette(("#8199a0", "#afc0c0", "#d6deda", "#edf0e5"),
                      ("#537772", "#78968c", "#bfcebf"), "#e1b38b",
                      "#9da9a6", "#c2d5d7", "#c2d5d7", "#708b8c"),
}

SPECIES_LABELS = {"oak": "oak", "pine": "pine", "birch": "birch",
                  "willow": "willow", "flowers": "wildflowers", "fern": "fern"}
STAGES = ("seed", "seedling", "sapling", "established", "mature")
SEASON_LINES = {
    "spring": "New leaves. Old roots. Room to begin again.",
    "summer": "A little shade, grown from days well spent.",
    "autumn": "Some things grow quietly. Here is the evidence.",
    "winter": "The season changes. The roots remember.",
}


def season_for(day: date, hemisphere: str = "north") -> str:
    month = ((day.month - 1 + (6 if hemisphere == "south" else 0)) % 12) + 1
    return ("winter", "spring", "summer", "autumn")[(month % 12) // 3]


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    if not seconds:
        return "no saved time"
    if minutes == 0:
        return "<1m recorded"
    if minutes < 60:
        return f"{minutes}m recorded"
    hours, remainder = divmod(minutes, 60)
    return f"{hours:,}h" + (f" {remainder}m" if remainder else "") + " recorded"


class Canvas:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.cells = [[(" ", "") for _ in range(width)] for _ in range(height)]

    def put(self, x: int, y: int, glyph: str, style: str):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = (glyph, style)

    def line(self, x0: int, y0: int, x1: int, y1: int, glyph: str, style: str):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            self.put(round(x0 + (x1 - x0) * step / steps),
                     round(y0 + (y1 - y0) * step / steps), glyph, style)

    def text(self, x: int, y: int, value: str, style: str):
        for offset, glyph in enumerate(value):
            self.put(x + offset, y, glyph, style)

    def rows(self) -> list[Text]:
        rows = []
        for row in self.cells:
            text = Text()
            for glyph, style in row:
                text.append(glyph, style=style)
            rows.append(text)
        return rows


def _draw_plant(canvas: Canvas, plant: Plant, x: int, ground: int,
                palette: Palette, season: str, ascii_only: bool,
                species_override: str | None = None):
    rng = random.Random(plant.seed)
    species = species_override or plant.species
    stage = plant.stage
    bark = "#b4987b"
    pale_bark = "#d4d4bf"
    leaf_colors = palette.evergreen if species in ("pine", "fern") else palette.leaves
    leaf_chars = ("o", "O", "@", ".") if ascii_only else ("█", "▓", "▓", "▒")

    def leaf(px: int, py: int, *, sparse: bool = False):
        # Leaves are positioned with a private RNG: rendering never affects the
        # caller's randomness or depends on Python's process-randomized hash.
        if sparse and rng.random() < .23:
            return
        canvas.put(px, py, rng.choice(leaf_chars), rng.choice(leaf_colors))

    def crown(cx: int, cy: int, rx: float, ry: float):
        for py in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
            for px in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
                distance = ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2
                if distance < .88 + rng.random() * .26:
                    leaf(px, py, sparse=season == "winter" and species != "pine")

    if stage == 0:
        canvas.text(x - 2, ground - 1, "  .  " if ascii_only else "  ◦  ", palette.accent)
        canvas.text(x - 2, ground, "_..._", palette.earth)
        if plant.completed:
            canvas.put(x + 3, ground - 1, "*" if ascii_only else "✦", palette.bloom)
        return
    if stage == 1:
        canvas.text(x - 2, ground - 2, "\\ /", leaf_colors[1])
        canvas.put(x - 1, ground - 1, "|", bark)
        canvas.text(x - 3, ground, "__|__", palette.earth)
        if plant.completed:
            canvas.put(x + 3, ground - 1, "*" if ascii_only else "✦", palette.bloom)
        return

    height = {2: 6, 3: 9, 4: 12}[stage]
    top = ground - height
    if species == "pine":
        canvas.line(x, top + 2, x, ground - 1, "|", bark)
        for tier in range(3):
            tier_top = top + tier * (height // 4)
            tier_height = 3 + stage // 2
            for dy in range(tier_height):
                half = min(9, dy + tier)
                for dx in range(-half, half + 1):
                    leaf(x + dx, tier_top + dy)
                if season == "winter":
                    canvas.put(x - half, tier_top + dy, "." if ascii_only else "▀", "#e3e9dd")
    elif species == "oak":
        canvas.line(x, top + 3, x, ground - 1, "|", bark)
        if stage >= 3:
            canvas.line(x + 1, top + 6, x + 1, ground - 1, "|", bark)
        canvas.line(x, top + 6, x - 4, top + 3, "/", bark)
        canvas.line(x, top + 6, x + 5, top + 3, "\\", bark)
        spread = {2: 3, 3: 5, 4: 6}[stage]
        crown(x - spread // 2, top + 3, spread, 2.1)
        crown(x + spread // 2 + 1, top + 3, spread, 2.3)
        crown(x, top + 1, spread * .8, 1.6)
    elif species == "birch":
        for dx, offset in ((-2, 1), (2, 0)):
            canvas.line(x + dx, top + offset + 1, x + dx, ground - 1, "|", pale_bark)
            for py in range(top + offset + 3, ground - 1, 3):
                canvas.put(x + dx, py, ":", bark)
            crown(x + dx, top + offset + 2, 2 + stage / 2, 2.3)
        if stage >= 3:
            crown(x - 4, top + 5, 2.5, 1.8)
    elif species == "willow":
        canvas.line(x, top + 2, x, ground - 1, "|", bark)
        spread = {2: 4, 3: 6, 4: 8}[stage]
        for dx in range(-spread, spread + 1, 2):
            start = top + 2 + int(abs(dx) / spread * 2)
            end = min(ground - 2, start + stage + rng.randrange(2))
            for py in range(start, end):
                canvas.put(x + dx, py, ":" if ascii_only else "╎", rng.choice(leaf_colors))
        crown(x, top + 2, spread, 2.2)
    elif species == "flowers":
        count = {2: 3, 3: 5, 4: 7}[stage]
        for index in range(count):
            dx = (index - count // 2) * 3
            flower_y = ground - 2 - rng.randint(0, stage + 1)
            canvas.line(x + dx, flower_y + 1, x + dx, ground - 1, "|", palette.evergreen[1])
            canvas.put(x + dx + (-1 if index % 2 else 1), ground - 2,
                       "/" if index % 2 else "\\", palette.evergreen[2])
            canvas.put(x + dx, flower_y, "*" if ascii_only else "✿",
                       palette.bloom if index % 2 else palette.accent)
    else:  # fern: low, spreading fronds, even at maturity
        spread = {2: 4, 3: 7, 4: 10}[stage]
        for direction in (-1, 1):
            previous = (x, ground - 1)
            for dx in range(1, spread + 1):
                py = ground - 1 - round(math.sin(dx / (spread + 2) * math.pi) * (stage + 1))
                canvas.line(*previous, x + direction * dx, py,
                            "/" if direction < 0 else "\\", leaf_colors[1])
                canvas.put(x + direction * dx, py - 1, "v" if ascii_only else "⌁", leaf_colors[2])
                previous = (x + direction * dx, py)
        canvas.put(x, ground - 1, "|", leaf_colors[0])

    canvas.text(x - 2, ground, "_/|\\_" if species not in ("flowers", "fern") else "_..._", palette.earth)
    # Completion is a keepsake, independent of the natural season.
    if plant.completed:
        canvas.put(x + 3, ground - 1, "*" if ascii_only else "✦", palette.bloom)
    if plant.visit_days >= 7:
        canvas.text(x - 7, ground - 1, "n" if ascii_only else "♠", palette.earth)


def _center(text: Text, width: int) -> Text:
    result = text.copy()
    result.truncate(width, overflow="ellipsis")
    result.align("center", width)
    return result


def render_garden(console: Console, snapshot: GardenSnapshot, plants: list[Plant], *,
                  season: str, ascii_only: bool = False, total: int | None = None,
                  focused: bool = False, species_override: str | None = None,
                  hemisphere: str = "north", offset: int = 0, page_size: int = 8) -> None:
    """Write a responsive scene. All user strings are literal Rich Text."""
    palette = PALETTES[season]
    width = console.width
    total = len(snapshot.plants) if total is None else total
    rule = "-" if ascii_only else "─"
    dot = "/" if ascii_only else "·"
    console.print()
    title = Text("  AUTUMN ", style=f"bold {palette.accent}")
    title.append("/ GARDEN", style=palette.sky)
    console.print(title)
    console.print(Text(f"  {snapshot.day.strftime('%d %B %Y')}  {dot}  {season}", style=palette.sky))
    console.print(Text("  " + rule * max(1, width - 4), style=palette.line))
    console.print(Text("  " + SEASON_LINES[season], style=f"italic {palette.accent}"))
    console.print()

    if not plants:
        console.print(Text("  A quiet patch of earth.", style=palette.accent))
        console.print(Text("  No projects to show for this view.", style=palette.sky))
        console.print()
        return

    columns = min(len(plants), max(1, (width - 4) // 27))
    cell_width = (width - 4) // columns
    scene_width = columns * cell_width
    for row_start in range(0, len(plants), columns):
        row_plants = plants[row_start:row_start + columns]
        canvas = Canvas(scene_width, 16)
        ground = 14
        # Quiet ground texture is stable per row, with a seasonal leaf or stone.
        rng = random.Random(snapshot.day.toordinal() // 7 + row_start)
        for px in range(scene_width):
            canvas.put(px, ground, "_" if ascii_only else "─", palette.line)
            if rng.random() < .12:
                canvas.put(px, ground + 1, rng.choice((".", ",", "'")), palette.earth)
        for index, plant in enumerate(row_plants):
            _draw_plant(canvas, plant, index * cell_width + cell_width // 2,
                        ground, palette, season, ascii_only, species_override)
        # Small plants don't need a screenful of empty sky. Keep one breathing
        # row above the tallest plant in each clearing.
        first_ink = next((index for index, row in enumerate(canvas.cells)
                          if any(glyph != " " for glyph, _ in row)), ground)
        for line in canvas.rows()[max(0, first_ink - 1):]:
            console.print(Text("  ") + line, soft_wrap=True)
        wrapped_names = [Text(plant.name, style="bold").wrap(console, cell_width - 2, overflow="fold")
                         for plant in row_plants]
        name_height = min(2, max(len(lines) for lines in wrapped_names))
        for index in range(name_height):
            line = Text("  ")
            for name_lines in wrapped_names:
                part = name_lines[index] if index < len(name_lines) else Text()
                if index == 1 and len(name_lines) > 2:
                    part = Text(str(part) + ("..." if ascii_only else "…"), style="bold")
                line.append_text(_center(part, cell_width))
            console.print(line, soft_wrap=True)
        line = Text("  ")
        for plant in row_plants:
            species = species_override or plant.species
            label = f"{STAGES[plant.stage]} {SPECIES_LABELS[species]}"
            if plant.completed:
                label += " *" if ascii_only else " ✦"
            line.append_text(_center(Text(label, style=palette.accent), cell_width))
        console.print(line, soft_wrap=True)
        line = Text("  ")
        for plant in row_plants:
            label = _duration(plant.total_seconds)
            line.append_text(_center(Text(label, style=palette.sky), cell_width))
        console.print(line, soft_wrap=True)
        console.print()

    if focused:
        plant = plants[0]
        console.print(Text("  " + rule * max(1, width - 4), style=palette.line))
        count = plant.session_count
        console.print(Text(f"  {count:,} saved session{'s' if count != 1 else ''}  {dot}  "
                           f"{plant.visit_days:,} visited day{'s' if plant.visit_days != 1 else ''}", style=palette.sky))
        if plant.first_session:
            console.print(Text("  First visit  " + plant.first_session.strftime("%d %b %Y"), style=palette.sky))
        if plant.last_session:
            last_day = min(plant.last_session.date(), snapshot.day)
            console.print(Text("  Last visit   " + last_day.strftime("%d %b %Y"), style=palette.sky))
        if plant.latest_note:
            console.print()
            console.print(Text("  A note left here", style=palette.accent))
            # A close-up is a keepsake, not an unbounded log dump.
            note = " ".join(plant.latest_note.split())
            if len(note) > 280:
                note = note[:277] + "..."
            console.print(Text("  " + note, style="italic"))
        console.print()
    else:
        visitors = (
            ("A fox takes the long way home.", " /\\_/\\"),
            ("A snail has made no plans to hurry.", "  @)_"),
            ("A small bird approves of the branches.", "  (o>"),
            ("Somewhere in the leaves, a beetle.", "  (o)"),
        )
        visitor, drawing = visitors[snapshot.day.toordinal() % len(visitors)]
        console.print(Text("  " + drawing, style=palette.earth))
        console.print(Text("  " + visitor, style=f"italic {palette.sky}"))
        console.print()
        if len(plants) < total:
            console.print(Text(f"  Projects {offset + 1}-{offset + len(plants)} of {total}, recent visits first.", style=palette.sky))
            if offset + len(plants) < total:
                next_page = offset // page_size + 2
                paging = f"autumn garden --page {next_page}"
                if page_size != 8:
                    paging += f" --limit {page_size}"
                if snapshot.historical:
                    paging += f" --at {snapshot.day.isoformat()}"
                console.print(Text("  Next: " + paging, style=palette.sky))
            console.print(Text("  Explore: autumn garden --all", style=palette.sky))
        else:
            console.print(Text(f"  {len(plants)} project{'s' if len(plants) != 1 else ''} in this clearing.", style=palette.sky))
    if any(plant.completed for plant in plants):
        console.print(Text("  " + ("*" if ascii_only else "✦") + " A completed project's keepsake.", style=palette.accent))
    if snapshot.historical:
        console.print(Text("  Rebuilt through this date from the saved history available now.", style=palette.sky))
        console.print(Text("  Names/notes reflect later edits; past completion is unknown.", style=palette.sky))
    console.print(Text("  Time away never takes growth away.", style=f"italic {palette.accent}"))
    if snapshot.skipped_sessions:
        console.print(Text(f"  Full history: {snapshot.skipped_sessions} open, duplicate or invalid records omitted.", style=palette.sky))
    console.print()
