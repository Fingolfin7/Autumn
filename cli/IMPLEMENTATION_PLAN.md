# CLI Feature Implementation Plan

## Overview

This plan covers implementing missing API features in the Autumn CLI, prioritized by value.

---

## Priority 1: High Value Features ✅ COMPLETE

### 1.1 Create Subproject ✅

**API:** `POST /api/create_subproject/`

**CLI Design:**
```bash
# Extend existing 'new' command
autumn new <project> -s <subproject> [-d "description"]

# Examples
autumn new "My Project" -s "Backend"
autumn new "My Project" -s "Frontend" -d "React UI components"
```

**Implementation:**
- Add `create_subproject(project, name, description)` to `api_client.py`
- Update `new_project` command in `commands/projects.py` to accept optional `-s/--subproject` flag
- When `-s` is provided, call `create_subproject()` instead of `create_project()`
- Add `--pick` support to select parent project interactively

---

### 1.2 Mark Project Status ✅

**API:** `POST /api/mark/`

**CLI Design:**
```bash
autumn mark <project> <status>
autumn mark <project> <status> --pick  # interactive project selection

# Valid statuses: active, paused, complete, archived
# Examples
autumn mark "Old Project" complete
autumn mark "Side Project" paused
```

**Implementation:**
- Add `mark_project_status(project, status)` to `api_client.py`
- Create new command `mark` in `commands/projects.py`
- Validate status is one of: active, paused, complete, archived
- Add `--pick` support for project selection

---

### 1.3 Rename Project/Subproject ✅

**API:** `POST /api/rename/`

**CLI Design:**
```bash
# Rename project
autumn rename <old_name> <new_name>

# Rename subproject (requires --project or -p)
autumn rename <old_sub> <new_sub> -p <project>

# Examples
autumn rename "Old Project" "New Project"
autumn rename "OldSub" "NewSub" -p "My Project"
```

**Implementation:**
- Add `rename_project(old_name, new_name)` to `api_client.py`
- Add `rename_subproject(project, old_sub, new_sub)` to `api_client.py`
- Create new command `rename` in `commands/projects.py`
- Detect type based on presence of `-p/--project` flag
- Add `--pick` support

---

### 1.4 Delete Project/Subproject ✅

**API:**
- `DELETE /api/project/delete/` (project)
- `DELETE /api/delete_subproject/<project>/<subproject>/` (subproject)

**CLI Design:**
```bash
# Delete project (with confirmation)
autumn delete-project <project>
autumn delete-project <project> --yes  # skip confirmation

# Delete subproject
autumn delete-sub <project> <subproject>
autumn delete-sub <project> <subproject> --yes
```

**Implementation:**
- Add `delete_project(name)` to `api_client.py`
- Add `delete_subproject(project, subproject)` to `api_client.py`
- Create `delete-project` command in `commands/projects.py`
- Create `delete-sub` command in `commands/projects.py`
- Add confirmation prompt (skip with `--yes/-y`)
- Add `--pick` support

---

### 1.5 Export Data ✅

**API:** `GET/POST /api/export/`

**CLI Design:**
```bash
autumn export [options]

# Options
--project, -p      Filter by project name
--start-date       Start date (YYYY-MM-DD)
--end-date         End date (YYYY-MM-DD)
--context, -c      Filter by context
--tags, -t         Filter by tags
--output, -o       Output file (default: stdout)
--compress         Compress output

# Examples
autumn export -o backup.json
autumn export -p "My Project" --start-date 2026-01-01
autumn export -o data.json --compress
```

**Implementation:**
- Add `export_data(filters, compress, autumn_compatible)` to `api_client.py`
- Create new command `export` in new file `commands/export_cmd.py`
- Support filtering by project, dates, context, tags
- Output to file or stdout
- Use `--compress` for compressed format

---

### 1.6 Audit (Recompute Totals) ✅

**API:** `POST /api/audit/`

**CLI Design:**
```bash
autumn audit

# Output shows what was recomputed
# Projects: 3 checked, 1 changed (delta: +9.0 min)
# Subprojects: 5 checked, 2 changed (delta: +18.0 min)
```

**Implementation:**
- Add `audit_totals()` to `api_client.py`
- Create new command `audit` in `commands/meta.py` (alongside `meta refresh`)
- Display summary of changes

---

## Priority 2: Medium Value Features ✅ COMPLETE

### 2.1 Search Projects ✅

**API:** `GET /api/search_projects/?search_term=...&status=...`

**CLI Design:**
```bash
autumn projects --search <term>
autumn projects --search <term> --status active

# Examples
autumn projects --search "web"
autumn projects --search "client" --status paused
```

**Implementation:**
- Add `search_projects(term, status)` to `api_client.py`
- Update `projects_list` command to accept `--search` option
- Display matching projects in same format as `autumn projects`

---

### 2.2 Project Totals ✅

**API:** `GET /api/totals/`

**CLI Design:**
```bash
autumn totals <project> [options]

# Options
--start-date       Start date filter
--end-date         End date filter

# Examples
autumn totals "My Project"
autumn totals "My Project" --start-date 2026-01-01
```

**Implementation:**
- Add `get_project_totals(project, filters)` to `api_client.py`
- Create new command `totals` in `commands/projects.py`
- Display project total and subproject breakdown
- Add `--pick` support

---

## Priority 3: Lower Priority Features ✅ COMPLETE

### 3.1 Merge Projects ✅

**API:** `POST /api/merge_projects/`

**CLI Design:**
```bash
autumn merge <project1> <project2> --into <new_name>
autumn merge <project1> <project2> --into <new_name> --yes

# Example
autumn merge "Project A" "Project B" --into "Combined Project"
```

**Implementation:**
- Add `merge_projects(p1, p2, new_name)` to `api_client.py`
- Create `merge` command in `commands/projects.py`
- Require confirmation (destructive operation)

---

### 3.2 Merge Subprojects ✅

**API:** `POST /api/merge_subprojects/`

**CLI Design:**
```bash
autumn merge-subs <project> <sub1> <sub2> --into <new_name>

# Example
autumn merge-subs "My Project" "Frontend" "UI" --into "Frontend UI"
```

**Implementation:**
- Add `merge_subprojects(project_id, s1, s2, new_name)` to `api_client.py`
- Create `merge-subs` command in `commands/projects.py`
- Require confirmation

---

### 3.3 Get Single Project Details ✅

**API:** `GET /api/get_project/<name>/`

**CLI Design:**
```bash
autumn project <name>

# Shows detailed info: status, total time, session count,
# avg session, context, tags, description, etc.
```

**Implementation:**
- Add `get_project(name)` to `api_client.py`
- Create `project` command in `commands/projects.py`
- Display formatted project details

---

### 3.4 Search Subprojects ✅

**API:** `GET /api/search_subprojects/?project_name=...&search_term=...`

**CLI Design:**
```bash
autumn subprojects <project> --search <term>

# Example
autumn subprojects "My Project" --search "api"
```

**Implementation:**
- Add `search_subprojects(project, term)` to `api_client.py`
- Update `subprojects` command to accept `--search` option

---

## Implementation Order

```
Phase 1 (High Priority): ✅ COMPLETE
├── 1.1 Create Subproject ✅
├── 1.2 Mark Project Status ✅
├── 1.3 Rename Project/Subproject ✅
├── 1.4 Delete Project/Subproject ✅
├── 1.5 Export Data ✅
└── 1.6 Audit ✅

Phase 2 (Medium Priority): ✅ COMPLETE
├── 2.1 Search Projects ✅
└── 2.2 Project Totals ✅

Phase 3 (Lower Priority): ✅ COMPLETE
├── 3.1 Merge Projects ✅
├── 3.2 Merge Subprojects ✅
├── 3.3 Get Single Project Details ✅
└── 3.4 Search Subprojects ✅
```

---

## Files Modified/Created

| File | Changes | Status |
|------|---------|--------|
| `api_client.py` | Added 15+ new API methods (incl. merge, search) | ✅ |
| `commands/projects.py` | Added mark, rename, delete-project, delete-sub, totals, project, merge, merge-subs + search options | ✅ |
| `commands/export_cmd.py` | **NEW** - Export command | ✅ |
| `commands/meta.py` | Added audit command | ✅ |
| `cli.py` | Registered all new commands | ✅ |
| `tests/test_api_client_new_methods.py` | **NEW** - 14 tests for API methods | ✅ |

---

## Testing Strategy

1. Add unit tests for new API client methods (mock responses)
2. Manual testing against live API
3. Test `--pick` integration with new commands
4. Test error handling (conflicts, not found, etc.)

---

## Notes

- All new commands should support `--pick` where project/subproject selection makes sense
- Use consistent styling with existing commands (Rich console, autumn.* tags)
- Add confirmation prompts for destructive operations (delete, merge)
- Handle API errors gracefully with user-friendly messages
