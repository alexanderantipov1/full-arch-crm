"""ENG-330: local-dev-only "Sync data now" surface.

A single button in the staff Inspector (`/dev/inspector`) drains the
CareStack + Salesforce provider pulls until the local DB has caught up to
provider state (see ``apps.worker.jobs.sync_local_job.run_local_sync`` and
the ENG-324 watermark). The drain runs as a background task INSIDE THE API
PROCESS — no worker is required — which is exactly why the surface must be
invisible outside local dev.

Every route is gated: when ``settings.is_production`` is true the router
raises ``NotFoundError`` (HTTP 404 via the platform error envelope) so the
endpoint does not exist in production. The route bodies stay thin — all
orchestration lives in ``run_local_sync``; this module only tracks the
single in-flight task and its last summary.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.worker.jobs.sync_local_job import run_local_sync
from packages.core.config import get_settings
from packages.core.exceptions import NotFoundError
from packages.core.logging import get_logger

log = get_logger("api.dev")

router = APIRouter(prefix="/dev", tags=["dev"])


def _guard_local() -> None:
    """Raise 404 (NotFoundError) when running in production.

    The drain reaches into provider credentials and runs unbounded
    background work; it is a local-dev affordance only. Raising
    ``NotFoundError`` (not ``AuthorizationError``) keeps the surface
    invisible — production behaves as if the route does not exist.
    """
    if get_settings().is_production:
        raise NotFoundError("Not Found")


class _DrainState:
    """Module-level holder for the single in-flight drain.

    The running task is kept here so it is not garbage-collected while
    detached, and so a concurrent POST can be short-circuited to
    ``already_running`` instead of launching a second overlapping drain.
    """

    task: asyncio.Task[dict[str, Any]] | None = None
    last_summary: dict[str, Any] | None = None
    last_finished_at: str | None = None


_state = _DrainState()


class SyncLocalIn(BaseModel):
    """Optional body for ``POST /dev/sync-local`` (ENG-351).

    Both fields optional so an empty body (the ENG-330 fast path) still
    works. ``deep`` selects the historical hole-filling backfill; ``since``
    is the ISO date ``YYYY-MM-DD`` lookback anchor (default in
    ``run_local_sync``: today - 30 days).
    """

    deep: bool = False
    since: str | None = None


def _is_running() -> bool:
    return _state.task is not None and not _state.task.done()


def _on_done(task: asyncio.Task[dict[str, Any]]) -> None:
    """Store the summary (or error) and clear the running flag."""
    _state.last_finished_at = datetime.now(UTC).isoformat()
    try:
        _state.last_summary = task.result()
    except asyncio.CancelledError:  # pragma: no cover - defensive
        _state.last_summary = {"error": "cancelled"}
    except Exception as exc:  # noqa: BLE001 - background task must not crash the loop
        log.error("dev.sync_local.failed", error=str(exc))
        _state.last_summary = {"error": str(exc)}
    finally:
        _state.task = None


@router.post("/sync-local")
async def start_sync_local(body: SyncLocalIn | None = None) -> JSONResponse:
    """Launch the local drain as a tracked background task.

    Accepts an OPTIONAL body ``{"deep": bool, "since": "YYYY-MM-DD"}``
    (ENG-351). An empty body (or no body) runs the ENG-330 fast watermark
    drain; ``deep=true`` runs the historical hole-filling backfill.

    Returns ``already_running`` (HTTP 200) if a drain is in flight,
    otherwise ``started`` (HTTP 202). The task opens its own DB sessions
    via ``run_local_sync`` — the request session is never threaded in.
    """
    _guard_local()
    if _is_running():
        return JSONResponse(
            {"status": "already_running"}, status_code=status.HTTP_200_OK
        )
    deep = body.deep if body is not None else False
    since = body.since if body is not None else None
    task = asyncio.ensure_future(run_local_sync(deep=deep, since=since))
    task.add_done_callback(_on_done)
    _state.task = task
    log.info("dev.sync_local.started", deep=deep, since=since)
    return JSONResponse({"status": "started"}, status_code=status.HTTP_202_ACCEPTED)


@router.get("/sync-local")
async def get_sync_local() -> dict[str, Any]:
    """Reflect drain state so the button can poll for progress/result."""
    _guard_local()
    return {
        "running": _is_running(),
        "last_summary": _state.last_summary,
        "last_finished_at": _state.last_finished_at,
    }
