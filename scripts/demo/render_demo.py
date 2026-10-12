"""Record the README demo GIF by running real `autumn` commands.

Each command runs against whatever account AUTUMN_API_BASE/AUTUMN_API_KEY
point at (use a throwaway server seeded by seed_demo.py, and a throwaway
HOME so your own config is untouched). Its coloured output is drawn into
terminal-style frames with Pillow and saved as an animated GIF.

    python render_demo.py ../../docs/demo.gif

The commands change data (note, stop, track), so reseed before re-recording.
Captured output is kept next to the GIF (``demo.json``); add ``--from-cache``
to redraw the frames from it without running anything.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

COLS = 100

# Screens are cleared between groups, like pressing Ctrl+L.
SCREENS = [
    [
        "autumn status",
        'autumn note "Found a rhyme for Eärendil. Bilbo is unconvinced."',
        "autumn stop",
    ],
    [
        'autumn track narsil 1h --start "yesterday 17:00" -n "Re-wrapped the hilt"',
        "autumn log yesterday",
    ],
    ["autumn log -q bilbo"],
    ["autumn cmt"],
    ["autumn garden --limit 3"],
]

PROMPT = [("imladris", "#c08a3e"), (" ❯ ", "#7a7064")]

# Warm dark theme: background, foreground, then the 8 normal and 8 bright colours.
BACKGROUND = (28, 26, 23)
FOREGROUND = (230, 220, 203)
NORMAL = [(40, 37, 33), (224, 108, 90), (156, 197, 107), (229, 181, 103),
          (111, 168, 220), (199, 146, 234), (108, 196, 196), (230, 220, 203)]
BRIGHT = [(110, 102, 92), (240, 128, 110), (176, 214, 128), (240, 200, 124),
          (140, 190, 235), (214, 170, 245), (130, 214, 214), (250, 244, 232)]

FONT_SIZE = 16
LINE_HEIGHT = 22
PADDING = 22
TITLE_BAR = 34
FONT_PATHS = [
    "C:/Windows/Fonts/CascadiaMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
FALLBACK_PATHS = [
    "C:/Windows/Fonts/seguisym.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def run_autumn_in_process(args: List[str]) -> None:
    """--exec mode: run the CLI with colour forced on at a fixed width."""
    os.environ.update(FORCE_COLOR="1", COLORTERM="truecolor", COLUMNS=str(COLS),
                      TERM="xterm-256color")
    import rich.console

    rich.console.detect_legacy_windows = lambda: False  # output is a pipe, not a console
    from autumn_cli.utils import console as autumn_console

    for con in (autumn_console.console, autumn_console.err_console):
        con.legacy_windows = False
        con.width = COLS
    from autumn_cli.cli import main

    sys.argv = ["autumn", *args]
    main()


def capture(command: str) -> str:
    import shlex

    args = shlex.split(command)[1:]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    result = subprocess.run(
        [sys.executable, __file__, "--exec", *args],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
    )
    output = result.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if result.returncode != 0:
        sys.exit(f"`{command}` failed:\n{output}")
    return output.rstrip("\n")


# --- drawing ------------------------------------------------------------------------

Run = Tuple[str, "CellStyle"]


@dataclass(frozen=True)
class CellStyle:
    fg: Tuple[int, int, int] = FOREGROUND
    bg: Optional[Tuple[int, int, int]] = None
    bold: bool = False
    underline: bool = False


def _hex(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def ansi_lines(text: str) -> List[List[Run]]:
    """Turn ANSI output into lines of (text, style) runs."""
    from rich.style import Style
    from rich.terminal_theme import TerminalTheme
    from rich.text import Text

    theme = TerminalTheme(BACKGROUND, FOREGROUND, NORMAL, BRIGHT)
    lines: List[List[Run]] = []
    for line in Text.from_ansi(text).split("\n", allow_blank=True):
        plain = line.plain[:COLS]
        styles = [Style.null()] * len(plain)
        for span in line.spans:
            for i in range(span.start, min(span.end, len(plain))):
                span_style = span.style if isinstance(span.style, Style) else Style.parse(span.style)
                styles[i] = styles[i] + span_style
        runs: List[Run] = []
        for char, style in zip(plain, styles):
            fg = style.color.get_truecolor(theme) if style.color else None
            bg = style.bgcolor.get_truecolor(theme, foreground=False) if style.bgcolor else None
            fg = tuple(fg) if fg else FOREGROUND
            bg = tuple(bg) if bg else None
            if style.reverse:
                fg, bg = (bg or BACKGROUND), fg
            if style.dim:
                fg = tuple(int(c * 0.7 + b * 0.3) for c, b in zip(fg, BACKGROUND))
            cell = CellStyle(fg, bg, bool(style.bold), bool(style.underline))
            if runs and runs[-1][1] == cell:
                runs[-1] = (runs[-1][0] + char, cell)
            else:
                runs.append((char, cell))
        lines.append(runs)
    return lines


# Box-drawing characters as (up, down, left, right) weights: 1 light, 2 heavy.
# Drawn as lines so borders join across rows, as they do in a real terminal.
BOX = {
    "─": (0, 0, 1, 1), "━": (0, 0, 2, 2), "│": (1, 1, 0, 0), "┃": (2, 2, 0, 0),
    "┌": (0, 1, 0, 1), "┐": (0, 1, 1, 0), "└": (1, 0, 0, 1), "┘": (1, 0, 1, 0),
    "╭": (0, 1, 0, 1), "╮": (0, 1, 1, 0), "╰": (1, 0, 0, 1), "╯": (1, 0, 1, 0),
    "├": (1, 1, 0, 1), "┤": (1, 1, 1, 0), "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1), "┏": (0, 2, 0, 2), "┓": (0, 2, 2, 0), "┗": (2, 0, 0, 2),
    "┛": (2, 0, 2, 0), "┳": (0, 2, 2, 2), "┻": (2, 0, 2, 2), "┣": (2, 2, 0, 2),
    "┫": (2, 2, 2, 0), "╋": (2, 2, 2, 2), "┡": (2, 1, 0, 2), "┩": (2, 1, 2, 0),
    "╇": (2, 1, 2, 2), "┢": (1, 2, 0, 2), "┪": (1, 2, 2, 0), "╈": (1, 2, 2, 2),
}
# Block elements as (left, top, right, bottom) fractions of the cell and an opacity.
BLOCKS = {
    "█": (0, 0, 1, 1, 1.0), "▓": (0, 0, 1, 1, 0.75), "▒": (0, 0, 1, 1, 0.5),
    "░": (0, 0, 1, 1, 0.25), "▀": (0, 0, 1, 0.5, 1.0), "▄": (0, 0.5, 1, 1, 1.0),
    "▌": (0, 0, 0.5, 1, 1.0), "▐": (0.5, 0, 1, 1, 1.0),
}


class Terminal:
    def __init__(self, rows: int):
        from fontTools.ttLib import TTFont
        from PIL import ImageFont

        primary = next(p for p in FONT_PATHS if Path(p).exists())
        fallback = next(p for p in FALLBACK_PATHS if Path(p).exists())
        self.font = ImageFont.truetype(primary, FONT_SIZE)
        self.bold = ImageFont.truetype(primary, FONT_SIZE)
        try:
            self.bold.set_variation_by_name("Bold")
        except Exception:
            pass
        self.fallback = ImageFont.truetype(fallback, FONT_SIZE - 1)
        self.cmap = TTFont(primary, fontNumber=0).getBestCmap()
        self.cell = round(self.font.getlength("M"))
        self.rows = rows
        self.width = PADDING * 2 + COLS * self.cell
        self.height = TITLE_BAR + PADDING * 2 + rows * LINE_HEIGHT

    def _box(self, draw, x, y, weights, colour) -> None:
        up, down, left, right = weights
        cx = x + self.cell // 2
        cy = y + LINE_HEIGHT // 2
        for weight, (x0, y0, x1, y1) in (
            (up, (cx, y, cx, cy)), (down, (cx, cy, cx, y + LINE_HEIGHT)),
            (left, (x, cy, cx, cy)), (right, (cx, cy, x + self.cell, cy)),
        ):
            if weight:
                draw.line([x0, y0, x1, y1], fill=colour, width=weight)

    def frame(self, lines: List[List[Run]], cursor: Optional[Tuple[int, int]] = None):
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (self.width, self.height), BACKGROUND)
        draw = ImageDraw.Draw(image)
        # Title bar with the three window buttons.
        draw.rectangle([0, 0, self.width, TITLE_BAR], fill=(38, 35, 31))
        for i, colour in enumerate([(224, 108, 90), (229, 181, 103), (156, 197, 107)]):
            x = 18 + i * 20
            draw.ellipse([x, 11, x + 12, 23], fill=colour)
        title = "elrond@imladris — autumn"
        draw.text(((self.width - self.font.getlength(title)) / 2, 8), title,
                  font=self.font, fill=(150, 140, 126))

        top = TITLE_BAR + PADDING
        for row, runs in enumerate(lines[-self.rows:]):
            y = top + row * LINE_HEIGHT
            col = 0
            for text, style in runs:
                for char in text:
                    x = PADDING + col * self.cell
                    if style.bg:
                        draw.rectangle([x, y, x + self.cell, y + LINE_HEIGHT], fill=style.bg)
                    if char in BOX:
                        self._box(draw, x, y, BOX[char], style.fg)
                    elif char in BLOCKS:
                        left, top_f, right, bottom, alpha = BLOCKS[char]
                        under = style.bg or BACKGROUND
                        colour = tuple(int(f * alpha + b * (1 - alpha)) for f, b in zip(style.fg, under))
                        draw.rectangle([x + left * self.cell, y + top_f * LINE_HEIGHT,
                                        x + right * self.cell - 1, y + bottom * LINE_HEIGHT - 1],
                                       fill=colour)
                    elif char != " ":
                        if ord(char) in self.cmap:
                            font = self.bold if style.bold else self.font
                            draw.text((x, y + 2), char, font=font, fill=style.fg)
                        else:
                            glyph_w = self.fallback.getlength(char)
                            draw.text((x + (self.cell - glyph_w) / 2, y + 2), char,
                                      font=self.fallback, fill=style.fg)
                    if style.underline:
                        draw.line([x, y + LINE_HEIGHT - 3, x + self.cell, y + LINE_HEIGHT - 3],
                                  fill=style.fg)
                    col += 1
        if cursor is not None:
            row, col = cursor
            x = PADDING + col * self.cell
            y = top + row * LINE_HEIGHT
            draw.rectangle([x, y + 2, x + self.cell - 1, y + LINE_HEIGHT - 2], fill=(230, 181, 103))
        return image


def prompt_runs(typed: str) -> List[Run]:
    runs = [(text, CellStyle(_hex(colour), bold=True)) for text, colour in PROMPT]
    return runs + [(typed, CellStyle())]


def prompt_width() -> int:
    return sum(len(text) for text, _ in PROMPT)


def record(output_path: Path) -> None:
    from PIL import Image

    cache = output_path.with_suffix(".json")
    if "--from-cache" in sys.argv:
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        raw = [[(command, capture(command)) for command in screen] for screen in SCREENS]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    outputs = [[(command, ansi_lines(text)) for command, text in screen] for screen in raw]
    rows = max(sum(1 + len(lines) for _, lines in screen) + 1 for screen in outputs)
    terminal = Terminal(rows)

    frames: List["Image.Image"] = []
    durations: List[int] = []

    def show(lines: List[List[Run]], ms: int, cursor: Optional[Tuple[int, int]] = None) -> None:
        frames.append(terminal.frame(lines, cursor))
        durations.append(ms)

    for screen_index, screen in enumerate(outputs):
        lines: List[List[Run]] = []
        for command, output in screen:
            row = len(lines)
            show(lines + [prompt_runs("")], 700, (row, prompt_width()))
            per_char = max(18, min(55, 2600 // max(1, len(command))))
            for i in range(1, len(command) + 1):
                show(lines + [prompt_runs(command[:i])], per_char, (row, prompt_width() + i))
            show(lines + [prompt_runs(command)], 450, (row, prompt_width() + len(command)))
            lines = lines + [prompt_runs(command)] + output
            hold = min(5200, 1300 + 120 * len(output))
            show(lines + [prompt_runs("")], hold, (len(lines), prompt_width()))
        if screen_index == len(outputs) - 1:
            durations[-1] += 2500

    # One shared palette keeps colours steady from frame to frame.
    sample = Image.new("RGB", (terminal.width, terminal.height * 3))
    for i, index in enumerate([0, len(frames) // 2, len(frames) - 1]):
        sample.paste(frames[index], (0, terminal.height * i))
    palette = sample.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(output_path, save_all=True, append_images=quantized[1:],
                      duration=durations, loop=0, optimize=True, disposal=1)
    size_kb = output_path.stat().st_size // 1024
    print(f"Wrote {output_path} ({len(frames)} frames, {sum(durations) / 1000:.1f}s, {size_kb} KB)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--exec":
        run_autumn_in_process(sys.argv[2:])
    else:
        paths = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
        record(Path(paths[0] if paths else "demo.gif"))
