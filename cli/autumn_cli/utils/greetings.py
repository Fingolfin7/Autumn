"""Greeting helpers for the CLI root command.

Keep this dependency-free. We vary greeting by:
- time of day (morning/afternoon/evening/night)
- month/season-ish + a couple light holiday callouts
- moon phase
- recent activity (contextual)

This is intentionally small and safe: no web calls, no heavy libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import random
import time


@dataclass(frozen=True)
class Greeting:
    line: str  # Complete greeting line with username placeholder


def _time_bucket(now: datetime) -> str:
    h = now.hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


def _season_hint(now: datetime) -> Optional[str]:
    # Northern-hemisphere-ish (fits the Autumn vibe); harmless if you're elsewhere.
    m = now.month
    if m in (12, 1, 2):
        return "Stay warm out there."
    if m in (3, 4, 5):
        return "Hope spring's treating you well."
    if m in (6, 7, 8):
        return "Hydrate and take breaks."
    if m in (9, 10, 11):
        return "Autumn vibes."
    return None


def _holiday_hint(now: datetime) -> Optional[str]:
    m, d = now.month, now.day

    # A few lightweight, non-region-specific-ish callouts.
    if m == 1 and d == 1:
        return "Happy New Year!"
    if m == 10 and d == 31:
        return "Happy Halloween!"
    if m == 12 and d in (24, 25):
        return "Merry Christmas!"

    return None


def _moon_phase_name(now: datetime) -> str:
    """Approximate moon phase name.

    Uses a simple synodic month approximation (~29.53058867 days).
    Good enough for a fun greeting line.
    """
    # Known new moon reference: 2000-01-06 18:14 UTC
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    days = (now.astimezone(timezone.utc) - ref).total_seconds() / 86400.0
    synodic = 29.53058867
    age = days % synodic

    # 8-phase buckets
    phase_index = int((age / synodic) * 8 + 0.5) % 8
    phases = [
        "New Moon",
        "Waxing Crescent",
        "First Quarter",
        "Waxing Gibbous",
        "Full Moon",
        "Waning Gibbous",
        "Last Quarter",
        "Waning Crescent",
    ]
    return phases[phase_index]


def _build_activity_suffix(activity: Dict[str, Any], now: datetime) -> Optional[str]:
    """Build a contextual suffix to append to the greeting phrase.

    This is intentionally *optional* and should not dominate the greeting.
    The caller decides how heavily to weight activity vs non-activity lines.
    """
    today_proj = activity.get("today_project")
    last_proj = activity.get("last_project")
    longest_proj = activity.get("longest_project")
    longest_min = activity.get("longest_minutes")
    most_frequent = activity.get("most_frequent_project")
    streak = activity.get("streak_days", 0)

    # Prefer today's activity
    current_proj = today_proj or last_proj

    # Per-call RNG (do NOT call random.seed(), it makes output deterministic)
    # Mix in time_ns so each run varies, and add a few stable inputs so it still
    # feels "about" your data.
    stable = "|".join(
        str(x)
        for x in (
            today_proj,
            last_proj,
            longest_proj,
            most_frequent,
            streak,
            _moon_phase_name(now),
            _holiday_hint(now) or "",
            _season_hint(now) or "",
            now.hour,
        )
    )
    rng = random.Random(hash((stable, time.time_ns())))

    # Build a pool of possible suffixes (we'll pick from these)
    possible_suffixes = []

    # --- Project-based suffixes ---
    if current_proj:
        if today_proj:
            possible_suffixes.extend([
                f"Still chipping away at [autumn.project]{current_proj}[/]?",
                f"Back to [autumn.project]{current_proj}[/].",
                f"[autumn.project]{current_proj}[/] keeping you busy?",
            ])
        else:
            possible_suffixes.extend([
                f"Last worked on [autumn.project]{current_proj}[/].",
                f"[autumn.project]{current_proj}[/] was your focus.",
            ])

    # --- Longest session suffixes (if significant) ---
    if longest_proj and longest_min and float(longest_min) >= 90:
        hours = float(longest_min) / 60.0
        possible_suffixes.extend([
            f"You spent [autumn.time]{hours:.1f}h[/] on [autumn.project]{longest_proj}[/]. Deep work!",
            f"That [autumn.time]{hours:.1f}h[/] on [autumn.project]{longest_proj}[/] was impressive.",
        ])

    # --- Streak suffixes ---
    if streak >= 3:
        possible_suffixes.extend([
            f"[autumn.time]{streak} days[/] in a row!",
            f"[autumn.time]{streak}-day streak[/]. Keep it up!",
        ])
    elif streak == 2:
        possible_suffixes.append(f"Two days in a row. Building a habit?")

    # --- Moon phase suffixes ---
    moon = _moon_phase_name(now)
    if moon in ("Full Moon", "New Moon"):
        possible_suffixes.append(f"Enjoying the {moon}?")

    # --- Season/holiday suffixes ---
    holiday = _holiday_hint(now)
    season = _season_hint(now)
    if holiday:
        possible_suffixes.append(holiday)
    if season:
        possible_suffixes.append(season)

    # Pick one suffix from the pool
    if possible_suffixes:
        return rng.choice(possible_suffixes)

    return None


def _build_non_activity_suffix(
    now: datetime,
    *,
    rng: random.Random,
    moon_cameo_weight: float = 0.15,
) -> Optional[str]:
    """Build a fun non-activity suffix (moon/season/holiday/time vibe)."""
    bucket = _time_bucket(now)
    moon = _moon_phase_name(now)
    holiday = _holiday_hint(now)
    season = _season_hint(now)

    pool: list[str] = []

    # Holiday + season get priority if present
    if holiday:
        pool.extend([
            holiday,
            f"{holiday} Let's make it a good one.",
        ])
    if season:
        pool.extend([
            season,
            f"{season} Take it slow and steady.",
        ])

    # Moon mentions
    if moon in ("Full Moon", "New Moon"):
        pool.extend([
            f"Enjoying the {moon}?",
            f"{moon} night energy.",
        ])
    else:
        # occasional non-extreme moon phases
        if rng.random() < float(moon_cameo_weight):
            pool.extend([
                f"{moon} overhead.",
                f"{moon} kind of day.",
            ])

    # Time-of-day vibe fillers
    if bucket == "morning":
        pool.extend([
            "Let's make today count.",
            "Coffee-powered?",
            "Fresh start.",
            "Warm drink, warm brain.",
            "Light the candle and ship something.",
            "Tiny steps, big momentum.",
            "Good day to write clean code.",
            "Start small. Finish strong.",
        ])
    elif bucket == "afternoon":
        pool.extend([
            "Keep rolling.",
            "Steady progress.",
            "Midday momentum.",
            "Halfway through — stay sharp.",
            "A quick win would be nice.",
            "One good session can change the whole day.",
            "Hydrate. Stretch. Then crush it.",
        ])
    elif bucket == "evening":
        pool.extend([
            "Nice work today.",
            "One more good session?",
            "A calm finish beats a frantic sprint.",
            "Wrap up something satisfying.",
            "Evening focus hits different.",
            "Last push, then rest.",
            "Ship it, then chill.",
        ])
    else:
        pool.extend([
            "Quiet hours. Focus time.",
            "Midnight momentum.",
            "Low noise, high signal.",
            "The best ideas show up late.",
            "Just you and the keyboard.",
            "Tiny commit energy.",
            "Soft music, sharp thinking.",
        ])

    # General autumn-y / cozy / productive lines
    pool.extend([
        "Make something satisfying.",
        "Slow and steady.",
        "One session at a time.",
        "Be kind to future-you.",
        "Leave it cleaner than you found it.",
        "A little progress is still progress.",
        "Today counts.",
        "Small wins stack.",
        "Less doomscroll, more deep work.",
        "Your future self will thank you.",
        "Trust the process.",
    ])

    return rng.choice(pool) if pool else None


def build_greeting(
    now: datetime,
    activity: Optional[Dict[str, Any]] = None,
    *,
    activity_weight: float = 0.35,
    moon_cameo_weight: float = 0.15,
) -> Greeting:
    bucket = _time_bucket(now)

    # Per-call RNG for base greeting rotation
    rng = random.Random(time.time_ns() ^ (now.hour << 16) ^ now.minute)

    if bucket == "morning":
        base_choices = ["Good morning", "Morning", "Hey", "Rise and shine"]
    elif bucket == "afternoon":
        base_choices = ["Good afternoon", "Afternoon", "Hey", "Howdy"]
    elif bucket == "evening":
        base_choices = ["Good evening", "Evening", "Hey", "Nice work today"]
    else:
        base_choices = ["Hey", "Up late", "Still going", "Night shift mode"]

    base = rng.choice(base_choices)

    # Choose a suffix. We *don't* want activity to dominate.
    suffix: Optional[str] = None
    if activity and rng.random() < float(activity_weight):
        suffix = _build_activity_suffix(activity, now)

    if not suffix:
        suffix = _build_non_activity_suffix(now, rng=rng, moon_cameo_weight=moon_cameo_weight)

    if suffix:
        line = f"{base} {{username}}! {suffix}"
    else:
        line = f"{base} {{username}}!"

    return Greeting(line=line)
