# Autumn CLI Style Guide

This document defines the standards for command-line arguments, output formatting, and color usage to ensure consistency across the Autumn CLI. It bridges the "Legacy" style with the modern `rich`-based implementation.

## 1. Command-Line Arguments (Flags)

We prioritize consistency across commands. When a concept (like "project" or "note") appears, it should use the same flag.

### Standard Short Flags

| Concept | Flag | Long Flag | Notes |
| :--- | :--- | :--- | :--- |
| **Project** | `-p` | `--project` | **CHANGE:** `log` command currently uses `-p` for period. This must change to `-P` or `--period`. |
| **Subprojects** | `-s` | `--subprojects` | |
| **Tags** | `-t` | `--tags` | **CHANGE:** `charts` command currently uses `-g`. Update to `-t`. |
| **Context** | `-c` | `--context` | |
| **Note** | `-n` | `--note` | Legacy used `-sn`. `-n` is preferred. |
| **Period** | `-P` | `--period` | Uppercase `-P` to avoid conflict with project `-p`. Legacy used `-pd`. |
| **Status** | `-S` | `--status` | `-s` is taken by subprojects. |
| **Start Date** | | `--start-date` | |
| **End Date** | | `--end-date` | |
| **ID** | `-i` | `--id` | Used for Session IDs. |
| **Background** | | `--background` | |
| **Quiet** | `-q` | `--quiet` | |

### Positional Arguments
*   **Primary Entities:** Commands acting on a specific primary entity (e.g., `start <project>`) should take the name as a positional argument.
*   **Search/List:** Commands that list or search (e.g., `log`, `charts`) should use flags for filtering.

## 2. Color Palette & Styling

We use the `rich` library for formatting. This section maps logical states to colors, inspired by the Legacy implementation.

| State / Entity | Color | Rich Tag | Legacy Equivalent |
| :--- | :--- | :--- | :--- |
| **Active / Success** | **Green** | `[autumn.ok]` | `[green]`, `[bright green]` |
| **Paused** | **Magenta** | `[autumn.paused]` | `[magenta]` |
| **Complete / Warning** | **Yellow** | `[autumn.warn]` | `[yellow]` |
| **Error / Deleted** | **Red** | `[autumn.err]` | `[red]`, `[bright red]` |
| **Project Name** | **Red** | `[autumn.project]` | `[bright red]` (Legacy). Restored from Cyan. |
| **Subproject Name** | **Blue** | `[autumn.subproject]` | `[_text256_26_]` (Legacy Color 26) |
| **Label / Key** | **Dim White** | `[autumn.label]` | (Standard text) |
| **Muted / Info** | **Dim** | `[autumn.muted]` | (Standard text) |
| **Highlight** | **Bold White** | `[autumn.highlight]`| `[bold]` |
| **Time (Start/End)** | **Cyan** | `[autumn.time]` | `[cyan]` |
| **Duration** | **Green** | `[autumn.duration]` | `[_text256_34_]` (Legacy Green) |

### Output Formats

#### 1. Key-Value Pairs (Single Entity)
When displaying a single object (like a started timer or tracked session), use a vertical key-value list.

**Format:**
```
[autumn.ok]Action Successful[/]
[autumn.label]Project:[/] [autumn.project]MyProject[/]
[autumn.label]Duration:[/] [autumn.duration]25m[/]
[autumn.label]Note:[/] Working on the thing
```

#### 2. Date & Time Formatting
*   **Dates:** Use ISO-8601 `YYYY-MM-DD` for clarity and sorting. (Legacy used `MM-DD-YYYY`).
*   **Times:** Use `HH:MM:SS` (24-hour) for consistency.
*   **Durations:** Prefer compact `1h 25m` over verbose `1 hour 25 minutes` for lists.
*   **Coloring:**
    *   Timestamps (Start/End): `[autumn.time]`.
    *   Durations (Elapsed/Total): `[autumn.duration]`.

#### 3. Lists & Tables
*   **Complex Data:** Use `rich.table.Table` for multi-column data (logs, summaries).
*   **Simple Lists:** Use comma-separated strings or simple vertical lists if columns aren't needed.

#### 3. Messages
*   **Success:** Start with `[autumn.ok]`.
*   **Error:** Start with `[autumn.err]Error:[/]`.
*   **Info:** Use `[autumn.muted]` for background info or prompts.

## 3. Implementation Plan

To align the current CLI with this guide:

1.  **Refactor `log` / `sessions.py`:**
    *   Change `--period` short flag from `-p` to `-P`.
    *   Add `-p` alias for `--project`.
2.  **Refactor `charts.py`:**
    *   Change `--tag` short flag from `-g` to `-t`.
3.  **Refactor `projects.py`:**
    *   Ensure `-t` is used for tags (already is).
    *   Add `-S` for status if missing.
4.  **Theme Update:**
    *   Update `console.py` to define the custom theme keys (`autumn.ok`, `autumn.project`, etc.) to match the palette above.
    *   Audit `console.print` calls to use these semantic tags instead of raw colors.
