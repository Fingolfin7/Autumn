"""Deterministic garden state derived from an Autumn format-2 export.

The model deliberately uses completed session timestamps instead of exported
summary totals.  Open, invalid, duplicate, and non-positive sessions never grow
a plant.  Inactivity also never reduces growth.

Historical snapshots include activity through the requested local calendar
day.  A session crossing the following midnight is clipped at that boundary,
and its note is withheld because the note was not yet known at the cutoff.
Project status is current export metadata, so ``completed`` is always false in
historical snapshots rather than pretending that current state is historical.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any, Mapping


SPECIES = ("oak", "pine", "birch", "willow", "flowers", "fern")

_ANSI_RE = re.compile(
    r"\x1b(?:\][^\x07]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-_])"
)


@dataclass(frozen=True, slots=True)
class Plant:
    """One project represented as a deterministic garden plant."""

    key: str
    name: str
    status: str
    species: str
    seed: int
    stage: int
    session_count: int
    total_seconds: float
    first_session: datetime | None
    last_session: datetime | None
    latest_note: str | None
    visit_days: int
    completed: bool


@dataclass(frozen=True, slots=True)
class GardenSnapshot:
    """Garden state for one local day."""

    plants: list[Plant]
    day: date
    historical: bool
    skipped_sessions: int


def sanitize_text(value: object, *, multiline: bool = False) -> str:
    """Remove terminal escapes and unsafe controls from display text.

    Names use the default single-line form.  Notes may request ``multiline`` to
    preserve line feeds while still removing other control characters.
    """

    text_value = "" if value is None else str(value)
    text_value = _ANSI_RE.sub("", text_value).replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    for character in text_value:
        if character == "\n" and multiline:
            cleaned.append(character)
        elif character.isspace() or unicodedata.category(character).startswith("C"):
            cleaned.append(" ")
        else:
            cleaned.append(character)

    if not multiline:
        return " ".join("".join(cleaned).split()).strip()

    lines = [" ".join(line.split()).strip() for line in "".join(cleaned).split("\n")]
    return "\n".join(lines).strip()


def seed_for_key(key: str) -> int:
    """Return a stable unsigned 64-bit seed for a plant key."""

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def species_for_key(key: str) -> str:
    """Choose a stable species without relying on process-randomized hash()."""

    return SPECIES[seed_for_key(key) % len(SPECIES)]


def stage_for_seconds(total_seconds: float) -> int:
    """Map recorded time to the five diminishing-return growth stages."""

    if total_seconds <= 0:
        return 0
    hours = total_seconds / 3600.0
    if hours < 2:
        return 1
    if hours < 10:
        return 2
    if hours < 40:
        return 3
    return 4


def build_garden(
    data: Mapping[str, Any],
    *,
    at: date | None = None,
    now: datetime | None = None,
    identities: dict[str, int] | None = None,
) -> GardenSnapshot:
    """Build a garden snapshot from an Autumn format-2 export.

    ``at`` is an inclusive local calendar date.  With no ``at``, the snapshot
    uses ``now`` (or the system clock) as an exact cutoff: future sessions are
    excluded and a saved session crossing that instant is clipped without
    revealing its note.  ``identities`` may map current project names to stable
    API IDs so visual identity survives a rename.

    Malformed individual sessions are counted in ``skipped_sessions``.  A
    malformed export envelope or project record raises a clear ``ValueError``.
    """

    if not isinstance(data, Mapping):
        raise ValueError("Garden data must be a mapping")
    if data.get("format") != 2:
        raise ValueError("Unsupported Autumn export format; expected format 2")
    projects = data.get("projects")
    if not isinstance(projects, list):
        raise ValueError("Autumn format-2 export must contain a projects list")
    if at is not None and (not isinstance(at, date) or isinstance(at, datetime)):
        raise ValueError("Garden snapshot date must be a date")
    if now is not None and not isinstance(now, datetime):
        raise ValueError("Garden current time must be a datetime")

    reference_now = now or datetime.now().astimezone()
    # When no clock is injected, leave the zone implicit.  Calling astimezone()
    # on each naive local boundary asks the operating system for the offset on
    # that particular date instead of freezing today's UTC offset across DST.
    local_zone = now.tzinfo if now is not None and now.tzinfo is not None else None
    reference_local = _as_local(reference_now, local_zone)
    snapshot_day = at or reference_local.date()
    historical = at is not None
    cutoff_utc = (
        _local_midnight(snapshot_day + timedelta(days=1), local_zone)
        if historical
        else reference_local
    ).astimezone(timezone.utc)
    # An explicit --at today still cannot include activity from later today.
    cutoff_utc = min(cutoff_utc, reference_local.astimezone(timezone.utc))

    identity_map = identities or {}
    plants: list[Plant] = []
    skipped_sessions = 0

    for project_index, project in enumerate(projects):
        if not isinstance(project, Mapping):
            raise ValueError(f"projects[{project_index}] must be a mapping")

        raw_name = project.get("name")
        if not isinstance(raw_name, str):
            raise ValueError(f"projects[{project_index}].name must be a string")
        name = sanitize_text(raw_name)
        if not name:
            raise ValueError(f"projects[{project_index}].name must not be empty")

        raw_sessions = project.get("sessions", [])
        if not isinstance(raw_sessions, list):
            raise ValueError(f"projects[{project_index}].sessions must be a list")

        valid_sessions: list[_Session] = []
        seen_uuids: set[str] = set()
        for raw_session in raw_sessions:
            parsed = _parse_session(raw_session, local_zone)
            if parsed is None:
                skipped_sessions += 1
                continue
            if parsed.uuid in seen_uuids:
                skipped_sessions += 1
                continue
            seen_uuids.add(parsed.uuid)
            valid_sessions.append(parsed)

        project_start = _parse_project_start(project.get("start_date"), local_zone)
        earliest_session_day = min(
            (session.start_local.date() for session in valid_sessions), default=None
        )
        existence_day = _earliest_date(project_start, earliest_session_day)

        if existence_day is not None and existence_day > snapshot_day:
            continue
        if historical and existence_day is None:
            # A current seed with no date or activity cannot be placed in history.
            continue

        included: list[_IncludedSession] = []
        for session in valid_sessions:
            if session.start_utc >= cutoff_utc:
                continue
            effective_end_utc = min(session.end_utc, cutoff_utc)

            seconds = (effective_end_utc - session.start_utc).total_seconds()
            if seconds <= 0:
                continue
            included.append(
                _IncludedSession(
                    source=session,
                    end_utc=effective_end_utc,
                    end_local=_as_local(effective_end_utc, local_zone),
                    seconds=seconds,
                    note_known=session.end_utc <= cutoff_utc,
                )
            )

        identity = identity_map.get(raw_name)
        if identity is None and name != raw_name:
            identity = identity_map.get(name)
        key = str(identity) if isinstance(identity, int) and not isinstance(identity, bool) else name
        seed = seed_for_key(key)
        status = sanitize_text(project.get("status") or "")
        total_seconds = sum(session.seconds for session in included)
        first_session = min(
            (session.source.start_local for session in included), default=None
        )
        last_session = max((session.end_local for session in included), default=None)
        note_sessions = [
            session
            for session in included
            if session.note_known and session.source.note is not None
        ]
        latest_note = None
        if note_sessions:
            note_session = max(
                note_sessions,
                key=lambda session: (session.source.end_utc, session.source.uuid),
            )
            latest_note = sanitize_text(note_session.source.note, multiline=True) or None

        plants.append(
            Plant(
                key=key,
                name=name,
                status=status,
                species=SPECIES[seed % len(SPECIES)],
                seed=seed,
                stage=stage_for_seconds(total_seconds),
                session_count=len(included),
                total_seconds=total_seconds,
                first_session=first_session,
                last_session=last_session,
                latest_note=latest_note,
                visit_days=len(
                    {session.source.start_local.date() for session in included}
                ),
                completed=(not historical and status.casefold() in {"complete", "completed"}),
            )
        )

    plants.sort(key=_plant_sort_key)
    return GardenSnapshot(
        plants=plants,
        day=snapshot_day,
        historical=historical,
        skipped_sessions=skipped_sessions,
    )


@dataclass(frozen=True, slots=True)
class _Session:
    uuid: str
    start_utc: datetime
    end_utc: datetime
    start_local: datetime
    note: object | None


@dataclass(frozen=True, slots=True)
class _IncludedSession:
    source: _Session
    end_utc: datetime
    end_local: datetime
    seconds: float
    note_known: bool


def _parse_session(raw: object, local_zone: tzinfo | None) -> _Session | None:
    if not isinstance(raw, Mapping):
        return None
    uuid = raw.get("uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        return None
    try:
        start = _parse_datetime(raw.get("start"), local_zone)
        end = _parse_datetime(raw.get("end"), local_zone)
    except (TypeError, ValueError, OverflowError):
        return None
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    if end_utc <= start_utc:
        return None
    return _Session(
        uuid=uuid.strip(),
        start_utc=start_utc,
        end_utc=end_utc,
        start_local=_as_local(start_utc, local_zone),
        note=raw.get("note"),
    )


def _parse_datetime(value: object, local_zone: tzinfo | None) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("session timestamp must be a non-empty ISO string")
    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return _localize_naive(parsed, local_zone)
    return parsed


def _parse_project_start(value: object, local_zone: tzinfo | None) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        pass
    try:
        return _as_local(_parse_datetime(candidate, local_zone), local_zone).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _localize_naive(value: datetime, local_zone: tzinfo | None) -> datetime:
    if local_zone is not None:
        return value.replace(tzinfo=local_zone)
    # astimezone() interprets a naive datetime in the system local zone at that
    # date, preserving the correct historical DST offset.
    return value.astimezone()


def _as_local(value: datetime, local_zone: tzinfo | None) -> datetime:
    if value.tzinfo is None:
        return _localize_naive(value, local_zone)
    return value.astimezone(local_zone) if local_zone is not None else value.astimezone()


def _local_midnight(day: date, local_zone: tzinfo | None) -> datetime:
    naive = datetime.combine(day, time.min)
    return _localize_naive(naive, local_zone)


def _earliest_date(first: date | None, second: date | None) -> date | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def _plant_sort_key(plant: Plant) -> tuple[bool, float, str, str]:
    latest = plant.last_session.timestamp() if plant.last_session is not None else 0.0
    return (
        plant.last_session is None,
        -latest,
        plant.name.casefold(),
        plant.key,
    )
