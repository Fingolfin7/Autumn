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

You can also provide them as options:

```bash
autumn auth setup --api-key "your-token-here" --base-url "http://localhost:8000"
```

#### Option B: Username/email + password (new)

This will request a token from the server and save it to your config file:

```bash
autumn auth login
```

Options:
- `--username` (or email)
- `--password` (will prompt if omitted)
- `--base-url`

#### Switch accounts / logout

```bash
autumn auth logout
autumn auth login
```

### 2) Verify configuration

```bash
autumn auth verify
autumn auth status
```

### 3) Say hi

Running `autumn` with no subcommands prints:
- A short, dynamic greeting (time-of-day / moon phase / seasonal vibes, sometimes recent activity)
- The base URL you’re currently connected to

```bash
autumn
```

## Usage

## Command Reference

A quick overview of the most-used commands:

| Area | Command | What it does | Common options |
|---|---|---|---|
| Greeting | `autumn` | Show a short greeting + connection info | (see greeting knobs via `autumn config greeting show`) |
| Auth | `autumn auth setup` | Save API token + base URL | `--api-key`, `--base-url` |
| Auth | `autumn auth login` | Login with username/email + password and store token | `--username`, `--password`, `--base-url` |
| Auth | `autumn auth logout` | Clear stored API token | — |
| Timers | `autumn start <project>` | Start a timer | `--subprojects`, `--note` |
| Timers | `autumn status` | Show active timers | `--project`, `--session-id` |
| Timers | `autumn stop` | Stop timer | `--project`, `--session-id`, `--note` |
| Timers | `autumn restart` | Restart timer | `--project`, `--session-id` |
| Timers | `autumn resume` | Resume last worked-on project | `--stop-current` |
| Timers | `autumn delete` | Delete timer without saving | `--session-id` |
| Logs | `autumn log` | List sessions (saved) | `--period`, `--project`, `--context`, `--tag`, `--start-date`, `--end-date` |
| Logs | `autumn log search` | Search sessions | `--note-snippet`, `--context`, `--tag`, `--limit`, `--offset` |
| Projects | `autumn projects` | List projects grouped by status | `--status`, `--context`, `--tag` |
| Charts | `autumn chart` | Render charts | `--type`, `--project`, `--context`, `--tag`, `--period/-pd`, `--save` |
| Meta | `autumn context list` | List contexts | `--full`, `--json` |
| Meta | `autumn tag list` | List tags | `--full`, `--json` |
| Meta | `autumn meta refresh` | Clear cached contexts/tags + greeting activity cache | — |
| Convenience | `autumn open` | Open the web app in your browser | `--path` |
| Aliases | `autumn p` | Alias for `autumn projects` | same options as `projects` |
| Aliases | `autumn ls` | Alias for `autumn log` | same options as `log` |

### Timer Commands

Start a timer:
```bash
autumn start "My Project"
autumn start "My Project" --subprojects "Frontend" "Backend" --note "Working on API"
```

Check timer status:
```bash
autumn status
autumn status --project "My Project"
```

Stop a timer:
```bash
autumn stop
autumn stop --project "My Project" --note "Finished for today"
```

Restart a timer:
```bash
autumn restart
autumn restart --project "My Project"
autumn restart --session-id 123
```

Resume a project:
```bash
autumn resume
autumn resume --stop-current
```

Delete a timer:
```bash
autumn delete --session-id 123
```

### Sessions / Logs

Show activity logs (saved sessions):
```bash
autumn log                   # Default: last week
autumn log --period month
```

You can filter logs by context and tags:
```bash
autumn log --context General --tag Code --tag "Error Handling"
```

Search sessions:
```bash
autumn log search --project "My Project"
autumn log search --start-date 2024-01-01 --end-date 2024-01-31
autumn log search --note-snippet "meeting"
autumn log search --context General --tag Code
```

Track a completed session manually:
```bash
autumn track "My Project" --start "2024-01-15 09:00:00" --end "2024-01-15 11:30:00" --note "Morning work session"
```

### Projects

List projects (grouped by status, including archived):
```bash
autumn projects
```

Filter by status/context/tags:
```bash
autumn projects --status archived
autumn projects --context General
autumn projects --tag Code --tag "Backend"
```

Create a project:
```bash
autumn new "New Project" --description "Project description"
```

### Charts

All charts can be displayed interactively or saved to a file using `--save`.
Charts also support `--context` and repeatable `--tag` filtering.

Chart types:
- `pie` (default) - Project/subproject time distribution
- `bar` - Horizontal bar chart of project/subproject totals
- `scatter` - Session durations over time
- `calendar` - GitHub contribution-style calendar heatmap
- `wordcloud` - Word cloud from session notes
- `heatmap` - Activity heatmap by day of week and hour

Examples:
```bash
# Pie chart (default)
autumn chart

# Filtered chart
autumn chart --context General --tag Code -pd month

# Bar chart
autumn chart --type bar

# Save to file
autumn chart --type pie --save chart.png
```

### Contexts & Tags

List contexts:
```bash
autumn context list
autumn context list --full
```

List tags:
```bash
autumn tag list
autumn tag list --full
```

Refresh cached metadata (contexts/tags + greeting activity cache):
```bash
autumn meta refresh
```

## Configuration

Configuration is stored in `~/.autumn/config.yaml`.

Common keys:
```yaml
api_key: your_api_token_here
base_url: https://your-instance

# Greeting knobs
# How often the greeting references recent activity (0..1)
greeting_activity_weight: 0.35

# How often non-full/new moon phases can show up in the greeting (0..1)
greeting_moon_cameo_weight: 0.15
```

### Config commands (new)

Show config (redacts API key by default):
```bash
autumn config show
```

Get/set values by dotted path:
```bash
autumn config get base_url
autumn config set base_url https://example.com

autumn config set greeting_activity_weight 0.15 --type float
```

Greeting convenience commands:
```bash
autumn config greeting show
autumn config greeting set --activity-weight 0.2 --moon-cameo-weight 0.05
```

Environment variables:
- `AUTUMN_API_KEY`: overrides `api_key`
- `AUTUMN_API_BASE`: overrides `base_url`

## Features

- ✅ **Timer Management**: Start, stop, restart, and manage timers
- ✅ **Session Logs + Search**: View and search sessions, including notes
- ✅ **Projects (Grouped + Robust)**: Colored grouped tables with metadata; includes archived
- ✅ **Contexts + Tags**: Discover via CLI and use for filtering (projects/logs/charts/search)
- ✅ **Charts & Visualization**: Generate charts (pie/bar/scatter/calendar/wordcloud/heatmap)
- ✅ **Dynamic Greeting**: Fun “alive” greeting when running `autumn` with no args
- ✅ **Config Editor**: View/edit `config.yaml` from the CLI

## API Endpoints

The CLI communicates with your AutumnWeb instance using the REST API.

Key endpoints used:
- `/get-auth-token/` - create token via username/password
- `/api/me/` - user identity for greeting
- `/api/timer/*` - timer management
- `/api/log/` - activity logs
- `/api/sessions/search/` - session search
- `/api/track/` - manual session tracking
- `/api/projects/grouped/` - project listings (grouped)
- `/api/contexts/`, `/api/tags/` - metadata discovery
- `/api/tally_by_sessons/`, `/api/tally_by_subprojects/`, `/api/list_sessions/` - charts

## Troubleshooting

### Authentication errors

- `autumn auth status`
- `autumn auth verify`
- Make sure `base_url` is correct and reachable

### Charts don’t display

- Use `--save` to render to a file
