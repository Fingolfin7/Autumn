"""Helpers to resolve user-entered context/tag/project values to canonical API parameters.

Goal: make CLI robust to capitalization differences and allow users to specify
contexts/tags/projects by either ID or name, with optional alias support.

We resolve names via API discovery endpoints and then pass IDs downstream.

Alias configuration is stored in ~/.autumn/config.yaml under the `aliases` key:
    aliases:
      projects:
        cli: "Autumn CLI"
      contexts:
        home: Personal
      tags:
        imp: Important
      subprojects:
        "Autumn CLI":
          fe: Frontend
          be: Backend
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, List

from ..config import get_account_aliases


def _is_int_string(value: str) -> bool:
    try:
        int(str(value).strip())
        return True
    except (ValueError, TypeError):
        return False


def _norm_key(value: str) -> str:
    return str(value).strip().casefold()


def _get_alias(alias_type: str, name: str) -> Optional[str]:
    """Look up alias from config.

    Args:
        alias_type: One of 'projects', 'contexts', 'tags'
        name: The alias key to look up

    Returns:
        The canonical name if alias exists, None otherwise
    """
    aliases = get_account_aliases().get(alias_type, {})
    if not isinstance(aliases, dict):
        return None
    # Case-insensitive alias lookup
    for alias_key, target in aliases.items():
        if _norm_key(alias_key) == _norm_key(name):
            return target
    return None


def _get_subproject_alias(name: str, project: Optional[str] = None) -> Optional[str]:
    """Look up subproject alias from config.

    Subproject aliases are scoped to their parent project.

    Args:
        name: The alias key to look up
        project: The parent project name (required for scoped lookup)

    Returns:
        The canonical subproject name if alias exists, None otherwise
    """
    all_sub_aliases = get_account_aliases().get("subprojects", {})
    if not isinstance(all_sub_aliases, dict):
        return None

    if not project:
        return None

    # Find matching project key (case-insensitive)
    project_aliases = None
    for proj_key, aliases in all_sub_aliases.items():
        if _norm_key(proj_key) == _norm_key(project):
            project_aliases = aliases
            break

    if not project_aliases or not isinstance(project_aliases, dict):
        return None

    # Case-insensitive alias lookup within project
    for alias_key, target in project_aliases.items():
        if _norm_key(alias_key) == _norm_key(name):
            return target

    return None


@dataclass(frozen=True)
class ResolveResult:
    value: Optional[str]
    warning: Optional[str] = None
    # Informational: set when a partial name was expanded to a full one.
    note: Optional[str] = None


def resolve_context_param(
    *,
    context: Optional[str],
    contexts: Iterable[dict],
) -> ResolveResult:
    """Resolve a context argument (id or name) into a context id string.

    If context is falsy -> returns None.
    If context is "all" -> returns "all".
    If context is numeric -> returns as-is.
    Otherwise checks aliases, then matches against contexts by name (case-insensitive).
    """
    if not context:
        return ResolveResult(None)

    raw = str(context).strip()
    if not raw:
        return ResolveResult(None)

    if raw.casefold() == "all":
        return ResolveResult("all")

    if _is_int_string(raw):
        return ResolveResult(str(int(raw)))

    # Check alias first
    aliased = _get_alias("contexts", raw)
    if aliased:
        raw = aliased

    lookup = {_norm_key(c.get("name", "")): c for c in contexts}
    hit = lookup.get(_norm_key(raw))
    if hit and hit.get("id") is not None:
        return ResolveResult(str(hit["id"]))

    return ResolveResult(raw, warning=f"Unknown context '{context}'. Passing through as provided.")


def resolve_tag_params(
    *,
    tags: Optional[Iterable[str]],
    known_tags: Iterable[dict],
) -> Tuple[List[str], List[str]]:
    """Resolve tag args (ids or names) into canonical tag names.

    Returns: (resolved_tag_names, warnings)

    - numeric strings (IDs) are kept as-is for backwards compatibility
    - aliases are expanded first
    - names are matched case-insensitively against known_tags and resolved to canonical names
    - unknown names are passed through unchanged (API supports names too), but we warn
    """
    if not tags:
        return [], []

    # Build lookup: normalized name -> canonical name
    name_lookup = {}
    for t in known_tags:
        name = t.get("name")
        if name:
            name_lookup[_norm_key(name)] = name

    resolved: List[str] = []
    warnings: List[str] = []

    for tag in tags:
        raw = str(tag).strip()
        if not raw:
            continue

        # Keep numeric IDs as-is for backwards compatibility
        if _is_int_string(raw):
            resolved.append(str(int(raw)))
            continue

        # Check alias first
        aliased = _get_alias("tags", raw)
        if aliased:
            raw = aliased

        # Resolve to canonical name (case-insensitive match)
        hit = name_lookup.get(_norm_key(raw))
        if hit:
            resolved.append(hit)
        else:
            resolved.append(raw)
            warnings.append(f"Unknown tag '{tag}'. Passing through as provided.")

    return resolved, warnings


def resolve_project_param(
    *,
    project: str,
    projects: Iterable[dict],
    partial: bool = False,
) -> ResolveResult:
    """Resolve a project argument to canonical project name.

    Steps:
    1. Check aliases first
    2. Case-insensitive match against projects list
    3. With ``partial``, a unique prefix (then unique substring) match
    4. Pass through with warning if unknown, suggesting close names

    Args:
        project: User-provided project name/alias
        projects: Iterable of project dicts with 'name' key
        partial: Accept an unambiguous partial name such as ``autu``

    Returns:
        ResolveResult with canonical name or original value with warning
    """
    if not project:
        return ResolveResult(None)

    raw = str(project).strip()
    if not raw:
        return ResolveResult(None)

    # Check alias first
    aliased = _get_alias("projects", raw)
    if aliased:
        raw = aliased

    # Build case-insensitive lookup
    name_lookup = {}
    for p in projects:
        name = p.get("name", "")
        if name:
            name_lookup[_norm_key(name)] = name

    # Try to match
    folded = _norm_key(raw)
    hit = name_lookup.get(folded)
    if hit:
        return ResolveResult(hit)

    candidates: List[str] = []
    if partial and folded:
        for matches in (
            lambda key: key.startswith(folded),
            lambda key: folded in key,
        ):
            candidates = sorted(
                name for key, name in name_lookup.items() if matches(key)
            )
            if len(candidates) == 1:
                return ResolveResult(
                    candidates[0],
                    note=f"Using project '{candidates[0]}' for '{project}'.",
                )
            if candidates:
                break

    if not candidates:
        close = difflib.get_close_matches(folded, list(name_lookup), n=3, cutoff=0.6)
        candidates = [name_lookup[key] for key in close]
    hint = f" Did you mean: {', '.join(candidates[:5])}?" if candidates else ""
    return ResolveResult(
        raw,
        warning=f"Unknown project '{project}'. Passing through as provided.{hint}",
    )


def resolve_project_name(client, project: str, *, partial: bool = True) -> str:
    """Resolve a project name against the cached project list.

    Prints any warning or partial-match note to stderr and returns the
    canonical name (or the input unchanged when it matches nothing).
    """
    from .console import err_console

    projects = client.get_discovery_projects().get("projects", [])
    result = resolve_project_param(project=project, projects=projects, partial=partial)
    if result.warning:
        err_console.print(f"[autumn.warn]Warning:[/] {result.warning}")
    if result.note:
        err_console.print(f"[autumn.muted]{result.note}[/]")
    return result.value or project


def resolve_subproject_params(
    *,
    subprojects: Optional[Iterable[str]],
    known_subprojects: Iterable[dict],
    project: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Resolve subproject args to canonical names.

    Returns: (resolved_names, warnings)

    Steps for each subproject:
    1. Check project-scoped aliases first (if project is provided)
    2. Case-insensitive match against known_subprojects
    3. Pass through with warning if unknown

    Args:
        subprojects: User-provided subproject names/aliases
        known_subprojects: Iterable of subproject dicts with 'name' key,
                          or strings for compact format
        project: Parent project name (for scoped alias lookup)

    Returns:
        Tuple of (resolved_names, warnings)
    """
    if not subprojects:
        return [], []

    # Build case-insensitive lookup
    name_lookup = {}
    for sub in known_subprojects:
        if isinstance(sub, str):
            name = sub
        else:
            name = sub.get("name", "")
        if name:
            name_lookup[_norm_key(name)] = name

    resolved: List[str] = []
    warnings: List[str] = []

    for sub in subprojects:
        raw = str(sub).strip()
        if not raw:
            continue

        # Check project-scoped alias first
        aliased = _get_subproject_alias(raw, project)
        if aliased:
            raw = aliased

        # Try to match
        hit = name_lookup.get(_norm_key(raw))
        if hit:
            resolved.append(hit)
        else:
            resolved.append(raw)
            warnings.append(f"Unknown subproject '{sub}'. Passing through as provided.")

    return resolved, warnings
