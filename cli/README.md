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
autumn start web                 # any unique part of a project name works
autumn note "Working on timer cleanup"
autumn stop
autumn track web 45m -n "Review" # log time you forgot to time
autumn log today
autumn log -q "login bug"        # search every session ever
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

## Names, dates and periods

Wherever a command takes a project, you can type its exact name in any case,
an alias (`autumn alias add project web AutumnWeb`), or any unique part of it.
`autumn start web` starts "AutumnWeb" when no other project contains "web";
`stop`, `status`, `note` and `discard` first match against the timers that
are running. An ambiguous or unknown name is not guessed: the CLI lists the
closest names instead. Renames only accept exact names.

Periods (`-P`, or a bare word after `autumn log`) are `today`, `yesterday`,
`week`, `fortnight`, `month`, `quarter`, `year` and `all`, with the shorthands
`d`, `w`, `2w`, `m`, `q`, `y`. Week, fortnight and month are rolling windows
(the last 7, 14 or 30 days).

`--since` and `--until` (also spelled `--start-date` and `--end-date`) accept
`2026-01-05`, `yesterday`, a weekday (the most recent one, including today),
`3d ago` or `-2w`.

## Search

`-q/--search` matches project names, subproject names and session notes on
the server, the same search the web Sessions page uses. Add `--related` to
also include sessions whose notes match by meaning; they are listed after the
direct matches under "Related by meaning", in the usual log layout. Related
matches need AI features and an OpenAI key on your AutumnWeb account; otherwise
the CLI says they were unavailable and shows direct matches only.

Notes print in full unless you ask for them shortened: `--truncate` cuts them
at 300 characters, `-m 120` at 120, and `--no-truncate` overrides
`autumn config set log.truncate_notes true --type bool` for one run
(`log.max_note_length` sets the default length).

```console
autumn log -q "auth"                 # all time unless you give a period
autumn log -q "auth" --related       # related matches listed after the rest
autumn log search -q deploy --limit 20 --newest
autumn projects -q garden --related  # searches every status
autumn chart pie -q "client" -P month
autumn export -q "thesis" --stdout
```

## Logging time after the fact

`autumn track` takes any two of a start, an end and a duration. A duration on
its own ends now. Time-only values fall on today unless `--on` names another
day; if both are time-only and the end is earlier, the session crosses
midnight.

```console
autumn track AutumnWeb 45m -n "Code review"
autumn track AutumnWeb 2h --start 14:00
autumn track AutumnWeb --start 9:00 --end 11:30
autumn track AutumnWeb --on yesterday --start 9am --end 5pm
```

`autumn edit` and `autumn delete-session` take a session ID, `last`, or
nothing to choose from your recent sessions. `autumn log --ids` shows IDs.
Time-only edits keep the session's own day, and `--for` sets its length.

```console
autumn edit last -a "Also fixed the tests"
autumn edit 123 --start 9:30 --for 1h
autumn delete-session last
```

## Command reference

| Area | Command | What it does | Common options |
|---|---|---|---|
| Timers | `autumn start <project>` | Start a timer | `-s`, `-n`, `--for`, `--remind-in`, `--pick` |
| | `autumn status [project]` | Show running timers | `-p`, `-i` |
| | `autumn stop [project]` | Stop a running timer | `-p`, `-i`, `-n`, `--split` |
| | `autumn note <text...>` (`autumn n`) | Update a running timer's note | `-p`, `-i`, `--replace`, `--stamp`, `--no-stamp` |
| | `autumn restart [project]` | Restart a running timer from now | `-p`, `-i` |
| | `autumn discard [project]` | Throw away a running timer (was `delete`) | `-p`, `-i`, `-y` |
| Sessions | `autumn log [period] [project]` (`autumn ls`) | List saved sessions | `-P`, `-p`, `-s`, `-x`, `-t`, `-c`, `-q`, `--related`, `--since`, `--ids`, `-m`, `--raw` |
| | `autumn log search` | Search with paging | `-q`, `--related`, `-n`, `--newest`, `--limit`, `--offset`, `-m` |
| | `autumn track <project> [duration]` | Log a completed session | `--start`, `--end`, `--for`, `--on`, `-s`, `-n`, `--split` |
| | `autumn edit [session]` | Edit a saved session in place | `-p`, `-s`, `--start`, `--end`, `--for`, `-n`, `-a`, `--split` |
| | `autumn delete-session [session]` | Delete a saved session | `-y` |
| Projects | `autumn projects` (`autumn p`) | List projects | `-S`, `-q`, `--related`, `-c`, `-t`, `-x` |
| | `autumn project <name>` | Show a project, or `edit` its metadata | `show`, `edit -d -c -t -T` |
| | `autumn subprojects [project]` (`autumn subs`) | List subprojects | `--search` |
| | `autumn new` | Create a project or subproject | `-s`, `-d`, `-c`, `-t` |
| | `autumn mark` | Change project status | `<project> <status>` |
| | `autumn totals [project]` | Project and subproject totals | `-P`, `--since`, `-c`, `-t` |
| Metadata | `autumn context` | Manage contexts | `list`, `new`, `rename`, `edit`, `delete` |
| | `autumn tag` | Manage tags | `list`, `new`, `rename`, `edit`, `delete` |
| Reminders | `autumn remind in 25m stretch` / `autumn reminders` | Schedule and manage desktop reminders | `in`, `at`, `every`, `session` |
| Data and reports | `autumn chart [type]` | Render activity charts | `-P`, `-p`, `-q`, `--related`, `--save` |
| | `autumn garden` | Visit a seasonal woodland grown from saved history | `--project`, `--at`, `--page`, `--all`, `--save` |
| | `autumn export` / `autumn import` | Move Autumn data | See `--help` |
| Setup | `autumn config` | Manage CLI settings | `show`, `get`, `set`, `open` |
| | `autumn auth` | Manage API accounts | `login`, `logout`, `status`, `accounts`, `switch` |
| Other | `autumn commitments` (`autumn cmt`) | Manage recurring commitments | `list`, `show`, `new`, `edit`, `restart`, `adjust`, `delete` |

Commitments are addressed by ID or target name: `autumn cmt new Autumn 5h`
(5 hours a week), `autumn cmt new Autumn 3 --sessions -P day`,
`autumn cmt adjust Autumn 1h -r "offline work"`, `autumn cmt show Autumn`.

`autumn chart heatmap` uses the server's weekday/hour aggregation, the same
numbers as the web chart: sessions are split across each clock hour they span,
and each cell is the average share of that hour spent working.

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
autumn track AutumnWeb 1h --start 09:00 --split "api=75,docs=25"
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
autumn note -i 123 "Found the race condition"
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
