"""Heuristic activity classifier for worker log files.

`activity_state(log_path, idle_threshold_seconds=60)` returns one of:

- `"waiting_input"` — recent tail contains `Needs decision:` marker
- `"blocked"`       — recent tail contains `Blocked:` marker
- `"active"`        — log mtime is within the idle threshold
- `"idle"`          — log is older than the threshold OR missing

Marker-based checks WIN over mtime: a stale-by-hours log whose tail
includes `Needs decision:` reports `"waiting_input"`, not `"idle"`.

Disclaimer: this is a heuristic, not a contract. Surfaces that render
the result must label it as a heuristic so readers do not treat it as
authoritative.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

ActivityState = Literal["active", "idle", "waiting_input", "blocked"]

NEEDS_DECISION_MARKER = "needs decision:"
BLOCKED_MARKER = "blocked:"
TAIL_LINES_FOR_MARKERS = 50


def _read_tail(path: Path, n: int) -> list[str]:
    """Read the last `n` lines of `path`. Returns [] when file is missing."""
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            data = handle.read()
    except OSError:
        return []
    return data.splitlines()[-n:]


def activity_state(log_path: Path, idle_threshold_seconds: int = 60) -> ActivityState:
    if not log_path.is_file():
        return "idle"

    tail = _read_tail(log_path, TAIL_LINES_FOR_MARKERS)
    for line in tail:
        lowered = line.lower()
        if NEEDS_DECISION_MARKER in lowered:
            return "waiting_input"
        if BLOCKED_MARKER in lowered:
            return "blocked"

    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return "idle"

    age = time.time() - mtime
    if age <= idle_threshold_seconds:
        return "active"
    return "idle"
