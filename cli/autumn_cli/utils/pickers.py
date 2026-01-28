"""Interactive pickers for optional CLI prompting.

These are *opt-in* (used only when commands pass pick=True).
Supports fuzzy search and recency-based ordering.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

import click

from .console import console


def _fuzzy_match(query: str, text: str) -> Tuple[bool, int]:
    """Simple fuzzy matching. Returns (is_match, score).

    Higher score = better match. Uses substring and character matching.
    """
    query = query.lower().strip()
    text_lower = text.lower()

    if not query:
        return True, 0

    # Exact prefix match - highest score
    if text_lower.startswith(query):
        return True, 1000 + len(query)

    # Contains substring - high score
    if query in text_lower:
        return True, 500 + len(query)

    # Fuzzy character matching - check if all chars appear in order
    query_idx = 0
    score = 0
    for char in text_lower:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
            score += 10

    if query_idx == len(query):
        return True, score

    return False, 0


def _fuzzy_filter(query: str, items: Sequence[str]) -> List[str]:
    """Filter and sort items by fuzzy match score."""
    if not query.strip():
        return list(items)

    matches = []
    for item in items:
        is_match, score = _fuzzy_match(query, item)
        if is_match:
            matches.append((score, item))

    # Sort by score descending
    matches.sort(key=lambda x: -x[0])
    return [item for _, item in matches]


def pick_from_names(
    *,
    label: str,
    names: Sequence[str],
    default: Optional[str] = None,
    recent: Optional[Sequence[str]] = None,
    max_display: int = 10,
) -> Optional[str]:
    """Prompt user to pick a value from a list with fuzzy search.

    Args:
        label: What we're picking (e.g., "project", "context")
        names: All available names
        default: Default selection
        recent: Recently used items to show first
        max_display: Max items to show at once (default 10)

    Returns:
        The selected name or None if cancelled/no options
    """
    cleaned = [n for n in names if n]
    if not cleaned:
        return None

    # Build display list: recent first, then others
    recent_set = set(recent or [])
    recent_items = [n for n in (recent or []) if n in cleaned]
    other_items = [n for n in cleaned if n not in recent_set]

    # Combine: recent first, then alphabetically sorted others
    all_items = recent_items + sorted(other_items)

    current_filter = ""

    while True:
        # Apply fuzzy filter
        if current_filter:
            filtered = _fuzzy_filter(current_filter, all_items)
        else:
            filtered = all_items

        if not filtered:
            console.print(f"[autumn.warn]No matches for '{current_filter}'[/]")
            current_filter = ""
            continue

        # Display list
        display_items = filtered[:max_display]
        has_more = len(filtered) > max_display

        console.print()
        if current_filter:
            console.print(f"[autumn.label]Select {label}[/] [dim](filter: {current_filter})[/]")
        else:
            console.print(f"[autumn.label]Select {label}[/]")

        for i, name in enumerate(display_items, start=1):
            if name in recent_set:
                console.print(f"  [autumn.ok]{i})[/] [autumn.project]{name}[/] [dim](recent)[/]")
            else:
                console.print(f"  [dim]{i})[/] {name}")

        if has_more:
            remaining = len(filtered) - max_display
            console.print(f"  [dim]... and {remaining} more (type to filter)[/]")

        # Prompt
        prompt_text = f"Enter number (1-{len(display_items)})"
        if not current_filter:
            prompt_text += " or type to search"
        prompt_text += " [q=quit]"

        raw = click.prompt(prompt_text, default="", show_default=False)
        raw = raw.strip()

        # Handle quit
        if raw.lower() == 'q':
            return None

        # Handle empty input - clear filter
        if not raw:
            if current_filter:
                current_filter = ""
                continue
            else:
                # No filter and empty input - just continue
                continue

        # Try to parse as number
        try:
            idx = int(raw)
            if 1 <= idx <= len(display_items):
                return display_items[idx - 1]
            else:
                console.print(f"[autumn.warn]Enter 1-{len(display_items)}[/]")
                continue
        except ValueError:
            pass

        # Not a number - treat as filter text
        current_filter = raw


def pick_project(
    client,
    *,
    label: str = "project",
    default: Optional[str] = None,
) -> Optional[str]:
    """Pick a project with recency ordering.

    Fetches projects and recent activity to order by recency.
    """
    # Get all projects
    projects_meta = client.get_discovery_projects()
    all_projects = [p.get("name") for p in projects_meta.get("projects", []) if p.get("name")]

    if not all_projects:
        console.print("[dim]No projects found.[/]")
        return None

    # Get recent projects from activity
    recent = []
    try:
        activity = client.get_recent_activity_snippet(ttl_seconds=600)
        # Collect recent project names
        if activity.get("last_project"):
            recent.append(activity["last_project"])
        if activity.get("today_project") and activity["today_project"] not in recent:
            recent.append(activity["today_project"])
        if activity.get("most_frequent_project") and activity["most_frequent_project"] not in recent:
            recent.append(activity["most_frequent_project"])
    except Exception:
        pass

    return pick_from_names(
        label=label,
        names=all_projects,
        default=default,
        recent=recent,
    )


def pick_subproject(
    client,
    project: str,
    *,
    label: str = "subproject",
) -> Optional[str]:
    """Pick a subproject for a given project."""
    try:
        result = client.list_subprojects(project, compact=True)
        subs = result.get("subprojects", []) if isinstance(result, dict) else result

        # Handle both string list and dict list
        names = []
        for sub in subs:
            if isinstance(sub, str):
                names.append(sub)
            elif isinstance(sub, dict):
                name = sub.get("name")
                if name:
                    names.append(name)

        if not names:
            return None

        return pick_from_names(label=label, names=names)
    except Exception:
        return None


def pick_context(
    client,
    *,
    label: str = "context",
    include_all: bool = True,
) -> Optional[str]:
    """Pick a context."""
    meta = client.get_discovery_meta()
    contexts = meta.get("contexts", [])
    names = [c.get("name") for c in contexts if c.get("name")]

    if include_all:
        names = ["all"] + names

    if not names:
        return None

    return pick_from_names(label=label, names=names)


def pick_tag(
    client,
    *,
    label: str = "tag",
) -> Optional[str]:
    """Pick a tag."""
    meta = client.get_discovery_meta()
    tags = meta.get("tags", [])
    names = [t.get("name") for t in tags if t.get("name")]

    if not names:
        return None

    return pick_from_names(label=label, names=names)


def normalize_repeatable(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        s = str(v).strip()
        if s:
            out.append(s)
    return out
