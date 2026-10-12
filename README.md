# Autumn CLI

Command-line interface for AutumnWeb — time tracking and project management from your terminal.

```bash
autumn start web                  # "web" is enough to find AutumnWeb
autumn note "Fixed the login race"
autumn stop
autumn track web 45m -n "Review"  # log time you forgot to time
autumn log today
autumn log -q "login" --related   # search notes, by text and by meaning
```

## Features

- **Timers**: start, stop, restart, resume and discard, with server-side auto-stop (`--for 25m`) and desktop reminders.
- **Forgiving input**: type any unique part of a project name, an alias, or any case; ambiguous names get "did you mean" suggestions instead of a guess.
- **Natural dates and periods**: `autumn log yesterday`, `-P 2w`, `--since monday`, `--start 9am --on yesterday`.
- **Logging after the fact**: `autumn track <project> 45m`, or any two of start, end and duration; `autumn edit last` fixes the latest session.
- **Search**: one `-q` searches project names, subprojects and notes across logs, projects, charts and exports; `--related` adds matches by meaning (needs AI features on your account).
- **Projects and metadata**: subprojects, contexts, tags, statuses, merges, aliases and per-subproject time splits.
- **Commitments**: recurring time or session goals with streaks and balances (`autumn cmt new Autumn 5h`).
- **Charts**: pie, bar, calendar, heatmap, wordcloud, treemap and more (`autumn chart heatmap`).
- **Garden**: a seasonal terminal woodland grown from your project history (`autumn garden`).
- **Data**: JSON export and import, filtered by project, context, tag, date or search.
- **Cross-platform**: Windows, macOS and Linux, with native notifications and interactive `--pick` pickers.

## Installation

### Using pip

```bash
cd cli
pip install -e .
```

Or from the AutumnWeb root directory:

```bash
pip install -e ./cli
```

### Using uv

```bash
cd cli
uv pip install -e .
```

Or from the AutumnWeb root directory:

```bash
uv pip install -e ./cli
```

### Running tests

`pytest` is tracked in the CLI's dev dependency group.

```bash
cd cli
uv run --group dev python -m pytest
```

## Getting Started

### 1) Authenticate

Autumn CLI supports two authentication flows:

#### Option A: API token (existing)

```bash
autumn auth setup
```

You’ll be prompted for:
- **API Key**: Your AutumnWeb API token
- **Base URL**: Your AutumnWeb instance URL (default: `http://localhost:8000`)

#### Option B: Username/email + password (new)

This will request a token from the server and save it to your config file:

```bash
autumn auth login
```

Options:
- `--username` (or email)
- `--password` (will prompt if omitted)
- `--base-url`

### 2) Verify configuration

```bash
autumn auth status
autumn auth verify
autumn auth accounts
```

If you log into multiple accounts against the same AutumnWeb instance, you can switch between them quickly:

```bash
autumn auth switch alice
```

### 3) Say hi

Running `autumn` with no subcommands prints a short, dynamic greeting (time-of-day / moon phase / seasonal vibes).

```bash
autumn
```

## Command Reference

| Area | Command | What it does | Common options |
|---|---|---|---|
| **Timers** | `autumn start <project>` | Start a timer (with optional server-side auto-stop) | `-s`, `-n`, `--for`, `--remind-in`, `--pick` |
| | `autumn status [project]` | Show active timers and auto-stop timing | `-p`, `-i` |
| | `autumn stop [project]` | Stop timer | `-p`, `-i`, `-n`, `--split` |
| | `autumn note <text...>` (`n`) | Add to a running timer's note | `-p`, `-i`, `--replace` |
| | `autumn restart [project]` | Reset start time to now | `-p`, `-i` |
| | `autumn discard [project]` | Throw away a running timer (was `delete`) | `-p`, `-i`, `-y` |
| | `autumn resume` | Resume last project | `--stop-current` |
| **Logs** | `autumn log [period] [project]` (`ls`) | List sessions (saved) | `-P`, `-p`, `-s`, `-x`, `-t`, `-c`, `-q`, `--related`, `--since`, `--ids` |
| | `autumn log search` | Search with paging | `-q`, `--related`, `--newest`, `-n`, `--limit`, `--offset` |
| | `autumn track <project> [duration]` | Log a completed session | `--start`, `--end`, `--for`, `--on`, `-n` |
| | `autumn edit [session]` | Edit a saved session (ID or `last`) | `--start`, `--end`, `--for`, `-n`, `-a`, `--split` |
| | `autumn delete-session [session]` | Delete a saved session | `-y` |
| **Projects** | `autumn projects` (`p`) | List projects by status | `-S`, `-c`, `-x`, `-t`, `-d`, `-q`, `--related` |
| | `autumn project` | Show or edit a project's metadata | `<name>`, `edit <name>` |
| | `autumn subprojects [project]` (`subs`) | List subprojects for a project | `-d`, `-q` |
| | `autumn new` | Create project or subproject | `-s`, `-d`, `-c`, `-t`, `--pick` |
| | `autumn mark` | Change project status | `<project> <status>`, `--pick` |
| | `autumn rename` | Rename project or subproject | `<old> <new>`, `-p` for subprojects |
| | `autumn totals [project]` | Show project time breakdown | `-P`, `--since`, `--until`, `-c`, `-t` |
| | `autumn merge` | Merge two projects | `<p1> <p2> --into <name>`, `-y` |
| | `autumn merge-subs` | Merge two subprojects | `<project> <s1> <s2> --into`, `-y` |
| | `autumn delete-project` | Delete a project | `<project>`, `-y`, `--pick` |
| | `autumn delete-sub` | Delete a subproject | `<project> <sub>`, `-y`, `--pick` |
| **Data** | `autumn export` | Export sessions/projects JSON | `-o`, `-d`, `-p`, `-c`, `-t`, `-q`, `--since`, `--stdout` |
| | `autumn import <file>` | Import an export JSON or compressed export | `--force`, `--merge`, `--tolerance`, `-y` |
| **Reminders** | `autumn remind` | Set ad-hoc reminders | `at`, `every`, `in`, `session` |
| | `autumn reminders` | Manage background workers | `list`, `stop` |
| **Charts** | `autumn chart [type]` | Render charts | `-P`, `-p`, `-q`, `--related`, `--color-by-project`, `--save` |
| **Garden** | `autumn garden` | Draw a seasonal woodland from saved project history | `--project`, `--at`, `--page`, `--all`, `--save` |
| **Config** | `autumn config` | Edit settings | `show`, `set`, `open` |
| **Auth** | `autumn auth accounts` | List saved accounts | — |
| | `autumn auth switch <account>` | Switch active account | — |
| | `autumn alias` | Manage aliases | `add`, `list`, `remove` |
| **Metadata** | `autumn context` | List and manage contexts | `list`, `new`, `rename`, `edit`, `delete` |
| | `autumn tag` | List and manage tags | `list`, `new`, `rename`, `edit`, `delete` |
| **Commitments** | `autumn commitments` (`cmt`) | Track recurring goals | `list`, `show`, `new`, `edit`, `restart`, `adjust`, `delete` |
| **Meta** | `autumn meta refresh` | Clear cached metadata | — |

## Usage

### Timer & Pomodoro Commands

Start a basic timer:
```bash
autumn start "AutumnWeb" --note "Implementing reminders"
```

**Pomodoro / Timed Sessions:**
You can set a server-side auto-stop duration and various reminders when starting:
```bash
autumn start "Deep Work" --for 25m --remind-in 20m --remind-message "5 minutes left!"
```

`--for` sends the duration to AutumnWeb, so the timer stops even if this machine sleeps or the local CLI worker exits. `autumn start`, `autumn restart`, and `autumn status` show when an active timer auto-stops (and how long remains). The local worker only handles the desktop notification; it does not own the stop itself.

Periodic reminders (runs in background):
```bash
autumn start "Coding" --remind-every 1h --remind-message "Stand up and stretch!"
```

### Reminders (Ad-hoc)

Set reminders independent of timers:
```bash
# Relative time
autumn remind in 15m Check the oven

# Absolute time
autumn remind at 5pm Team meeting

# Periodic
autumn remind every 30m Drink water

# Attach to an existing session
autumn remind session 123 --every 20m --message "Review progress"
```

**Managing Workers:**
Reminders run as background processes.
```bash
autumn reminders list       # See what's running
autumn reminders stop --all # Stop everything
```

### Sessions & Logs

View activity for the current week (default):
```bash
autumn log
```

Give a period and project as bare words, or use flags:
```bash
autumn log today
autumn log AutumnWeb month
autumn log -P 2w -p web -t Feature
autumn log --since monday --until yesterday
```

Periods are `today`, `yesterday`, `week`, `fortnight`, `month`, `quarter`, `year` and `all` (shorthands `d`, `w`, `2w`, `m`, `q`, `y`). `--since`/`--until` accept `2026-01-05`, `yesterday`, a weekday, `3d ago` or `-2w`.

Exclude one or more projects from logs:
```bash
autumn log -P month -x "Admin" -x "Meta"
autumn log search --since 2026-01-01 --exclude "Admin"
```

*Note: Short flag `-P` is for **Period**, and `-p` is for **Project**.*

**Search** project names, subproject names and session notes (all time unless you give a period). `--related` also lists sessions that match by meaning; it needs AI features and an OpenAI key on your AutumnWeb account.
```bash
autumn log -q "auth"
autumn log -q "auth" --related
autumn log search -q deploy --newest --limit 20
```

**Log time after the fact** with any two of a start, an end and a duration (a duration alone ends now):
```bash
autumn track AutumnWeb 45m -n "Code review"
autumn track AutumnWeb 2h --start 14:00
autumn track AutumnWeb --on yesterday --start 9am --end 5pm
```

**Fix or remove saved sessions** by ID, `last`, or from a picker of recent sessions (`autumn log --ids` shows IDs):
```bash
autumn edit last -a "Also fixed the tests"
autumn edit 123 --start 9:30 --for 1h
autumn delete-session last
```

### Projects & Subprojects

List all projects:
```bash
autumn projects
autumn p            # Alias
autumn projects -d  # Show descriptions
autumn projects -x "Admin" -x "Meta"  # Exclude projects
```

List subprojects for a specific project:
```bash
autumn subprojects "AutumnWeb"
autumn subs "AutumnWeb"        # Alias
```

Create a new project or subproject:
```bash
autumn new "My Project" -d "Project description"
autumn new "My Project" -c Work -t Important -t Client
autumn new "My Project" -s "Backend" -d "Backend services"  # Create subproject
autumn new --pick -s "New Feature"  # Interactive project selection
```

### Project Management

**Change project status:**
```bash
autumn mark "Old Project" complete
autumn mark "Side Project" paused
autumn mark --pick  # Interactive selection
```

Valid statuses: `active`, `paused`, `complete`, `archived`

**Rename projects or subprojects:**
```bash
autumn rename "Old Name" "New Name"
autumn rename "OldSub" "NewSub" -p "Parent Project"  # Rename subproject
```

**View project time totals:**
```bash
autumn totals "My Project"
autumn totals "My Project" -P month
autumn totals "My Project" --since 2026-01-01
```

**View single project details:**
```bash
autumn project "My Project"
autumn project --pick  # Interactive selection
```

Shows: status, total time, session count, average session duration, context, tags, and subprojects.

**Edit project metadata:**
```bash
autumn project edit "My Project" --description "New description" --context Work
autumn project edit "My Project" --clear-context
autumn project edit "My Project" --tags "Important,Client"  # Replace all tags
autumn project edit "My Project" --add-tag Urgent --remove-tag Client
```

Use either `--tags` to replace the complete tag list, or `--add-tag` / `--remove-tag` for incremental changes. `--context` and `--clear-context` cannot be combined.

**Search projects and subprojects:**
```bash
autumn projects -q "web"                    # Searches every status
autumn projects -q "api" -S active          # Only active projects
autumn projects -q "garden" --related       # Also projects related by meaning
autumn projects -q "api" -x "Admin"         # Search while excluding projects
autumn subprojects "My Project" -q "frontend"
```

**Merge projects:**
```bash
autumn merge "Project A" "Project B" --into "Combined Project"
autumn merge --pick --into "Merged"  # Interactive selection
```

All sessions and subprojects from both projects are moved to the new project. The original projects are deleted.

**Merge subprojects:**
```bash
autumn merge-subs "My Project" "Frontend" "UI" --into "Frontend UI"
autumn merge-subs --pick --into "Merged Sub"
```

**Delete projects or subprojects:**
```bash
autumn delete-project "Old Project"      # Prompts for confirmation
autumn delete-project "Old Project" -y   # Skip confirmation
autumn delete-sub "Project" "Subproject"
```

### Data Export & Maintenance

**Export data to JSON:**

By default, exports save to `~/Downloads` with a timestamped filename.

```bash
autumn export                              # Export to ~/Downloads/autumn_export_20260129_143052.json
autumn export -p "My Project"              # Filter by project
autumn export -c Work -t Client --since 2026-01-01  # Context, tag and date
autumn export -q "thesis"                  # Only sessions matching a search
autumn export -o backup.json               # Export to specific file
autumn export -d ~/backups                 # Export to custom directory
autumn export --stdout                     # Print to terminal (for piping)
autumn export --stdout | jq .sessions      # Pipe to jq
autumn export --compress                   # Compressed format
```

**Import an export:**

```bash
autumn import backup.json
autumn import autumn_export_compressed.txt --merge --tolerance 5 -y
autumn import legacy_export.json --autumn-format --context Work
autumn import replacement.json --force
```

Imports are performed by the server. Use `--merge` to merge into existing projects, or `--force` to delete same-named projects first; the two options are mutually exclusive. `--context` imports into that context (creating it if needed), and `--autumn-format` marks a legacy Autumn CLI export.

Configure a custom default directory:
```bash
autumn config set export.default_dir "~/backups"
```

### Interactive Selection

Many commands support `--pick` for interactive fuzzy-search selection:
```bash
autumn start --pick           # Pick project interactively
autumn log --pick             # Pick project/context/tags
autumn mark --pick            # Pick project to mark
autumn totals --pick          # Pick project for totals
```

The picker shows recent projects first and supports typing to filter the list.

### Charts & Visualization

Chart types include `pie`, `bar`, `scatter`, `line`, `area`, `cumulative`, `calendar`, `heatmap`, `wordcloud`, `treemap`, `sunburst`, `histogram`, `radar` and `bubble`. Charts need the plotting extra: `pip install -e "./cli[charts]"`.

```bash
# Calendar colored by project
autumn chart calendar --color-by-project

# Weekly bar chart for a specific context
autumn chart bar -P week -c Work

# Only sessions matching a search
autumn chart pie -q "client" -P month
```

`autumn chart heatmap` shows the same numbers as the web chart: sessions are split across each clock hour they span, and each cell is the average share of that hour spent working.

### Contexts & Tags

Contexts and tags can be listed, created, renamed, edited, and deleted:

```bash
autumn context list -d
autumn context new Work --description "Client and office work"
autumn context rename Work "Client Work"
autumn context edit "Client Work" --description "Client-facing work"
autumn context delete "Client Work" -y

autumn tag list --color
autumn tag new Urgent --color red
autumn tag rename Urgent Priority
autumn tag edit Priority --color orange
autumn tag delete Priority -y
```

Pass an empty string to `context edit --description` or `tag edit --color` to clear that field. Deleting a context removes it from its projects but retains the projects and their other data.

### Commitments

Commitments track recurring time or session goals for a project, subproject, context, or tag. `autumn commitments` (or `autumn cmt`) lists active commitments with progress, status, and balance.

```bash
autumn commitments --all --streak
autumn cmt new AutumnWeb 5h                       # 5 hours a week
autumn cmt new AutumnWeb 3 --sessions -P day      # 3 sessions a day
autumn cmt new "AutumnWeb/Backend" 10h --type subproject -P month
autumn cmt new Work 8h --type context --include "Client Project"
autumn cmt show AutumnWeb                         # by target name or ID
autumn cmt edit AutumnWeb --target-value 6h --no-banking --max-balance 2h
autumn cmt adjust AutumnWeb 1h -r "offline work"
autumn cmt delete AutumnWeb
```

Commitments are addressed by ID or target name (a unique partial name works). Time commitments accept duration values such as `5h` for the goal, `--min-balance`, and `--max-balance`; session commitments use whole session counts. `--include` and `--exclude` apply only to context or tag commitments. Use `--json` for raw list output, and `--start-date` to set a commitment's `YYYY-MM-DD` start date.

## Configuration

Settings are stored in `~/.autumn/config.yaml`. You can edit this file directly or use the CLI:

```bash
autumn config show    # View current config
autumn config open    # Open config file in default editor
```

**Common Knobs:**
- `tls.insecure: true` - Disable TLS verification (for local dev)
- `greeting_activity_weight: 0.5` - How often to show activity in greetings (0-1)
- `notify.log_file: "~/.autumn/notify.log"` - Enable notification debug logging
- `wake_retry: true` - Automatically wake and retry a sleeping hosted server
- `wake_timeout_seconds: 120` - Maximum seconds to wait for the server to become healthy

When a hosted instance such as a Render free-tier service is asleep, commands print a waking-up notice, poll `/healthz/` with backoff, then retry automatically. Set `wake_retry: false` to fail fast, or override either setting for one environment with `AUTUMN_WAKE_RETRY` and `AUTUMN_WAKE_TIMEOUT_SECONDS`.

### Aliases

Define short names for projects, contexts, tags, or subprojects using the `alias` command:

**Add aliases:**
```bash
autumn alias add project cli "Autumn CLI"
autumn alias add context w Work
autumn alias add tag imp Important
autumn alias add subproject fe Frontend -p "Autumn CLI"  # Scoped to project

# Interactive mode
autumn alias add project myalias --pick
```

**List aliases:**
```bash
autumn alias list                # Show all aliases
autumn alias list --type project # Filter by type
autumn alias list --json         # JSON output
```

**Remove aliases:**
```bash
autumn alias remove project cli
autumn alias remove subproject fe -p "Autumn CLI"
```

**Use aliases in commands:**
```bash
autumn start cli           # Resolves to "Autumn CLI"
autumn log -c w            # Resolves to "Work" context
autumn start cli -s fe     # Subproject alias resolves within project scope
```

Subproject aliases are **project-scoped** — the alias `fe` can map to different subprojects in different projects.

## Troubleshooting

- **No notifications?** Check `autumn reminders list` to see if the daemon is running. On macOS, Autumn uses `terminal-notifier`; if it is missing, the CLI will explicitly try `brew install terminal-notifier` on first use.
- **SSL Errors?** If using a self-signed cert, set `autumn config set tls.insecure true`.
- **Outdated Data?** Run `autumn meta refresh` to sync projects, tags, and contexts.