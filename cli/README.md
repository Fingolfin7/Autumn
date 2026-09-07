# Autumn CLI

The Click + Rich command-line client for AutumnWeb.

## Installation

Install the everyday time-tracking CLI from this `cli` directory:

```console
python -m pip install -e .
```

Charts use a separate plotting extra so regular CLI installs stay small:

```console
python -m pip install -e ".[charts]"
```

Existing installs that use `autumn chart` should reinstall from the checkout
with the `charts` extra once; all non-chart commands continue to use the base
install.

## Quick start

```console
autumn auth login
autumn start AutumnWeb
autumn status
autumn note "Working on timer cleanup"
autumn stop
autumn log
```

Use `autumn projects` to find project names and `autumn resume` to restart the
most recently used project. `autumn context`, `autumn tag`, and
`autumn commitments` list their current entries; their subcommands create or
edit them.

The root help groups commands by everyday task:

```console
autumn --help
autumn start --help
autumn context --help
```

Short aliases remain available for frequent commands: `p` for `projects`, `ls`
for `log`, `n` for `note`, `subs` for `subprojects`, and `cmt` for
`commitments`.

## Command reference

| Area | Command | What it does | Common options |
|---|---|---|---|
| Timers | `autumn start <project>` | Start a timer | `-s`, `-n`, `--for`, `--remind-in`, `--pick` |
| | `autumn status` | Show active timers | `-p`, `-i` |
| | `autumn stop` | Stop an active timer | `-p`, `-i`, `-n`, `--split` |
| | `autumn restart` | Reset an active timer's start time | `-p`, `-i` |
| | `autumn note <text...>` (`autumn n`) | Update an active timer's note | `-p`, `-s`, `--replace`, `--stamp`, `--no-stamp` |
| Sessions | `autumn log` (`autumn ls`) | List saved sessions | `-P`, `-p`, `-x`, `-t`, `-c`, `--show-ids` |
| | `autumn log search` | Search sessions | `--note-snippet`, `--start-date`, `--end-date` |
| | `autumn track <project>` | Manually log a session | `--start`, `--end`, `-s`, `-n`, `--split` |
| | `autumn edit <session-id>` | Edit a saved session in place | `-p`, `-s`, `--start`, `--end`, `-n`, `-a`/`--append-note`, `--split` |
| | `autumn delete-session <session-id>` | Delete a saved session | `-y` |
| Projects | `autumn projects` (`autumn p`) | List projects | `--status`, `--search`, `-x` |
| | `autumn project <name>` | Show or edit project metadata | `edit` |
| | `autumn subprojects <project>` (`autumn subs`) | List subprojects | `--search` |
| | `autumn new` | Create a project or subproject | `-s`, `-d`, `--context`, `--tags` |
| | `autumn mark` | Change project status | `<project> <status>` |
| Metadata | `autumn context` | Manage contexts | `list`, `new`, `rename`, `edit`, `delete` |
| | `autumn tag` | Manage tags | `list`, `new`, `rename`, `edit`, `delete` |
| Reminders | `autumn remind` / `autumn reminders` | Schedule and manage desktop reminders | See `--help` |
| Data and reports | `autumn chart` | Render activity charts | `--type`, `-P` |
| | `autumn garden` | Visit a seasonal woodland grown from saved history | `--project`, `--at`, `--page`, `--all`, `--save` |
| | `autumn export` / `autumn import` | Move Autumn data | See `--help` |
| Setup | `autumn config` | Manage CLI settings | `show`, `get`, `set`, `open` |
| | `autumn auth` | Manage API accounts | `login`, `logout`, `status`, `accounts`, `switch` |
| Other | `autumn commitments` (`autumn cmt`) | Manage recurring commitments | `list`, `show`, `new`, `edit`, `restart`, `adjust`, `delete` |

Run `autumn <command> --help` for the complete option list.

## Your garden

`autumn garden` draws a coloured terminal woodland from your live project
history. Oaks, pines, birches, willows, wildflowers, and ferns grow as saved time
accumulates. Time away never shrinks them. Completed projects get a small
star keepsake; each day brings a little visitor.

```console
autumn garden
autumn garden --page 2
autumn garden --project AutumnWeb
autumn garden --project AutumnWeb --species oak
autumn garden --at 2026-01-01
autumn garden --all --season spring
autumn garden --save woodland.svg
```

The default clearing shows eight projects, ordered by their latest saved visit.
Use `--limit 12` for a larger clearing, `--page 2` to move along, or `--all` for
the whole woodland. A project name can be a unique partial match; exact names
take priority. A close-up includes first/last visit dates and a short excerpt
from the latest nonempty session note. `--species` only changes that rendering.

Colours follow the date's season in the northern hemisphere; use
`--hemisphere south` or choose `--season` yourself. Layout fits the terminal,
with `--width 100` available for a fixed size. `--ascii` substitutes ASCII art,
`--no-color` removes colour, and `--color` forces it when piping to an ANSI-aware
viewer. `NO_COLOR` is respected unless you explicitly pass `--color`.

`--save` writes a standalone `.svg`, `.html`, or plain `.txt` keepsake. SVG and
HTML preserve the colours and need no external fonts or network access to view.
The file contains the displayed project names and, for a close-up, the displayed
note. Create its parent directory first. Ordinary terminal views save no new
history files.

The garden needs only the base CLI installation: no AI, plotting extras, or
new dependencies. It reads the saved export and project identities, never
updates Autumn history or project metadata, and uses stable project IDs so a
rename keeps the same plant. For offline viewing, use
`autumn garden --from-file export.json`. Format-2 exports omit project IDs, so
offline species are determined by names and can differ from the live view.

Growth uses five stages: seed (no positive saved time), seedling (under two
hours), sapling (two hours), established (ten hours), and mature (forty hours).
Further hours remain visible without letting one project swallow the scene.
Active timers, invalid timestamps, and zero/negative durations do not grow
plants; duplicate session UUIDs count once per project. Seven distinct session
start dates add a small woodland companion beside the roots. Unlogged time
doesn't imply inactivity.

`--at YYYY-MM-DD` rebuilds growth through the end of that **local** day, clipping
sessions that cross midnight and withholding their notes until their saved end.
It uses the history available now: later edits/deletions cannot be undone,
names and note text are current, and past completion status is unknown, so
historical views omit completion keepsakes. Future dates are rejected. In a
current view, even a mistakenly saved future session cannot grow beyond now.

## Subproject splits

`stop`, `track`, and `edit` accept an integer-percent split. Percentages are
converted to basis points for the API and may total less than 100; the remainder
is unallocated time.

```console
autumn stop --split "api=60,frontend=40"
autumn track AutumnWeb --start 09:00 --end 10:00 --split "api=75,docs=25"
autumn edit 123 --split "api=50,frontend=50"
```

Whitespace around names and values is allowed. Each percentage must be from 1
through 100 and the total cannot exceed 100. A named split defines the attached
subproject set. If `--subprojects` is also supplied, it must name exactly the same
set.

Use `--split even` with explicit subprojects to document an even split while
using the server's default distribution:

```console
autumn track AutumnWeb --start 09:00 --end 10:00 \
  --subprojects api --subprojects frontend --split even
```

For `stop --split even`, the CLI evenly divides the active timer's currently
attached subprojects.

## Notes as you go

Saved sessions are edited in place, so `autumn edit` preserves the session ID.
Use `--note` to replace a saved session's note or `--append-note` to add text
after its existing note:

```console
autumn edit 123 -a "Added follow-up context"
```

Append text to the newest active timer without stopping it:

```console
autumn note Implemented the timer endpoint
autumn n -p AutumnWeb "Reviewing tests"
autumn note -s 123 "Found the race condition"
```

Appends are separated from the existing note by a blank line and stamped with
the local time, for example `— 14:30 — Reviewing tests`. Use `--no-stamp` to
append plain text. `--replace` overwrites the current note and is unstamped by
default; combine it with `--stamp` to include a timestamp.

```console
autumn note --no-stamp "Plain appended text"
autumn note --replace "New complete note"
autumn note --replace --stamp "Stamped replacement"
```
