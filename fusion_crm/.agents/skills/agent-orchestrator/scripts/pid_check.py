"""Cross-platform process liveness check.

`runtime_status(pid)` reports `"alive"` | `"exited"` | `"missing"`
using `os.kill(pid, 0)` semantics. Pure stdlib; macOS + Linux.
"""

from __future__ import annotations

import os
from typing import Literal

RuntimeStatus = Literal["alive", "exited", "missing"]


def runtime_status(pid: int | None) -> RuntimeStatus:
    """Return whether the process for `pid` is alive on this host.

    - None / non-int / <= 0 → `"missing"`.
    - `os.kill(pid, 0)` raises `ProcessLookupError` → `"exited"`.
    - `PermissionError` from the same call → `"alive"` (process exists,
      we just cannot signal it; this happens for root-owned PIDs).
    - Otherwise → `"alive"`.
    """
    if not isinstance(pid, int) or pid <= 0:
        return "missing"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "exited"
    except PermissionError:
        return "alive"
    except OSError:
        return "missing"
    return "alive"
