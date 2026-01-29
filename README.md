# Autumn CLI

Command-line interface for AutumnWeb — time tracking and project management from your terminal.

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
```

### 3) Say hi

Running `autumn` with no subcommands prints a short, dynamic greeting (time-of-day / moon phase / seasonal vibes).

```bash
autumn
```

## Command Reference

| Area | Command | What it does | Common options |
|---|---|---|---|
| **Timers** | `autumn start <project>` | Start a timer | `-s`, `-n`, `--for`, `--remind-in`, `--pick` |
| | `autumn status` | Show active timers | `-p`, `-i` |
| | `autumn stop` | Stop timer | `-p`, `-i`, `-n` |
| | `autumn restart` | Reset start time to now | `-p`, `-i` |
| | `autumn resume` | Resume last project | `--stop-current` |
| **Logs** | `autumn log` | List sessions (saved) | `-P month`, `-p`, `-t`, `-c`, `--pick` |
| | `autumn log search` | Advanced search | `--note-snippet`, `--start-date` |
| | `autumn track` | Manually log a session | `--start`, `--end`, `-n` |
| **Projects** | `autumn projects` | List projects by status | `-S active`, `-c`, `-t`, `-d` |
| | `autumn subprojects` | List subprojects for a project | `<project>`, `-d` |
| | `autumn new` | Create project or subproject | `-s`, `-d`, `--pick` |
| | `autumn mark` | Change project status | `<project> <status>`, `--pick` |
| | `autumn rename` | Rename project or subproject | `<old> <new>`, `-p` for subprojects |
| | `autumn totals` | Show project time breakdown | `<project>`, `--start-date`, `--end-date` |
| | `autumn delete-project` | Delete a project | `<project>`, `-y`, `--pick` |
| | `autumn delete-sub` | Delete a subproject | `<project> <sub>`, `-y`, `--pick` |
| **Data** | `autumn export` | Export sessions/projects JSON | `-o`, `-d`, `-p`, `--stdout` |
| | `autumn audit` | Recompute project totals | — |
| **Reminders** | `autumn remind` | Set ad-hoc reminders | `at`, `every`, `in`, `session` |
| | `autumn reminders` | Manage background workers | `list`, `stop` |
| **Charts** | `autumn chart` | Render charts | `--type`, `-P`, `--color-by-project` |
| **Config** | `autumn config` | Edit settings | `show`, `set`, `open` |
| **Meta** | `autumn meta refresh` | Clear cached metadata | — |

## Usage

### Timer & Pomodoro Commands

Start a basic timer:
```bash
autumn start "AutumnWeb" --note "Implementing reminders"
```

**Pomodoro / Timed Sessions:**
You can set an auto-stop duration and various reminders when starting:
```bash
autumn start "Deep Work" --for 25m --remind-in 20m --remind-message "5 minutes left!"
```

Periodic reminders (runs in background):
```bash
autumn start "Coding" --remind-every 1h --remind-message "Stand up and stretch!"
```

### Reminders (Ad-hoc)

Set reminders independent of timers:
```bash
# Relative time
autumn remind in 15m --message "Check the oven"

# Absolute time
autumn remind at 5pm --message "Team Meeting"

# Periodic
autumn remind every 30m --message "Drink water"

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

Filter by period, project, or tags:
```bash
autumn log -P month -p "AutumnWeb" -t "Feature"
```

*Note: Short flag `-P` is for **Period**, and `-p` is for **Project**.*

### Projects & Subprojects

List all projects:
```bash
autumn projects
autumn p            # Alias
autumn projects -d  # Show descriptions
```

List subprojects for a specific project:
```bash
autumn subprojects "AutumnWeb"
autumn subs "AutumnWeb"        # Alias
```

Create a new project or subproject:
```bash
autumn new "My Project" -d "Project description"
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
autumn totals "My Project" --start-date 2026-01-01
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
autumn export -o backup.json               # Export to specific file
autumn export -d ~/backups                 # Export to custom directory
autumn export --stdout                     # Print to terminal (for piping)
autumn export --stdout | jq .sessions      # Pipe to jq
autumn export --compress                   # Compressed format
```

Configure a custom default directory:
```bash
autumn config set export.default_dir "~/backups"
```

**Audit/recompute totals:**
```bash
autumn audit
```

This recalculates all project and subproject totals from session data. Useful after imports or if totals seem incorrect.

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

Autumn supports various chart types: `pie`, `bar`, `scatter`, `calendar`, `wordcloud`, `heatmap`.

```bash
# Calendar heatmap colored by project
autumn chart --type calendar --color-by-project

# Weekly bar chart for a specific context
autumn chart --type bar -P week --context Work
```

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

**Aliases:**

Define short names for projects, contexts, or tags:
```bash
autumn config set aliases.projects '{"cli": "Autumn CLI", "oss": "Open Source"}' --type json
autumn config set aliases.contexts '{"w": "Work", "h": "Personal"}' --type json
```

Then use the short names in commands:
```bash
autumn start cli        # Resolves to "Autumn CLI"
autumn log -c w         # Resolves to "Work" context
```

## Features

- ✅ **Full Timer Lifecycle**: Start, stop, restart, resume, and delete.
- ✅ **Pomodoro Support**: Auto-stop timers and timed reminders.
- ✅ **Project Management**: Create, rename, mark status, and delete projects/subprojects.
- ✅ **Interactive Pickers**: Fuzzy-search selection with `--pick` flag.
- ✅ **Data Export**: Export sessions and projects to JSON with filtering.
- ✅ **Background Reminders**: NLP-powered reminders (`at`, `every`, `in`).
- ✅ **Rich Visualization**: Beautiful Matplotlib/Seaborn charts.
- ✅ **Metadata Aware**: Context and Tag filtering across all commands.
- ✅ **Cross-Platform Notifications**: Native toasts on Windows, macOS, and Linux.
- ✅ **Smart Greetings**: Dynamic, personalized messages based on time and activity.
- ✅ **Case-Insensitive Input**: Project/subproject names resolve regardless of case.
- ✅ **Alias Support**: Define short names for frequently used projects.

## Troubleshooting

- **No notifications?** Check `autumn reminders list` to see if the daemon is running. On macOS, ensure `terminal-notifier` is installed (the CLI tries to auto-install via Homebrew).
- **SSL Errors?** If using a self-signed cert, set `autumn config set tls.insecure true`.
- **Outdated Data?** Run `autumn meta refresh` to sync projects, tags, and contexts.
- **Incorrect Totals?** Run `autumn audit` to recompute all project/subproject totals from session data.
