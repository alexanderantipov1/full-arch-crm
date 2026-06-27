"""ENG-330: on-demand local-dev drain of provider pulls.

The scheduled CareStack / Salesforce pulls are page-bounded and the arq
cron only fires hourly (and never while the Mac is asleep), so a fresh
local checkout lags production by hours. ``run_local_sync`` repeatedly
runs the SAME per-tenant pull the worker uses and stops once a full pass
imports nothing new — i.e. the ``ingest.raw_event`` high-watermark
(ENG-324) has caught up to "now".

It is the on-demand equivalent of "wait for many cron ticks". It depends
on the watermark resume: without it each pass would re-read the same
oldest rows forever. Because it reuses the real ingest path, what you get
locally matches what the worker would eventually produce.

Both the ``make sync-local`` CLI (``infra/scripts/sync_local.py``) and the
local-gated ``POST /dev/sync-local`` API endpoint call this function. NOT
for production — the API surface is env-gated and this job is never
registered on the scheduled worker.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.worker.jobs.ingest_scheduled import (
    _list_tenant_ids,
    backfill_carestack_for_tenant,
    pull_carestack_for_tenant,
    pull_salesforce_for_tenant,
)
from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger

log = get_logger("worker.sync_local")

_DEFAULT_PROVIDERS = ("carestack", "salesforce")

# Deep backfill default window: the watermark (fast) mode keeps the newest
# data fresh, so the deep sweep only needs to reach back far enough to cover
# the holes a sleeping laptop leaves. 30 days is the default lookback.
_DEEP_DEFAULT_LOOKBACK_DAYS = 30


def _parse_since(since: str | None) -> datetime:
    """Parse an ISO date ``YYYY-MM-DD`` into an aware UTC datetime.

    Defaults to ``now - 30 days`` when ``since`` is omitted. Raises
    ``ValidationError`` on an unparseable value so the API surfaces a clean
    envelope instead of a 500.
    """
    if since is None:
        return datetime.now(UTC) - timedelta(days=_DEEP_DEFAULT_LOOKBACK_DAYS)
    try:
        parsed = datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValidationError(
            "since must be an ISO date (YYYY-MM-DD)",
            details={"since": since},
        ) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _sum_imported(result: dict[str, Any]) -> int:
    """Sum every ``imported_count`` in a pull result envelope.

    The per-tenant pulls return a dict whose values are per-object
    ``model_dump()`` envelopes; each carries an ``imported_count``. A
    pass that imports zero new rows everywhere means the watermark has
    caught up and we can stop.
    """
    total = 0
    for value in result.values():
        if isinstance(value, dict):
            count = value.get("imported_count")
            if isinstance(count, int):
                total += count
    return total


async def _run_one_pass(
    provider: str, tenant_id: str, max_pages: int
) -> dict[str, Any]:
    """Run a single pull for one (tenant, provider).

    CareStack accepts ``max_pages`` (it caps the three watermark-resuming
    financial feeds). Salesforce bounding is heterogeneous (per-object
    ``limit`` knobs, no page concept) so it is left unchanged — see the
    module docstring and ``pull_salesforce_for_tenant``.
    """
    if provider == "carestack":
        return await pull_carestack_for_tenant({}, tenant_id, max_pages=max_pages)
    return await pull_salesforce_for_tenant({}, tenant_id)


async def _drain_provider(
    provider: str, tenant_id: str, *, max_pages: int, max_passes: int
) -> dict[str, Any]:
    """Loop one provider for one tenant until caught up or capped."""
    passes = 0
    imported_total = 0
    imported = 0
    while passes < max_passes:
        passes += 1
        result = await _run_one_pass(provider, tenant_id, max_pages)
        if isinstance(result, dict) and result.get("skipped"):
            log.info(
                "sync_local.skipped",
                provider=provider,
                tenant_id=tenant_id,
                reason=result["skipped"],
            )
            return {
                "skipped": result["skipped"],
                "passes": passes,
                "imported": 0,
                "caught_up": False,
            }
        imported = _sum_imported(result)
        imported_total += imported
        log.info(
            "sync_local.pass",
            provider=provider,
            tenant_id=tenant_id,
            pass_num=passes,
            imported=imported,
            imported_total=imported_total,
        )
        if imported == 0:
            break
    caught_up = imported == 0
    return {
        "passes": passes,
        "imported": imported_total,
        "caught_up": caught_up,
    }


async def _backfill_provider(
    provider: str, tenant_id: str, since: datetime
) -> dict[str, Any]:
    """ENG-351: run ONE deep backfill leg for one (tenant, provider).

    CareStack runs ``backfill_carestack_for_tenant`` ONCE — ``pull_all_since``
    already drains every paginated feed to exhaustion, so no pass-loop is
    needed. Salesforce deep is NOT implemented (only ``sf_lead`` has a
    ``pull_all_since``; the event / task / opportunity / case services expose
    heterogeneous ``days`` / ``limit`` knobs, not a clean ``since`` — see the
    worker report), so Salesforce falls back to its normal watermark pull,
    run once. The leg shape matches the fast (drain) legs: ``passes``,
    ``imported``, ``caught_up``, or ``skipped``.
    """
    if provider == "carestack":
        result = await backfill_carestack_for_tenant({}, tenant_id, since)
    else:
        result = await pull_salesforce_for_tenant({}, tenant_id)

    if isinstance(result, dict) and result.get("skipped"):
        log.info(
            "sync_local.deep.skipped",
            provider=provider,
            tenant_id=tenant_id,
            reason=result["skipped"],
        )
        return {
            "skipped": result["skipped"],
            "passes": 1,
            "imported": 0,
            "caught_up": False,
        }
    imported = _sum_imported(result)
    log.info(
        "sync_local.deep.pass",
        provider=provider,
        tenant_id=tenant_id,
        imported=imported,
    )
    # A single deep sweep drains to exhaustion, so it is "caught up" by
    # construction (modulo the page_safety_cap, which the per-feed logs warn
    # about and which a re-run resumes).
    return {"passes": 1, "imported": imported, "caught_up": True}


async def run_local_sync(
    tenant_ids: list[str] | None = None,
    providers: list[str] | None = None,
    max_pages: int = 20,
    max_passes: int = 12,
    deep: bool = False,
    since: str | None = None,
) -> dict[str, Any]:
    """Drain provider pulls until the local DB is caught up.

    Two modes:

    * **Fast (default, ``deep=False``)** — the ENG-330 behaviour: for each
      tenant + provider, repeatedly run the watermark-resuming per-tenant
      pull until a pass imports 0 new rows (caught up) or ``max_passes`` is
      reached. Forward-only — keeps the newest data fresh but cannot refill
      historical holes.
    * **Deep (``deep=True``)** — ENG-351: for each tenant, run the CareStack
      deep backfill (``pull_all_since(since)``) ONCE per provider — no
      pass-loop, since ``pull_all_since`` drains every feed to exhaustion and
      re-fills historical holes. ``since`` is an ISO date ``YYYY-MM-DD``
      (default ``now - 30 days``). Salesforce uses its normal pull once (deep
      SF not implemented — see ``_backfill_provider``).

    Returns a structured summary::

        {
          "results": [
            {"tenant_id": ..., "provider": ..., "passes": int,
             "imported": int, "caught_up": bool}              # or
            {"tenant_id": ..., "provider": ..., "skipped": str, ...},
          ],
          "total_imported": int,
          "elapsed_seconds": float,
          "caught_up": bool,   # every non-skipped leg caught up
          "deep": bool,
          "since": str | None,  # ISO datetime when deep, else None
        }
    """
    started = time.monotonic()
    resolved_tenants = tenant_ids if tenant_ids is not None else await _list_tenant_ids()
    resolved_providers = list(providers) if providers is not None else list(
        _DEFAULT_PROVIDERS
    )

    # Parse ``since`` up front (deep mode only) so a bad date fails fast with
    # a clean ValidationError before any provider call.
    since_dt = _parse_since(since) if deep else None

    results: list[dict[str, Any]] = []
    total_imported = 0
    all_caught_up = True

    for tenant_id in resolved_tenants:
        for provider in resolved_providers:
            if deep:
                assert since_dt is not None  # set when deep
                outcome = await _backfill_provider(provider, tenant_id, since_dt)
            else:
                outcome = await _drain_provider(
                    provider,
                    tenant_id,
                    max_pages=max_pages,
                    max_passes=max_passes,
                )
            leg: dict[str, Any] = {
                "tenant_id": tenant_id,
                "provider": provider,
                **outcome,
            }
            results.append(leg)
            if outcome.get("skipped"):
                # A skipped leg (no credential) does not block "caught up".
                continue
            total_imported += int(outcome.get("imported", 0))
            if not outcome.get("caught_up", False):
                all_caught_up = False

    elapsed = time.monotonic() - started
    summary = {
        "results": results,
        "total_imported": total_imported,
        "elapsed_seconds": round(elapsed, 1),
        "caught_up": all_caught_up,
        "deep": deep,
        "since": since_dt.isoformat() if since_dt is not None else None,
    }
    log.info(
        "sync_local.done",
        tenants=len(resolved_tenants),
        providers=resolved_providers,
        total_imported=total_imported,
        elapsed_seconds=summary["elapsed_seconds"],
        caught_up=all_caught_up,
        deep=deep,
        since=summary["since"],
    )
    return summary
