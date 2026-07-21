# Autumn CLI

The Click + Rich command-line client for AutumnWeb.

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
| Other | `autumn commitments` (`autumn cmt`) | Manage recurring commitments | `list`, `show`, `new`, `edit`, `delete` |
| | `autumn chart` | Render activity charts | `--type`, `-P` |
| | `autumn export` / `autumn import` | Move Autumn data | See `--help` |
| | `autumn config` | Manage CLI settings | `show`, `set`, `open` |
| | `autumn auth` | Manage API accounts | `setup`, `status`, `accounts`, `switch`, `remove` |

Run `autumn <command> --help` for the complete option list.

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
