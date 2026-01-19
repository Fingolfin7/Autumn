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
| **Timers** | `autumn start <project>` | Start a timer | `-s`, `-n`, `--for`, `--remind-in` |
| | `autumn status` | Show active timers | `-p`, `-i` |
| | `autumn stop` | Stop timer | `-p`, `-i`, `-n` |
| | `autumn restart` | Reset start time to now | `-p`, `-i` |
| | `autumn resume` | Resume last project | `--stop-current` |
| **Logs** | `autumn log` | List sessions (saved) | `-P month`, `-p`, `-t`, `-c` |
| | `autumn log search` | Advanced search | `--note-snippet`, `--start-date` |
| **Projects** | `autumn projects` | List projects by status | `-S active`, `-c`, `-t` |
| | `autumn subprojects` | List subprojects for a project | `-p <project>` |
| | `autumn new` | Create a new project | `-d "description"` |
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
```

List subprojects for a specific project:
```bash
autumn subprojects "AutumnWeb"
autumn subs "AutumnWeb"        # Alias
```

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

## Features

- ✅ **Full Timer Lifecycle**: Start, stop, restart, resume, and delete.
- ✅ **Pomodoro Support**: Auto-stop timers and timed reminders.
- ✅ **Background Reminders**: NLP-powered reminders (`at`, `every`, `in`).
- ✅ **Rich Visualization**: Beautiful Matplotlib/Seaborn charts.
- ✅ **Metadata Aware**: Context and Tag filtering across all commands.
- ✅ **Cross-Platform Notifications**: Native toasts on Windows, macOS, and Linux.
- ✅ **Smart Greetings**: Dynamic, personalized messages based on time and activity.

## Troubleshooting

- **No notifications?** Check `autumn reminders list` to see if the daemon is running. On macOS, ensure `terminal-notifier` is installed (the CLI tries to auto-install via Homebrew).
- **SSL Errors?** If using a self-signed cert, set `autumn config set tls.insecure true`.
- **Outdated Data?** Run `autumn meta refresh` to sync projects, tags, and contexts.
