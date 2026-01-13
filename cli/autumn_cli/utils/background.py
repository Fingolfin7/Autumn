"""Cross-platform process spawning helpers.

We need a way to spawn a detached background worker from the CLI.

Approach:
- Use the current Python interpreter (sys.executable)
- On Unix: start_new_session=True
- On Windows: CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS

The worker is another Python module in this package.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence


def spawn_detached_python_module(module: str, args: Sequence[str]) -> subprocess.Popen:
    cmd = [sys.executable, "-m", module, *list(args)]

    # Redirect to /dev/null on POSIX and NUL on Windows.
    devnull = subprocess.DEVNULL

    kwargs = {
        "stdin": devnull,
        "stdout": devnull,
        "stderr": devnull,
        # Don't use close_fds on Windows with creationflags; on POSIX it's fine.
        "close_fds": os.name != "nt",
    }

    if os.name == "nt":
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(cmd, **kwargs)  # noqa: S603,S607 (no shell)
