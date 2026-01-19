# Autumn CLI Style Guide

This document defines the standards for command-line arguments, output formatting, and color usage to ensure consistency across the Autumn CLI. It bridges the "Legacy" style with the modern `rich`-based implementation.

## 1. Command-Line Arguments (Flags)

We prioritize consistency across commands. When a concept (like "project" or "note") appears, it should use the same flag.

### Standard Short Flags

| Concept | Flag | Long Flag | Notes |
| :--- | :--- | :--- | :--- |
| **Project** | `-p` | `--project` | |
| **Subprojects** | `-s` | `--subprojects` | |
| **Tags** | `-t` | `--tags` | |
| **Context** | `-c` | `--context` | |
| **Note** | `-n` | `--note` | |
| **Period** | `-P` | `--period` | Uppercase `-P` to avoid conflict with project `-p`. |
| **Status** | `-S` | `--status` | `-s` is taken by subprojects. |
| **Start Date** | | `--start-date` | |
| **End Date** | | `--end-date` | |
| **ID** | `-i` | `--id` | Used for Session IDs. |
| **Background** | | `--background` | |
| **Quiet** | `-q` | `--quiet` | |

### Positional Arguments
*   **Primary Entities:** Commands acting on a specific primary entity (e.g., `start <project>`, `subprojects <project>`) should take the name as a positional argument where appropriate, or use `-p`.
*   **Search/List:** Commands that list or search (e.g., `log`, `charts`) should use flags for filtering.

## 2. Color Palette & Styling

We use the `rich` library for formatting. This section maps logical states to colors, inspired by the Legacy implementation.

| State / Entity | Color | Rich Tag |
| :--- | :--- | :--- |
| **Active / Success** | **Green** | `[autumn.ok]` |
| **Paused** | **Magenta** | `[autumn.paused]` |
| **Complete / Warning** | **Yellow** | `[autumn.warn]` |
| **Error / Deleted** | **Red** | `[autumn.err]` |
| **Project Name** | **Red** | `[autumn.project]` |
| **Subproject Name** | **Blue** | `[autumn.subproject]` |
| **Label / Key** | **Dim White** | `[autumn.label]` |
| **Muted / Info** | **Dim** | `[autumn.muted]` |
| **Highlight** | **Bold White** | `[autumn.highlight]`|
| **Time (Start/End)** | **Cyan** | `[autumn.time]` |
| **Duration** | **Green** | `[autumn.duration]` |

### Output Formats

#### 1. Key-Value Pairs (Single Entity)
When displaying a single object (like a started timer or tracked session), use a vertical key-value list.

**Example Output:**
```
Action Successful
Project: MyProject
Duration: 25m
Note: Working on the thing
```

#### 2. Date & Time Formatting
*   **Dates:** Use ISO-8601 `YYYY-MM-DD` for clarity and sorting.
*   **Times:** Use `HH:MM:SS` (24-hour) for consistency.
*   **Durations:** Prefer compact `1h 25m` over verbose `1 hour 25 minutes` for lists.
*   **Coloring:**
    *   Timestamps (Start/End): `[autumn.time]`.
    *   Durations (Elapsed/Total): `[autumn.duration]`.

#### 3. Lists & Tables
*   **Complex Data:** Use `rich.table.Table` for multi-column data (logs, summaries).
*   **Simple Lists:** Use comma-separated strings or simple vertical lists if columns aren't needed.

#### 4. Messages
*   **Success:** Start with `[autumn.ok]`.
*   **Error:** Start with `[autumn.err]Error:[/]`.
*   **Info:** Use `[autumn.muted]` for background info or prompts.
