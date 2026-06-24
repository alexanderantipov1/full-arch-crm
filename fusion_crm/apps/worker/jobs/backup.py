"""Backup job — invokes ``infra/scripts/backup.sh`` from a worker.

The shell script does the actual work (pg_dump → gzip → GCS upload). We invoke
it from a worker so backups can be triggered on a cron *or* on-demand from the
API without blocking the request.
"""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

from packages.core.logging import get_logger

log = get_logger("worker.backup")

_SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "scripts" / "backup.sh"


async def run_backup(_ctx: dict) -> dict:
    """Execute the backup script and return its exit status + tail of output."""
    if not _SCRIPT.exists():
        raise FileNotFoundError(f"backup script missing: {_SCRIPT}")

    log.info("backup.start", script=str(_SCRIPT))
    proc = await asyncio.create_subprocess_exec(
        "bash",
        str(_SCRIPT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    text = (stdout or b"").decode(errors="replace")
    tail = "\n".join(text.splitlines()[-20:])

    if proc.returncode != 0:
        log.error("backup.failed", returncode=proc.returncode, tail=tail)
        raise RuntimeError(f"backup failed (exit={proc.returncode}): {shlex.quote(tail)}")

    log.info("backup.ok")
    return {"returncode": proc.returncode, "tail": tail}
