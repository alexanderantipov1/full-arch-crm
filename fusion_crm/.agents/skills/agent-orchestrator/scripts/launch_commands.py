#!/usr/bin/env python3
"""Print launch commands for a worker or wave without starting agents."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LAUNCHER = SCRIPT_DIR / "launch_worker.py"


def main() -> None:
    args = [sys.executable, str(LAUNCHER), *sys.argv[1:]]
    if "--mode" not in sys.argv:
        args.extend(["--mode", "print"])
    # Intentional local wrapper around the sibling launch_worker.py script.
    subprocess.run(args, check=True)  # noqa: S603


if __name__ == "__main__":
    main()
