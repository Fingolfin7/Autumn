# Autumn TUI Dashboard - Implementation Plan

## 1. Visual Mockup
```text
 ───────────────── AUTUMN DASH ───────────────── [ACTIVE] AutumnWeb (CLI) • 01:12:45 ───
                                                                                       
  WEEKLY TALLY                        DAILY INTENSITY (HOURS)                          
 ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   
 ┃ AutumnWeb  [██████░░░] 72%   ┃    ┃ Mon [###########---------] 5.5h             ┃   
 ┃ Chess      [██░░░░░░░] 12%   ┃    ┃ Tue [################----] 8.2h             ┃   
 ┃ Bible      [█░░░░░░░░]  8%   ┃    ┃ Wed [#############-------] 6.1h             ┃   
 ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   
                                                                                       
  TOP SUBPROJECTS (AUTUMNWEB)         WEEKLY TRENDS                                    
 ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   
 ┃ CLI        [██████░░░] 60%   ┃    ┃ Total:    99.3h                             ┃   
 ┃ backend    [██░░░░░░░] 20%   ┃    ┃ Change:   +12% vs Last Week                 ┃   
 ┃ front-end  [█░░░░░░░░] 10%   ┃    ┃ Streak:   14 Days                           ┃   
 ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   
                                                                                       
  TERMINAL LOG                                                                         
 ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
 ┃ [19:38] Session tracked: AutumnWeb (CLI) - 68 minutes                              ┃
 ┃ [19:40] Reminder set for 25m                                                       ┃
 ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                                                                       
  autumn> start Chess -s tactics                                                       
 ───────────────────────────────────────────────────────────────────────────────────────
```

## 2. Component Details

### A. Header (Live Status)
* **Active Timer**: Displays `Project (Subproject)` and a live-ticking clock `HH:MM:SS`.
* **Visual Cues**: Colors transition from Green (active) to Dim (stopped/paused).

### B. Analytical Panels
* **Weekly Tally**: High-level distribution of time across projects for the current week.
* **Daily Intensity**: Visual workload bars for the last 7 days (including today).
* **Top Subprojects**: Focused breakdown of the most active project this week.
* **Weekly Trends**: Statistical summary (Total Time, Week-over-Week Change, Current Streak, Avg Daily Hours).

### C. Interaction Layer
* **Terminal Log**: Keeps a rolling history of the last 5 command outputs.
* **Fixed Command Prompt**: A permanent `autumn>` prompt at the bottom.
* **Non-blocking Input**: Allows the user to type commands while the dashboard continues to refresh and tick.

## 3. Tech Stack
* **UI/Layout**: `rich` (Layout, Panels, Live, Table, Bar).
* **Input Handling**: `prompt_toolkit` for non-blocking asynchronous input with history support.
* **Command Integration**: `click` (invoking existing CLI commands internally).
* **Networking**: `requests` via the existing `APIClient`.
* **State Management**: Custom `DashboardState` manager.

## 4. Implementation Plan

### Phase 1: Foundation
* Create `cli/autumn_cli/commands/dashboard.py` and register the `dash` command.
* Implement `DashboardState` to handle data polling and session calculation.
* Build the static `rich.layout` structure.

### Phase 2: Live Refresh & Analytics
* Set up the `rich.live` loop.
* Implement the data aggregation for Trends and Intensity (calculating WoW % change and daily totals).
* Add the live clock logic.

### Phase 3: Command Integration
* Integrate `prompt_toolkit` for the bottom input bar.
* Create a command-capture wrapper to redirect `click` output into the Terminal Log panel.
* Add logic to trigger an immediate state refresh after state-changing commands (e.g., `start`, `stop`).

### Phase 4: Polish & Refinement
* Ensure cross-platform compatibility for box-drawing characters.
* Handle terminal resizing gracefully.
* Final styling and theme integration.
