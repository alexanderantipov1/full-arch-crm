"""Scheduled marketing ingestion (ad spend + web analytics).

Cron entry ``pull_marketing_for_all_tenants`` iterates every tenant and runs
the ad-platform spend pulls (Google Ads, Meta Ads) and the web-analytics pulls
(GA4). TikTok Ads slots into the same per-tenant loop once its connector lands.

Credential resolution per tenant + provider (ENG-490):

  1. Read the per-tenant DB credential via
     ``IntegrationCredentialService.read_for(tenant_id, "<provider>",
     "api_key")`` and build the client via ``from_credential`` — so each
     tenant pulls with ITS OWN account and ingested rows are attributed to
     the right ``tenant_id``.
  2. On ``NoCredentialError`` (no DB row for this tenant), fall back to the
     env-var account via ``from_env()`` — the Phase 1/2 transition path.
  3. When neither a DB credential nor env vars are present, the provider's
     ``*NotConnectedError`` fires and the leg short-circuits to ``skipped``
     (mirrors the CareStack / SF scheduled-pull contract). Missing
     credentials are NOT an error.

Ad/analytics data has ~1-day latency, so the cron cadence is daily and the
pull window is a rolling few days to absorb late-settling data.

Secret hygiene: only ``provider`` / ``tenant_id`` / counts are logged here;
credential payload values are NEVER logged (the credential service logs only
``provider_kind`` + ``credential_kind``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.ga4_metric_service import GoogleAnalyticsMetricIngestService
from packages.ingest.google_ads_campaign_service import GoogleAdsCampaignIngestService
from packages.ingest.gsc_query_service import GoogleSearchConsoleQueryIngestService
from packages.ingest.meta_ads_ad_service import MetaAdsAdIngestService
from packages.ingest.meta_ads_campaign_service import MetaAdsCampaignIngestService
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

log = get_logger("worker.marketing_pull")

# Rolling window per pull. Ad platforms re-settle the most recent 1-3 days, so
# we re-pull a week and rely on content-identity dedupe in the ingest service.
_DEFAULT_DAYS = 7

# Ad-level (ENG-512) D-1 refresh uses a tighter rolling window — late-settling
# spend mostly lands within 2-3 days; idempotent upserts make overlap safe.
_AD_LEVEL_DAYS = 3

# All four marketing/SEO providers store their decrypted payload under
# ``credential_kind = "api_key"`` (the ENG-489 convention, matching how the
# bootstrap providers store non-OAuth-token grants).
_MARKETING_CREDENTIAL_KIND = "api_key"


async def _read_marketing_credential(
    tenant_id: TenantId, provider_kind: str
) -> dict[str, Any] | None:
    """Return the decrypted per-tenant payload for ``provider_kind``, or None.

    ``None`` means "no DB credential for this tenant" (the caller then tries
    the env fallback). A short-lived session is opened just for the read so
    the credential lookup never shares a unit of work with the ingest pull.
    Payload values are never logged.
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
            # A malformed/locked credential is treated as "no DB credential"
            # so the env fallback / graceful skip still applies — one bad row
            # must not poison the tick.
            log.info(
                "marketing_pull.credential.unreadable",
                tenant_id=str(tenant_id),
                provider=provider_kind,
            )
            return None


async def pull_google_ads_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, days: int = _DEFAULT_DAYS
) -> dict[str, Any]:
    """Pull recent Google Ads campaign spend for one tenant.

    DB credential preferred over env; missing both short-circuits to
    ``{"skipped": "no_credential"}``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    payload = await _read_marketing_credential(tenant_id, "google_ads")
    try:
        if payload is not None:
            client = GoogleAdsClient.from_credential(payload)
        else:
            client = GoogleAdsClient.from_env()
    except GoogleAdsNotConnectedError as exc:
        log.info(
            "marketing_pull.google_ads.no_credential",
            tenant_id=tenant_id_str,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}

    async with async_session() as session:
        service = GoogleAdsCampaignIngestService(
            session=session, google_ads_client=client
        )
        try:
            result = await service.import_recent_spend(tenant_id, days=days)
        finally:
            await client.close()

    log.info(
        "marketing_pull.google_ads.done",
        tenant_id=tenant_id_str,
        imported=result.imported_count,
        unchanged=result.unchanged_count,
        skipped=result.skipped_count,
        campaigns=result.campaigns_upserted,
        accounts=result.account_count,
    )
    return result.model_dump()


async def pull_meta_ads_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, days: int = _DEFAULT_DAYS
) -> dict[str, Any]:
    """Pull recent Meta Ads campaign spend for one tenant.

    DB credential preferred over env; missing both short-circuits to
    ``{"skipped": "no_credential"}``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    payload = await _read_marketing_credential(tenant_id, "meta_ads")
    try:
        if payload is not None:
            client = MetaAdsClient.from_credential(payload)
        else:
            client = MetaAdsClient.from_env()
    except MetaAdsNotConnectedError as exc:
        log.info(
            "marketing_pull.meta_ads.no_credential",
            tenant_id=tenant_id_str,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}

    async with async_session() as session:
        service = MetaAdsCampaignIngestService(session=session, meta_ads_client=client)
        try:
            result = await service.import_recent_spend(tenant_id, days=days)
        finally:
            await client.close()

    log.info(
        "marketing_pull.meta_ads.done",
        tenant_id=tenant_id_str,
        imported=result.imported_count,
        unchanged=result.unchanged_count,
        skipped=result.skipped_count,
        campaigns=result.campaigns_upserted,
        accounts=result.account_count,
    )
    return result.model_dump()


async def pull_meta_ads_ads_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, days: int = _AD_LEVEL_DAYS
) -> dict[str, Any]:
    """Pull recent Meta Ads **ad-level** spend for one tenant (ENG-512).

    Finer-grained than the campaign pull: one row per (ad, day) into the
    ad-tier ``marketing`` tables, feeding the cost-per-lead allocator. Rolling
    ``_AD_LEVEL_DAYS`` window for late-settling spend; idempotent upserts make
    the overlap safe. DB credential preferred over env; missing both
    short-circuits to ``{"skipped": "no_credential"}``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    payload = await _read_marketing_credential(tenant_id, "meta_ads")
    try:
        if payload is not None:
            client = MetaAdsClient.from_credential(payload)
        else:
            client = MetaAdsClient.from_env()
    except MetaAdsNotConnectedError as exc:
        log.info(
            "marketing_pull.meta_ads_ads.no_credential",
            tenant_id=tenant_id_str,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}

    async with async_session() as session:
        service = MetaAdsAdIngestService(session=session, meta_ads_client=client)
        try:
            result = await service.import_recent_spend(tenant_id, days=days)
        finally:
            await client.close()

    log.info(
        "marketing_pull.meta_ads_ads.done",
        tenant_id=tenant_id_str,
        imported=result.imported_count,
        unchanged=result.unchanged_count,
        skipped=result.skipped_count,
        ads=result.campaigns_upserted,
        accounts=result.account_count,
    )
    return result.model_dump()


async def pull_ga4_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, days: int = _DEFAULT_DAYS
) -> dict[str, Any]:
    """Pull recent GA4 daily property metrics for one tenant.

    DB credential preferred over env; missing both short-circuits to
    ``{"skipped": "no_credential"}``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    payload = await _read_marketing_credential(tenant_id, "google_analytics")
    try:
        if payload is not None:
            client = GoogleAnalyticsClient.from_credential(payload)
        else:
            client = GoogleAnalyticsClient.from_env()
    except GoogleAnalyticsNotConnectedError as exc:
        log.info(
            "marketing_pull.ga4.no_credential",
            tenant_id=tenant_id_str,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}

    async with async_session() as session:
        service = GoogleAnalyticsMetricIngestService(session=session, ga_client=client)
        try:
            result = await service.import_recent_metrics(tenant_id, days=days)
            channels = await service.import_recent_channels(tenant_id, days=days)
            pages = await service.import_recent_pages(tenant_id, days=days)
        finally:
            await client.close()

    log.info(
        "marketing_pull.ga4.done",
        tenant_id=tenant_id_str,
        imported=result.imported_count,
        unchanged=result.unchanged_count,
        skipped=result.skipped_count,
        channels_imported=channels.imported_count,
        pages_imported=pages.imported_count,
    )
    return {
        "daily": result.model_dump(),
        "channels": channels.model_dump(),
        "pages": pages.model_dump(),
    }


async def pull_gsc_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, days: int = _DEFAULT_DAYS
) -> dict[str, Any]:
    """Pull recent Search Console daily query rows for one tenant.

    DB credential preferred over env; missing both (or no verified site)
    short-circuit to ``{"skipped": "no_credential"}``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    payload = await _read_marketing_credential(tenant_id, "google_search_console")
    try:
        if payload is not None:
            client = GoogleSearchConsoleClient.from_credential(payload)
        else:
            client = GoogleSearchConsoleClient.from_env()
    except GoogleSearchConsoleNotConnectedError as exc:
        log.info(
            "marketing_pull.gsc.no_credential",
            tenant_id=tenant_id_str,
            source="db" if payload is not None else "env",
            missing=exc.details.get("missing_env") or exc.details.get("missing"),
        )
        return {"skipped": "no_credential"}

    async with async_session() as session:
        service = GoogleSearchConsoleQueryIngestService(
            session=session, gsc_client=client
        )
        try:
            result = await service.import_recent_queries(tenant_id, days=days)
        except GoogleSearchConsoleNotConnectedError as exc:
            # No verified site for this token — treat as skipped, not failed.
            log.info(
                "marketing_pull.gsc.no_site",
                tenant_id=tenant_id_str,
                detail=str(exc)[:200],
            )
            return {"skipped": "no_site"}
        finally:
            await client.close()

    log.info(
        "marketing_pull.gsc.done",
        tenant_id=tenant_id_str,
        imported=result.imported_count,
        unchanged=result.unchanged_count,
        skipped=result.skipped_count,
    )
    return result.model_dump()


async def pull_marketing_for_all_tenants(ctx: dict[str, Any]) -> dict[str, int]:
    """Cron entry: iterate tenants, run each ad-platform pull.

    One bad tenant/provider must not poison the tick — every pull is wrapped
    so the loop continues and the summary records ok/skipped/failed counts.
    """
    _ = ctx
    summary = {
        "tenants": 0,
        "google_ads_ok": 0,
        "google_ads_skipped": 0,
        "google_ads_failed": 0,
        "meta_ads_ok": 0,
        "meta_ads_skipped": 0,
        "meta_ads_failed": 0,
        "meta_ads_ads_ok": 0,
        "meta_ads_ads_skipped": 0,
        "meta_ads_ads_failed": 0,
        "ga4_ok": 0,
        "ga4_skipped": 0,
        "ga4_failed": 0,
        "gsc_ok": 0,
        "gsc_skipped": 0,
        "gsc_failed": 0,
    }

    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        tenant_ids = [str(t.id) for t in tenant_rows]

    if not tenant_ids:
        log.info("marketing_pull.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        ga_outcome = await _run_safe(
            pull_google_ads_for_tenant, tenant_id_str, tag="google_ads"
        )
        summary[f"google_ads_{ga_outcome}"] += 1
        meta_outcome = await _run_safe(
            pull_meta_ads_for_tenant, tenant_id_str, tag="meta_ads"
        )
        summary[f"meta_ads_{meta_outcome}"] += 1
        meta_ads_outcome = await _run_safe(
            pull_meta_ads_ads_for_tenant, tenant_id_str, tag="meta_ads_ads"
        )
        summary[f"meta_ads_ads_{meta_ads_outcome}"] += 1
        ga4_outcome = await _run_safe(pull_ga4_for_tenant, tenant_id_str, tag="ga4")
        summary[f"ga4_{ga4_outcome}"] += 1
        gsc_outcome = await _run_safe(pull_gsc_for_tenant, tenant_id_str, tag="gsc")
        summary[f"gsc_{gsc_outcome}"] += 1

    log.info("marketing_pull.tick", summary=summary)
    return summary


async def _run_safe(fn: Any, tenant_id_str: str, *, tag: str) -> str:
    """Run one per-tenant pull. Returns 'ok' | 'skipped' | 'failed'."""
    try:
        result = await fn({}, tenant_id_str)
    except Exception as exc:  # noqa: BLE001 — cron must not crash
        log.error(
            f"marketing_pull.{tag}.error",
            tenant_id=tenant_id_str,
            error=str(exc)[:300],
        )
        return "failed"
    if isinstance(result, dict) and result.get("skipped"):
        return "skipped"
    return "ok"
