"""Update the note of an active timer without stopping it."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

import click
from rich.markup import escape as rich_escape

from ..api_client import APIClient, APIError
from ..utils.console import console


def _newest_session(sessions: Iterable[Dict]) -> Dict:
    items = list(sessions)
    if not items:
        raise APIError("No active timer found.")
    return max(
        items,
        key=lambda session: (
            str(session.get("start") or ""),
            int(session.get("id") or 0),
        ),
    )


def _get_target(
    client: APIClient,
    session_id: Optional[int],
    project: Optional[str],
) -> Dict:
    result = client.get_timer_status(session_id=session_id, project=project)
    return _newest_session(result.get("sessions") or [])


def _compose_note(
    old_note: str,
    text: str,
    *,
    replace: bool,
    stamp: bool,
    hhmm: str,
) -> Tuple[str, str]:
    fragment = f"— {hhmm} — {text}" if stamp else text
    if replace or not old_note:
        return fragment, fragment
    return f"{old_note}\n\n{fragment}", fragment


@click.command("note")
@click.argument("text", nargs=-1, required=True)
@click.option("--project", "-p", help="Update that project's newest active timer")
@click.option("--session-id", "-s", type=int, help="Update a specific active timer")
@click.option("--replace", is_flag=True, help="Replace the note instead of appending")
@click.option(
    "--stamp/--no-stamp",
    default=None,
    help="Include or omit the local HH:MM timestamp prefix",
)
def note(
    text: Tuple[str, ...],
    project: Optional[str],
    session_id: Optional[int],
    replace: bool,
    stamp: Optional[bool],
):
    """Append TEXT to the newest active timer's note."""
    joined_text = " ".join(text).strip()
    if not joined_text:
        raise click.BadParameter("Note text cannot be empty.", param_hint="TEXT")

    use_stamp = (not replace) if stamp is None else stamp
    try:
        client = APIClient()
        target = _get_target(client, session_id, project)
        target_id = int(target["id"])
        fragment = joined_text

        for attempt in range(2):
            version = target.get("version")
            if version is None:
                raise APIError("The active timer response did not include a version.")
            new_note, fragment = _compose_note(
                str(target.get("note") or ""),
                joined_text,
                replace=replace,
                stamp=use_stamp,
                hhmm=datetime.now().astimezone().strftime("%H:%M"),
            )
            try:
                result = client.update_timer_note(target_id, new_note, int(version))
                updated = result.get("session") or {}
                break
            except APIError as error:
                if error.code != "version_conflict" or attempt == 1:
                    raise
                target = _get_target(client, target_id, None)

        project_name = (
            updated.get("p")
            or updated.get("project")
            or target.get("p")
            or target.get("project")
            or project
            or ""
        )
        console.print(
            f"[autumn.ok]Note updated[/] for [autumn.project]{rich_escape(str(project_name))}[/]."
        )
        console.print(f"[autumn.note]{rich_escape(fragment)}[/]")
    except APIError as error:
        console.print(f"[autumn.err]Error:[/] {error}")
        raise click.Abort()
