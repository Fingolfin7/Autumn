"""A tiny cross-platform in-process scheduler.

This is intentionally simple and dependency-free. It's meant for:
- one-shot reminders (sleep + callback)
- periodic reminders (loop + interval)

We *don't* daemonize or persist tasks across reboots. For that, we'd integrate
with OS schedulers (launchd/Task Scheduler/cron) later.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ScheduledTask:
    name: str
    thread: threading.Thread
    cancel: Callable[[], None]


def schedule_in(*, seconds: int, fn: Callable[[], None], name: str = "reminder") -> ScheduledTask:
    if seconds < 0:
        raise ValueError("seconds must be >= 0")

    stop_evt = threading.Event()

    def runner() -> None:
        if not stop_evt.wait(timeout=seconds):
            fn()

    t = threading.Thread(target=runner, name=f"autumn:{name}", daemon=True)
    t.start()

    return ScheduledTask(name=name, thread=t, cancel=stop_evt.set)


def schedule_every(
    *,
    every_seconds: int,
    fn: Callable[[], None],
    name: str = "reminder",
    start_in_seconds: Optional[int] = None,
) -> ScheduledTask:
    if every_seconds <= 0:
        raise ValueError("every_seconds must be > 0")

    stop_evt = threading.Event()

    def runner() -> None:
        # Optional initial delay
        if start_in_seconds is not None:
            if stop_evt.wait(timeout=max(0, int(start_in_seconds))):
                return
        while True:
            fn()
            if stop_evt.wait(timeout=every_seconds):
                return

    t = threading.Thread(target=runner, name=f"autumn:{name}", daemon=True)
    t.start()

    return ScheduledTask(name=name, thread=t, cancel=stop_evt.set)


def sleep_seconds(seconds: int) -> None:
    """Abstraction for testing/mocking."""
    time.sleep(seconds)

