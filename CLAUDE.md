# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Autumn CLI is a command-line interface for AutumnWeb, a time-tracking and project management application. It enables users to track work sessions, manage projects, set reminders, and visualize productivity through charts.

- **Python 3.8+** required
- Uses **Click** for CLI, **Rich** for terminal output, **requests** for API communication

## Platform Support

**Cross-platform compatibility is required.** All features must work on:

| Platform | Priority | Shell(s) |
|----------|----------|----------|
| **Windows** | Primary | PowerShell, cmd.exe |
| **macOS** | Required | zsh (default), bash |
| Linux | Optional | bash, zsh |

When implementing features:
- Test on Windows first (primary development environment)
- Avoid Unix-specific assumptions (paths, shell commands, process handling)
- Use `pathlib` for file paths, not string concatenation
- Prefer cross-platform interactive pickers over shell-specific completion

## Build & Test Commands

```bash
# Install in development mode (from cli/ directory)
pip install -e .
# OR with uv
uv pip install -e .

# Run all tests
cd cli/
pytest tests/

# Run specific test
pytest tests/test_config_knobs.py::test_greeting_weights_roundtrip -v

# Run CLI after installation
autumn --help
```

## Architecture

```
cli/
├── autumn_cli/
│   ├── cli.py           # Entry point, Click CLI group, auth commands
│   ├── api_client.py    # HTTP client for AutumnWeb REST API (~550 lines)
│   ├── config.py        # YAML config management (~/.autumn/config.yaml)
│   ├── commands/        # Command implementations
│   │   ├── timer.py     # start, stop, restart, delete, status
│   │   ├── sessions.py  # log, track
│   │   ├── projects.py  # projects, subprojects, new
│   │   ├── charts.py    # pie, bar, scatter, calendar, heatmap, wordcloud
│   │   ├── remind_cmd.py      # Ad-hoc reminder setup
│   │   └── reminders_cmd.py   # Reminder management
│   └── utils/           # Utility modules (38 files)
│       ├── console.py        # Rich console output with custom color tags
│       ├── datetime_parse.py # Flexible date parsing
│       ├── duration_parse.py # Duration string parsing
│       ├── notify.py         # Cross-platform notifications
│       ├── reminder_daemon.py # Background reminder processes
│       └── charts.py         # Matplotlib/Seaborn visualization
├── tests/               # pytest test suite (67 tests)
├── AutumnWeb API Docs.md  # Comprehensive API reference
└── STYLE_GUIDE.md       # CLI output style consistency guide
```

## Key Patterns

**Configuration:** YAML at `~/.autumn/config.yaml` with dotted-path access. Environment variables (`AUTUMN_API_KEY`, `AUTUMN_API_BASE`, `AUTUMN_INSECURE`) take precedence.

**API Client:** RESTful client with TTL-based caching for metadata (projects, contexts, tags, user info).

**Background Reminders:** Spawned as detached processes with JSON registry for persistence at `~/.autumn/reminders.json`.

**Notifications:** Cross-platform via plyer (Windows toast, macOS terminal-notifier, Linux notifications).

## CLI Flag Conventions

| Concept | Short | Long | Notes |
|---------|-------|------|-------|
| Project | -p | --project | |
| Subprojects | -s | --subprojects | |
| Tags | -t | --tags | |
| Context | -c | --context | |
| Note | -n | --note | |
| Period | -P | --period | Uppercase to avoid conflict with -p |
| Status | -S | --status | |
| ID | -i | --id | Session ID |

## Style Guide (Rich Color Tags)

| State | Tag |
|-------|-----|
| Success/Active | `[autumn.ok]` (green) |
| Paused | `[autumn.paused]` (magenta) |
| Warning/Complete | `[autumn.warn]` (yellow) |
| Error/Deleted | `[autumn.err]` (red) |
| Project Name | `[autumn.project]` (red) |
| Subproject Name | `[autumn.subproject]` (blue) |
| Timestamp | `[autumn.time]` (cyan) |
| Duration | `[autumn.duration]` (green) |

## Key Documentation

- `cli/README.md` - Usage guide
- `cli/STYLE_GUIDE.md` - Output formatting consistency
- `cli/AutumnWeb API Docs.md` - Backend API reference
