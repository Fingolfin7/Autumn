"""Helpers to resolve user-entered context/tag values to canonical API parameters.

Goal: make CLI robust to capitalization differences and allow users to specify
contexts/tags by either ID or name.

We resolve names via API discovery endpoints and then pass IDs downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, List


def _is_int_string(value: str) -> bool:
    try:
        int(str(value).strip())
        return True
    except Exception:
        return False


def _norm_key(value: str) -> str:
    return str(value).strip().casefold()


@dataclass(frozen=True)
class ResolveResult:
    value: Optional[str]
    warning: Optional[str] = None


def resolve_context_param(
    *,
    context: Optional[str],
    contexts: Iterable[dict],
) -> ResolveResult:
    """Resolve a context argument (id or name) into a context id string.

    If context is falsy -> returns None.
    If context is "all" -> returns "all".
    If context is numeric -> returns as-is.
    Otherwise matches against contexts by name (case-insensitive).
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
    """Resolve tag args (ids or names) into a list of tag id strings.

    Returns: (resolved_tag_values, warnings)

    - numeric strings are kept
    - names are matched case-insensitively against known_tags
    - unknown names are passed through unchanged (API supports names too), but we warn
    """
    if not tags:
        return [], []

    name_to_id = {}
    for t in known_tags:
        name = t.get("name")
        tid = t.get("id")
        if name and tid is not None:
            name_to_id[_norm_key(name)] = str(tid)

    resolved: List[str] = []
    warnings: List[str] = []

    for tag in tags:
        raw = str(tag).strip()
        if not raw:
            continue

        if _is_int_string(raw):
            resolved.append(str(int(raw)))
            continue

        hit = name_to_id.get(_norm_key(raw))
        if hit:
            resolved.append(hit)
        else:
            resolved.append(raw)
            warnings.append(f"Unknown tag '{tag}'. Passing through as provided.")

    return resolved, warnings

