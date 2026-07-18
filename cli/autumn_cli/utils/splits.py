"""Parsing and resolution helpers for session subproject splits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

from ..api_client import APIError
from .resolvers import resolve_subproject_params


@dataclass(frozen=True)
class SplitSpec:
    """A parsed ``--split`` value."""

    even: bool
    percentages: Tuple[Tuple[str, int], ...] = ()


def parse_split(value: Optional[str]) -> Optional[SplitSpec]:
    """Parse ``even`` or comma-separated ``name=integer-percent`` pairs."""
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        raise ValueError("Split cannot be empty.")
    if raw.casefold() == "even":
        return SplitSpec(even=True)

    percentages: List[Tuple[str, int]] = []
    seen = set()
    for item in raw.split(","):
        if "=" not in item:
            raise ValueError(
                "Use name=percent pairs separated by commas, or 'even'."
            )
        name_raw, percent_raw = item.split("=", 1)
        name = name_raw.strip()
        percent_text = percent_raw.strip()
        if not name or not percent_text:
            raise ValueError("Each split item must include a name and percent.")
        try:
            percent = int(percent_text)
        except ValueError:
            raise ValueError("Split percents must be integers from 1 to 100.") from None
        if percent < 1 or percent > 100:
            raise ValueError("Split percents must be integers from 1 to 100.")
        key = name.casefold()
        if key in seen:
            raise ValueError(f"Subproject '{name}' appears more than once in --split.")
        seen.add(key)
        percentages.append((name, percent))

    if sum(percent for _name, percent in percentages) > 100:
        raise ValueError("Split percents cannot total more than 100.")
    return SplitSpec(even=False, percentages=tuple(percentages))


def even_basis_points(names: Iterable[str]) -> List[Tuple[str, int]]:
    """Return a deterministic full 10,000bp even split for the given names."""
    items = list(names)
    if not items:
        return []
    base, remainder = divmod(10000, len(items))
    return [
        (name, base + (1 if index < remainder else 0))
        for index, name in enumerate(items)
    ]


def percentages_to_basis_points(
    percentages: Iterable[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    return [(name, percent * 100) for name, percent in percentages]


def resolve_split_selection(
    client: Any,
    project: str,
    subprojects: Iterable[str],
    split: Optional[SplitSpec],
    *,
    even_fallback: Optional[Iterable[str]] = None,
) -> Tuple[Optional[List[str]], Optional[List[Tuple[int, int]]], List[str]]:
    """Resolve command subprojects and an optional split to names and ID/bp pairs."""
    supplied = list(subprojects)
    if split is not None and split.even and not supplied:
        supplied = list(even_fallback or [])
        if not supplied:
            raise ValueError("--split even requires subprojects to split.")

    split_names = (
        [name for name, _percent in split.percentages]
        if split is not None and not split.even
        else []
    )
    names_to_resolve = supplied or split_names
    if not names_to_resolve:
        return None, None, []

    try:
        response = client.list_subprojects(project)
        known = (
            response.get("subprojects", [])
            if isinstance(response, dict)
            else response
        )
    except APIError:
        known = []

    resolved_supplied, supplied_warnings = resolve_subproject_params(
        subprojects=supplied,
        known_subprojects=known,
        project=project,
    )

    if split is None or split.even:
        return resolved_supplied or None, None, supplied_warnings

    resolved_split, split_warnings = resolve_subproject_params(
        subprojects=split_names,
        known_subprojects=known,
        project=project,
    )
    if supplied:
        supplied_keys = {name.casefold() for name in resolved_supplied}
        split_keys = {name.casefold() for name in resolved_split}
        if supplied_keys != split_keys:
            raise ValueError(
                "--subprojects and --split must name the same subprojects."
            )

    named_bp = [
        (resolved_name, percent * 100)
        for resolved_name, (_raw_name, percent) in zip(
            resolved_split, split.percentages
        )
    ]
    resolved_allocations = client.resolve_subproject_allocations(project, named_bp)
    return (
        resolved_supplied or resolved_split or None,
        resolved_allocations,
        supplied_warnings + split_warnings,
    )
