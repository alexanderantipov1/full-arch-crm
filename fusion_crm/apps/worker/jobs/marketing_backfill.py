"""One-shot HISTORICAL marketing/SEO backfill (ENG-492).

The daily ``marketing_pull`` cron only re-reads a rolling 7-day window — enough
to absorb late-settling ad spend, but it never reaches back far enough to fill a
dashboard with months of history. This job does the one-time deep load: for
every tenant and every one of the four marketing/SEO providers (Google Ads,
Meta Ads, GA4, Google Search Console) it pulls a configurable window (default
~365 days) and projects it into the curated ``marketing`` tables.

Credential resolution reuses the ENG-490 per-tenant path exactly:

  1. Read the per-tenant DB credential via
     ``IntegrationCredentialService.read_for(tenant_id, "<provider>", "api_key")``
     and build the client via ``from_credential`` — each tenant backfills with
     ITS OWN account so rows are attributed to the right ``tenant_id``.
  2. On ``NoCredentialError`` (no DB row), fall back to the env-var account via
     ``from_env()`` — the Phase 1/2 transition path.
  3. When neither a DB credential nor env vars are present, the provider's
     ``*NotConnectedError`` fires and the (tenant, provider) leg short-circuits
     to ``skipped`` — a missing credential is NOT an error.

Chunking
--------
A long window is split into bounded chunks (default 30 days each) and each chunk
is pulled through the per-service ``import_window(start_date, end_date)`` core.
Why chunk: Meta's ``act_{id}/insights`` rejects very wide ``time_range`` windows
and GSC caps each query response at a fixed row limit, so handing either one a
single 365-day range loses data. Google Ads / GA4 tolerate the full window but
are chunked the same way for one uniform, restart-safe code path.

Each chunk is idempotent: the ingest services dedupe on captured-payload
identity (re-pulled byte-identical rows are counted ``unchanged`` and skipped
before any write) and the marketing upserts are keyed on natural keys. So
overlapping chunks, retries, and a full re-run are all safe.

Secret hygiene: only ``provider`` / ``tenant_id`` / window dates / counts are
logged; credential payload values are NEVER logged.

Usage (local CLI):
    python -m apps.worker.jobs.marketing_backfill --months 12
    python -m apps.worker.jobs.marketing_backfill --days 90 --chunk-days 14
    python -m apps.worker.jobs.marketing_backfill --providers google_ads ga4

Usage (Cloud Run Job, once real creds are entered via the ENG-491 UI):
    gcloud run jobs execute fusion-job-marketing-backfill ...
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.ga4_metric_service import GoogleAnalyticsMetricIngestService
from packages.ingest.google_ads_campaign_service import GoogleAdsCampaignIngestService
from packages.ingest.gsc_query_service import GoogleSearchConsoleQueryIngestService
from packages.ingest.meta_ads_campaign_service import MetaAdsCampaignIngestService
from packages.ingest.schemas import MarketingMetricImportOut, MarketingSpendImportOut
from packages.integrations.google_ads import GoogleAdsClient, GoogleAdsNotConnectedError
from packages.integrations.google_analytics import (
    GoogleAnalyticsClient,
    GoogleAnalyticsNotConnectedError,
)
from packages.integrations.google_search_console import (
    GoogleSearchConsoleClient,
    GoogleSearchConsoleNotConnectedError,
)
from packages.integrations.meta_ads import MetaAdsClient, MetaAdsNotConnectedError
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("worker.marketing_backfill")

# Default ~12 months of history; the daily cron handles everything newer.
_DEFAULT_DAYS = 365
# Default chunk width. Narrow enough to stay under Meta's time_range ceiling and
# GSC's per-response row cap; wide enough that a year is ~12-13 requests/account.
_DEFAULT_CHUNK_DAYS = 30
# All four marketing/SEO providers store their decrypted payload under
# ``credential_kind = "api_key"`` (the ENG-489 convention).
_MARKETING_CREDENTIAL_KIND = "api_key"

PROVIDERS: tuple[str, ...] = ("google_ads", "meta_ads", "ga4", "gsc")

# provider key -> the credential provider_kind passed to ``read_for``.
_PROVIDER_KIND = {
    "google_ads": "google_ads",
    "meta_ads": "meta_ads",
    "ga4": "google_analytics",
    "gsc": "google_search_console",
}


def chunk_windows(
    *, end_date: date, days: int, chunk_days: int
) -> list[tuple[date, date]]:
    """Split ``[end_date - (days-1), end_date]`` into ``<= chunk_days`` windows.

    Returned windows are inclusive ``(start, end)`` pairs, contiguous and
    non-overlapping, ordered OLDEST first (so a partial run fills history in
    chronological order). The final/oldest window may be shorter than
    ``chunk_days`` when ``days`` is not an exact multiple.

    Example: ``days=365, chunk_days=30`` on ``end_date=2026-06-16`` yields 13
    windows — twelve 30-day windows plus one 5-day remainder at the far end.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")

    overall_start = end_date - timedelta(days=days - 1)
    windows: list[tuple[date, date]] = []
    chunk_end = end_date
    while chunk_end >= overall_start:
        chunk_start = max(overall_start, chunk_end - timedelta(days=chunk_days - 1))
        windows.append((chunk_start, chunk_end))
        chunk_end = chunk_start - timedelta(days=1)
    windows.reverse()
    return windows


async def _read_marketing_credential(
    tenant_id: TenantId, provider_kind: str
) -> dict[str, Any] | None:
    """Return the decrypted per-tenant payload for ``provider_kind``, or None.

    ``None`` means "no DB credential for this tenant" (caller then tries the env
    fallback). A short-lived session is opened just for the read. Payload values
    are never logged.
    """
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        try:
            return await cred_svc.read_for(
                tenant_id, provider_kind, _MARKETING_CREDENTIAL_KIND
            )
        except NoCredentialError:
            return None
        except PlatformError:
            log.info(
                "marketing_backfill.credential.unreadable",
                tenant_id=str(tenant_id),
                provider=provider_kind,
            )
            return None


def _build_client(provider: str, payload: dict[str, Any] | None) -> Any:
    """Build the provider client (DB credential preferred, else env).

    Raises the provider's ``*NotConnectedError`` when neither source has the
    config — the caller translates that into a graceful skip.
    """
    if provider == "google_ads":
        return (
            GoogleAdsClient.from_credential(payload)
            if payload is not None
            else GoogleAdsClient.from_env()
        )
    if provider == "meta_ads":
        return (
            MetaAdsClient.from_credential(payload)
            if payload is not None
            else MetaAdsClient.from_env()
        )
    if provider == "ga4":
        return (
            GoogleAnalyticsClient.from_credential(payload)
            if payload is not None
            else GoogleAnalyticsClient.from_env()
        )
    if provider == "gsc":
        return (
            GoogleSearchConsoleClient.from_credential(payload)
            if payload is not None
            else GoogleSearchConsoleClient.from_env()
        )
    raise ValueError(f"unknown provider: {provider}")  # pragma: no cover


_NOT_CONNECTED = (
    GoogleAdsNotConnectedError,
    MetaAdsNotConnectedError,
    GoogleAnalyticsNotConnectedError,
    GoogleSearchConsoleNotConnectedError,
)


async def _import_chunk(
    provider: str, client: Any, session: Any, tenant_id: TenantId,
    *, start_date: date, end_date: date,
) -> dict[str, int]:
    """Run one chunk through the right ingest service's ``import_window``.

    Returns a small counter dict (imported / unchanged / skipped). GSC's
    ``import_window`` may raise ``GoogleSearchConsoleNotConnectedError`` when the
    token has no verified site — the caller treats that as a skip for the whole
    provider leg, so it propagates here.
    """
    svc_result: MarketingSpendImportOut | MarketingMetricImportOut
    if provider == "google_ads":
        svc_result = await GoogleAdsCampaignIngestService(
            session=session, google_ads_client=client
        ).import_window(tenant_id, start_date=start_date, end_date=end_date)
    elif provider == "meta_ads":
        svc_result = await MetaAdsCampaignIngestService(
            session=session, meta_ads_client=client
        ).import_window(tenant_id, start_date=start_date, end_date=end_date)
    elif provider == "ga4":
        svc_result = await GoogleAnalyticsMetricIngestService(
            session=session, ga_client=client
        ).import_window(tenant_id, start_date=start_date, end_date=end_date)
    elif provider == "gsc":
        svc_result = await GoogleSearchConsoleQueryIngestService(
            session=session, gsc_client=client
        ).import_window(tenant_id, start_date=start_date, end_date=end_date)
    else:  # pragma: no cover - guarded by PROVIDERS
        raise ValueError(f"unknown provider: {provider}")
    return {
        "imported": svc_result.imported_count,
        "unchanged": svc_result.unchanged_count,
        "skipped": svc_result.skipped_count,
    }


async def backfill_provider_for_tenant(
    _ctx: dict[str, Any],
    tenant_id_str: str,
    provider: str,
    *,
    days: int = _DEFAULT_DAYS,
    chunk_days: int = _DEFAULT_CHUNK_DAYS,
) -> dict[str, Any]:
    """Backfill one (tenant, provider) over ``days`` of history, chunk by chunk.

    Graceful skip (``{"skipped": "no_credential"}``) when no DB credential and
    no env account exists. Each chunk gets its OWN DB session/unit-of-work so a
    failing chunk does not roll back the chunks that already committed — the
    idempotent re-run picks the rest back up.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {provider}")

    tenant_id = TenantId(UUID(tenant_id_str))
    provider_kind = _PROVIDER_KIND[provider]
    payload = await _read_marketing_credential(tenant_id, provider_kind)

    # Build a throwaway client once just to detect "not connected" up front, so
    # we do not open a chunk loop with no credentials. The real per-chunk client
    # is rebuilt inside the loop so each chunk owns its lifecycle.
    try:
        probe = _build_client(provider, payload)
    except _NOT_CONNECTED as exc:
        log.info(
            "marketing_backfill.no_credential",
            tenant_id=tenant_id_str,
            provider=provider,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}
    await _close_client(probe)

    end_date = datetime.now(UTC).date()
    windows = chunk_windows(end_date=end_date, days=days, chunk_days=chunk_days)

    totals = {"imported": 0, "unchanged": 0, "skipped": 0}
    chunks_ok = 0
    chunks_failed = 0

    for start_date, chunk_end in windows:
        client = _build_client(provider, payload)
        try:
            async with async_session() as session:
                counts = await _import_chunk(
                    provider, client, session, tenant_id,
                    start_date=start_date, end_date=chunk_end,
                )
            for key, value in counts.items():
                totals[key] += value
            chunks_ok += 1
            log.info(
                "marketing_backfill.chunk.done",
                tenant_id=tenant_id_str,
                provider=provider,
                start=start_date.isoformat(),
                end=chunk_end.isoformat(),
                **counts,
            )
        except GoogleSearchConsoleNotConnectedError:
            # No verified GSC site for this token — the whole provider leg is a
            # skip, not a failure. Stop the chunk loop.
            log.info(
                "marketing_backfill.gsc.no_site",
                tenant_id=tenant_id_str,
            )
            await _close_client(client)
            return {"skipped": "no_site"}
        except Exception as exc:  # noqa: BLE001 - one chunk must not abort the rest
            chunks_failed += 1
            log.error(
                "marketing_backfill.chunk.error",
                tenant_id=tenant_id_str,
                provider=provider,
                start=start_date.isoformat(),
                end=chunk_end.isoformat(),
                error=str(exc)[:300],
            )
        finally:
            await _close_client(client)

    result = {
        "provider": provider,
        "days": days,
        "chunk_days": chunk_days,
        "chunks": len(windows),
        "chunks_ok": chunks_ok,
        "chunks_failed": chunks_failed,
        **totals,
    }
    log.info("marketing_backfill.provider.done", tenant_id=tenant_id_str, **result)
    return result


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    try:
        await close()
    except Exception as exc:  # noqa: BLE001 - close failure must not abort backfill
        log.warning("marketing_backfill.client_close_failed", error=type(exc).__name__)


async def run(
    *,
    days: int = _DEFAULT_DAYS,
    chunk_days: int = _DEFAULT_CHUNK_DAYS,
    providers: tuple[str, ...] = PROVIDERS,
) -> list[dict[str, Any]]:
    """Iterate every tenant + provider and backfill ``days`` of history.

    One bad (tenant, provider) leg must not poison the run — each is wrapped so
    the loop continues and the summary records ok/skipped/failed counts.
    """
    configure_logging()
    log.info(
        "marketing_backfill.start",
        days=days,
        chunk_days=chunk_days,
        providers=list(providers),
    )

    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        tenant_ids = [str(t.id) for t in tenant_rows]

    if not tenant_ids:
        log.info("marketing_backfill.no_tenants")
        return []

    all_results: list[dict[str, Any]] = []
    for tenant_id_str in tenant_ids:
        tenant_result: dict[str, Any] = {"tenant_id": tenant_id_str}
        for provider in providers:
            tenant_result[provider] = await _run_safe(
                tenant_id_str, provider, days=days, chunk_days=chunk_days
            )
        all_results.append(tenant_result)
        log.info(
            "marketing_backfill.tenant_done",
            tenant_id=tenant_id_str,
            result=tenant_result,
        )

    log.info("marketing_backfill.complete", tenants=len(all_results))
    return all_results


async def _run_safe(
    tenant_id_str: str, provider: str, *, days: int, chunk_days: int
) -> dict[str, Any]:
    """Run one (tenant, provider) backfill, never raising into the fanout loop."""
    try:
        return await backfill_provider_for_tenant(
            {}, tenant_id_str, provider, days=days, chunk_days=chunk_days
        )
    except Exception as exc:  # noqa: BLE001 - backfill loop must not crash
        log.error(
            "marketing_backfill.provider.error",
            tenant_id=tenant_id_str,
            provider=provider,
            error=str(exc)[:300],
        )
        return {"failed": str(exc)[:200]}


async def backfill_marketing_history(
    ctx: dict[str, Any],
    *,
    days: int = _DEFAULT_DAYS,
    chunk_days: int = _DEFAULT_CHUNK_DAYS,
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """arq entrypoint: one-shot historical marketing backfill (NOT a cron).

    Enqueue on demand; this is registered in ``WorkerSettings.functions`` but
    intentionally has NO ``cron`` entry — the daily rolling pull
    (``pull_marketing_for_all_tenants``) is the recurring job.
    """
    _ = ctx
    chosen = tuple(providers) if providers else PROVIDERS
    return await run(days=days, chunk_days=chunk_days, providers=chosen)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="One-shot historical marketing/SEO backfill (ENG-492)."
    )
    window = parser.add_mutually_exclusive_group()
    window.add_argument(
        "--days",
        type=int,
        default=None,
        help=f"Window length in days (1..365). Default: {_DEFAULT_DAYS}.",
    )
    window.add_argument(
        "--months",
        type=int,
        default=None,
        help="Window length in months (30 days each). Overrides --days.",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=_DEFAULT_CHUNK_DAYS,
        help=f"Max days per provider request. Default: {_DEFAULT_CHUNK_DAYS}.",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=None,
        help=f"Subset of {', '.join(PROVIDERS)}. Default: all.",
    )
    args = parser.parse_args()

    if args.months is not None:
        days = args.months * 30
    elif args.days is not None:
        days = args.days
    else:
        days = _DEFAULT_DAYS

    if days < 1 or days > 365:
        parser.error("window must be between 1 and 365 days")
    if args.chunk_days < 1:
        parser.error("--chunk-days must be >= 1")

    if args.providers:
        flat: list[str] = []
        for raw in args.providers:
            flat.extend(p.strip() for p in raw.split(",") if p.strip())
        for p in flat:
            if p not in PROVIDERS:
                parser.error(f"Unknown provider: {p}. Valid: {', '.join(PROVIDERS)}")
        providers = tuple(flat)
    else:
        providers = PROVIDERS

    asyncio.run(run(days=days, chunk_days=args.chunk_days, providers=providers))


if __name__ == "__main__":
    main()
