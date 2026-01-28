"""Shell completion callbacks for Click options/arguments.

These functions provide tab-completion for project names, context names, tag names,
and subproject names by fetching from the cached discovery endpoints.
"""

from __future__ import annotations

from typing import List

from click.shell_completion import CompletionItem


def complete_project(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Completion for project names from cache.

    Returns matching project names (case-insensitive prefix match).
    """
    try:
        from ..api_client import APIClient

        client = APIClient()
        projects_meta = client.get_discovery_projects()
        projects = projects_meta.get("projects", [])

        items = []
        incomplete_lower = incomplete.lower()

        for proj in projects:
            name = proj.get("name", "")
            if name and name.lower().startswith(incomplete_lower):
                # Include status as help text if available
                status = proj.get("status", "")
                help_text = f"({status})" if status else None
                items.append(CompletionItem(name, help=help_text))

        return items
    except Exception:
        return []


def complete_context(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Completion for context names.

    Includes "all" as a special option plus cached context names.
    """
    try:
        from ..api_client import APIClient

        client = APIClient()
        meta = client.get_discovery_meta()
        contexts = meta.get("contexts", [])

        items = []
        incomplete_lower = incomplete.lower()

        # Add "all" as special option
        if "all".startswith(incomplete_lower):
            items.append(CompletionItem("all", help="All contexts"))

        for ctx_item in contexts:
            name = ctx_item.get("name", "")
            if name and name.lower().startswith(incomplete_lower):
                items.append(CompletionItem(name))

        return items
    except Exception:
        return []


def complete_tag(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Completion for tag names."""
    try:
        from ..api_client import APIClient

        client = APIClient()
        meta = client.get_discovery_meta()
        tags = meta.get("tags", [])

        items = []
        incomplete_lower = incomplete.lower()

        for tag in tags:
            name = tag.get("name", "")
            if name and name.lower().startswith(incomplete_lower):
                items.append(CompletionItem(name))

        return items
    except Exception:
        return []


def complete_subproject(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Completion for subproject names.

    This is context-aware: if a project is already specified in the command,
    it will only show subprojects for that project.
    """
    try:
        from ..api_client import APIClient

        client = APIClient()

        # Try to get the project from the context (if already specified)
        project = None
        if ctx.params:
            project = ctx.params.get("project")

        if not project:
            # Can't complete subprojects without a project context
            return []

        # Fetch subprojects for the project
        result = client.list_subprojects(project, compact=True)
        subprojects = result.get("subprojects", []) if isinstance(result, dict) else result

        items = []
        incomplete_lower = incomplete.lower()

        for sub in subprojects:
            if isinstance(sub, str):
                name = sub
            else:
                name = sub.get("name", "")

            if name and name.lower().startswith(incomplete_lower):
                items.append(CompletionItem(name))

        return items
    except Exception:
        return []
