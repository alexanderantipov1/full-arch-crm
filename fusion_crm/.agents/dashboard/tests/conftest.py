"""Load `.agents/dashboard/server.py` as a module for the tests under
`.agents/dashboard/tests/`. The dashboard ships as a single-file script
without a package init, so we load it by path."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
SERVER_PATH = DASHBOARD_DIR / "server.py"

_spec = importlib.util.spec_from_file_location("dashboard_server", SERVER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load dashboard server module from {SERVER_PATH}")
_module = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("dashboard_server", _module)
_spec.loader.exec_module(_module)


@pytest.fixture
def server():
    return _module
