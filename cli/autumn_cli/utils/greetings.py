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
from astral import moon
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
    phase = moon.phase(now)
    labels = [
        "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
        "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"
    ]
    index = int((phase / 29.53) * 8) % 8
    return labels[index]


def _build_activity_suffix(activity: Dict[str, Any], now: datetime) -> Optional[str]:
    """Build a contextual suffix to append to the greeting phrase.

    This is intentionally *optional* and should not dominate the greeting.
    The caller decides how heavily to weight activity vs non-activity lines.
    """
    today_proj = activity.get("today_project")
    last_proj = activity.get("last_project")
    last_session_min = activity.get("last_session_minutes")
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
                f"Another round with [autumn.project]{current_proj}[/]?",
                f"[autumn.project]{current_proj}[/] time. Let's go!",
                f"Ready to ship some [autumn.project]{current_proj}[/]?",
            ])
        else:
            possible_suffixes.extend([
                f"Last worked on [autumn.project]{current_proj}[/].",
                f"[autumn.project]{current_proj}[/] was your focus.",
                f"You were cooking on [autumn.project]{current_proj}[/].",
                f"[autumn.project]{current_proj}[/] had your attention last.",
            ])

    # --- Last session suffixes (if recent and significant) ---
    if last_proj and last_session_min and float(last_session_min) >= 15:
        hours = float(last_session_min) / 60.0
        if hours >= 6.0:
            possible_suffixes.extend([
                f"Peak session: [autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/]. Legendary!",
                f"That [autumn.duration]{hours:.1f}h[/] [autumn.project]{last_proj}[/] marathon was insane.",
                f"[autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/]? Absolute unit.",
                f"Your [autumn.duration]{hours:.1f}h[/] [autumn.project]{last_proj}[/] session lives rent-free in my head.",
            ])
        elif 3.0 <= hours < 6.0:
            possible_suffixes.extend([
                f"Last time: [autumn.duration]{hours:.1f}h[/] straight on [autumn.project]{last_proj}[/]. Beast mode!",
                f"[autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/] last session. You're cooking!",
                f"That [autumn.duration]{hours:.1f}h[/] [autumn.project]{last_proj}[/] session? Chef's kiss.",
                f"[autumn.duration]{hours:.1f}h[/] deep in [autumn.project]{last_proj}[/] last time. Respect.",
            ])
        elif 2.0 <= hours < 3.0:
            possible_suffixes.extend([
                f"Last session: [autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/]. Solid focus time!",
                f"[autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/]. That's the spirit!",
                f"Crushed [autumn.duration]{hours:.1f}h[/] on [autumn.project]{last_proj}[/] last time.",
                f"[autumn.project]{last_proj}[/] got [autumn.duration]{hours:.1f}h[/] of your energy last session.",
            ])
        else:
            if hours >= 1:
                min_or_hrs = f"{hours:.1f}h"
            else:
                min_or_hrs = f"{int(last_session_min)}m"

            possible_suffixes.extend([
                f"Last session: [autumn.duration]{min_or_hrs}[/] on [autumn.project]{last_proj}[/]. Nice warmup!",
                f"[autumn.duration]{min_or_hrs}[/] on [autumn.project]{last_proj}[/] last time. Building momentum!",
                f"Put in [autumn.duration]{min_or_hrs}[/] on [autumn.project]{last_proj}[/] recently.",
            ])

    # --- Streak suffixes ---
    if streak >= 7:
        possible_suffixes.extend([
            f"[autumn.time]{streak} days[/] straight! You're unstoppable!",
            f"[autumn.time]{streak}-day streak[/]! Absolutely killing it!",
            f"Week {streak // 7}+ complete. Legend status!",
            f"[autumn.time]{streak} days[/] and counting. This is the way.",
        ])
    elif streak >= 5:
        possible_suffixes.extend([
            f"[autumn.time]{streak} days[/] in a row! Keep the fire burning!",
            f"[autumn.time]{streak}-day streak[/]! Don't break the chain!",
            f"[autumn.time]{streak} consecutive days[/]. Momentum is real!",
        ])
    elif streak > 3:
        possible_suffixes.extend([
            f"[autumn.time]{streak} days[/] in a row!",
            f"[autumn.time]{streak}-day streak[/]. Keep it up!",
            f"[autumn.time]{streak} days[/] straight. You're on a roll!",
        ])
    elif streak == 3:
        possible_suffixes.extend([
            f"Three days strong. Habit forming!",
            f"Three days running. Nice!",
            f"Third day in a row. Momentum building!",
            f"Three-day streak! Keep it going!",
        ])
    elif streak == 2:
        possible_suffixes.extend([
            f"Two days in a row. Building a habit?",
            f"Back-to-back days. Consistency unlocked!",
            f"Day two! The hardest part is starting.",
        ])

    # --- Moon phase suffixes ---
    moon = _moon_phase_name(now)
    if "Full Moon" in moon or "New Moon" in moon:
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


def _build_moon_suffix(now: datetime, *, rng: random.Random, moon_cameo_weight: float) -> Optional[str]:
    """Build a moon-only suffix."""

    moon = _moon_phase_name(now)
    pool: list[str] = []

    if "Full Moon" in moon or "New Moon" in moon:
        pool.extend(
            [
                f"Enjoying the {moon}?",
                f"{moon} night energy.",
                f"{moon} vibes tonight.",
                f"Perfect {moon} for shipping code.",
                f"{moon} out there!",
                f"Coding under the {moon}.",
            ]
        )
    else:
        if float(moon_cameo_weight) >= 1.0 or rng.random() < float(moon_cameo_weight):
            pool.extend(
                [
                    f"{moon} overhead.",
                    f"{moon} kind of day.",
                    f"{moon} aesthetic.",
                    f"Nice {moon} tonight.",
                    f"{moon} energy.",
                    f"Building under the {moon}.",
                ]
            )

    return rng.choice(pool) if pool else None


def _build_non_activity_suffix(
    now: datetime,
    *,
    rng: random.Random,
    moon_cameo_weight: float = 0.15,
) -> Optional[str]:
    """Build a fun non-activity suffix (season/holiday/time vibe + optional moon)."""

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

    moon_suffix = _build_moon_suffix(now, rng=rng, moon_cameo_weight=moon_cameo_weight)
    if moon_suffix:
        pool.append(moon_suffix)

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
            "Morning energy is undefeated.",
            "Ready to cook?",
            "Time to build something cool.",
            "New day, new commits.",
            "The early bird ships features.",
            "Sunrise and code — name a better duo.",
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
            "Afternoon grind hits different.",
            "Post-lunch flow state incoming?",
            "Second wind energy.",
            "The zone is calling.",
            "Perfect time for a PR.",
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
            "Golden hour coding.",
            "Finish strong!",
            "End the day with a win.",
            "One more commit before bed?",
            "Prime deep-work hours.",
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
            "Night owl mode: activated.",
            "3am code hits different.",
            "The world's asleep. Time to build.",
            "Burning the midnight oil?",
            "Late-night genius hours.",
            "Dark mode and deep thoughts.",
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
        "You got this.",
        "Ship something today.",
        "Make it work, then make it better.",
        "Commit early, commit often.",
        "Progress over perfection.",
        "The code won't write itself.",
        "One line at a time.",
        "Debug mode: ON.",
        "Build in public, build with purpose.",
        "Flow state awaits.",
        "Every expert was once a beginner.",
        "Coffee in, code out.",
        "Refactor your way to glory.",
        "Make those tests green.",
        "Document as you go.",
        "Clean code, clear mind.",
        "Solve problems. Ship value.",
    ])

    return rng.choice(pool) if pool else None


def _weighted_choice(*, rng: random.Random, items: list[str], weights: list[float]) -> str:
    if len(items) != len(weights):
        raise ValueError("items and weights must have same length")

    total = sum(float(w) for w in weights)
    if total <= 0:
        raise ValueError("total weight must be > 0")

    r = rng.random() * total
    upto = 0.0
    for item, weight in zip(items, weights):
        w = float(weight)
        if w <= 0:
            continue
        upto += w
        if upto >= r:
            return item

    return items[-1]


def build_greeting(
    now: datetime,
    activity: Optional[Dict[str, Any]] = None,
    *,
    general_weight: float = 0.4,
    activity_weight: float = 0.4,
    moon_weight: float = 0.2,
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

    # Choose which pool we want, then choose inside it.
    pools: list[str] = []
    weights: list[float] = []

    # General pool (always available)
    pools.append("general")
    weights.append(float(general_weight))

    # Activity pool (only if we have activity to talk about)
    if activity:
        pools.append("activity")
        weights.append(float(activity_weight))

    # Moon pool (always available)
    pools.append("moon")
    weights.append(float(moon_weight))

    # If the configured weights don't sum to 1, leftover probability becomes general.
    missing = 1.0 - sum(weights)
    if missing > 0:
        weights[0] += missing

    choice = _weighted_choice(rng=rng, items=pools, weights=weights)

    suffix: Optional[str] = None
    if choice == "activity" and activity:
        suffix = _build_activity_suffix(activity, now)
    elif choice == "moon":
        suffix = _build_moon_suffix(now, rng=rng, moon_cameo_weight=moon_weight)
    else:
        suffix = _build_non_activity_suffix(now, rng=rng, moon_cameo_weight=0.0)


    if suffix:
        line = f"{base} {{username}}! {suffix}"
    else:
        line = f"{base} {{username}}!"

    return Greeting(line=line)
