"""MarketingService — the public surface for ad-spend / campaign data.

Idempotent upserts keyed on each table's natural key, plus the dashboard
spend aggregation. Callers (ingest connectors, API routes) depend on this
service only — never on the repository or models.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

from .models import (
    AD_PROVIDERS,
    Ad,
    AdCampaign,
    AdMetricDaily,
    AdMetricDailyAd,
    AdSet,
    GaChannelDaily,
    GaMetricDaily,
    GaPageDaily,
    GscQueryDaily,
)
from .repository import MarketingRepository
from .schemas import (
    AdCampaignRefOut,
    AdCampaignUpsertIn,
    AdDailySpendOut,
    AdMetricDailyAdUpsertIn,
    AdMetricDailyUpsertIn,
    AdRefOut,
    AdSetUpsertIn,
    AdSpendDailyPointOut,
    AdSpendMonthlyPointOut,
    AdSpendProviderTotalOut,
    AdSpendRowOut,
    AdSpendTotalsOut,
    AdUpsertIn,
    CampaignDailySpendOut,
    GaChannelDailyUpsertIn,
    GaChannelRowOut,
    GaEngagementTotalsOut,
    GaMetricDailyPointOut,
    GaMetricDailyUpsertIn,
    GaMetricTotalsOut,
    GaPageDailyUpsertIn,
    GaPageRowOut,
    GscQueryDailyUpsertIn,
    GscQueryRowOut,
    GscQueryTotalsOut,
    MarketingSpendBreakdownOut,
    UpsertResult,
)

# How many GSC top-query rows the SEO dashboard table shows by default.
_GSC_TOP_QUERIES_DEFAULT_LIMIT = 25

# How many GA4 top-page rows the SEO dashboard table shows by default.
_GA_TOP_PAGES_DEFAULT_LIMIT = 25

# Campaign fields whose change flips ``was_changed`` (drives re-emit / logs).
_CAMPAIGN_WATCHED = ("name", "status", "objective", "account_id")


def _require_provider(provider: str) -> None:
    if provider not in AD_PROVIDERS:
        raise ValidationError(
            "unknown ad provider",
            details={"provider": provider, "allowed": list(AD_PROVIDERS)},
        )


def _num_equal(current: object, incoming: float) -> bool:
    """Compare a DB Numeric (Decimal) against an incoming float safely."""
    if isinstance(current, int | float | Decimal):
        return float(current) == float(incoming)
    return False


class MarketingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MarketingRepository(session)

    async def upsert_campaign(
        self, tenant_id: TenantId, payload: AdCampaignUpsertIn
    ) -> UpsertResult:
        _require_provider(payload.provider)
        if not payload.external_id.strip():
            raise ValidationError("campaign external_id is required")

        existing = await self._repo.get_campaign(
            tenant_id, provider=payload.provider, external_id=payload.external_id
        )
        if existing is None:
            await self._repo.add_campaign(
                AdCampaign(
                    tenant_id=tenant_id,
                    provider=payload.provider,
                    external_id=payload.external_id,
                    name=payload.name,
                    status=payload.status,
                    objective=payload.objective,
                    account_id=payload.account_id,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in _CAMPAIGN_WATCHED:
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if payload.extra and existing.extra != payload.extra:
            existing.extra = {**existing.extra, **dict(payload.extra)}
            changed = True
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_metric_daily(
        self, tenant_id: TenantId, payload: AdMetricDailyUpsertIn
    ) -> UpsertResult:
        _require_provider(payload.provider)
        if not payload.campaign_external_id.strip():
            raise ValidationError("metric campaign_external_id is required")

        existing = await self._repo.get_metric(
            tenant_id,
            provider=payload.provider,
            campaign_external_id=payload.campaign_external_id,
            metric_date=payload.metric_date,
        )
        if existing is None:
            await self._repo.add_metric(
                AdMetricDaily(
                    tenant_id=tenant_id,
                    provider=payload.provider,
                    campaign_external_id=payload.campaign_external_id,
                    metric_date=payload.metric_date,
                    spend=payload.spend,
                    impressions=payload.impressions,
                    clicks=payload.clicks,
                    conversions=payload.conversions,
                    currency=payload.currency,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        if not _num_equal(existing.spend, payload.spend):
            existing.spend = payload.spend
            changed = True
        if existing.impressions != payload.impressions:
            existing.impressions = payload.impressions
            changed = True
        if existing.clicks != payload.clicks:
            existing.clicks = payload.clicks
            changed = True
        if not _num_equal(existing.conversions, payload.conversions):
            existing.conversions = payload.conversions
            changed = True
        if payload.currency is not None and existing.currency != payload.currency:
            existing.currency = payload.currency
            changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ad_set(
        self, tenant_id: TenantId, payload: AdSetUpsertIn
    ) -> UpsertResult:
        """Idempotent upsert of one ad set on ``(tenant, provider, external_id)``."""
        _require_provider(payload.provider)
        if not payload.external_id.strip():
            raise ValidationError("ad_set external_id is required")

        existing = await self._repo.get_ad_set(
            tenant_id, provider=payload.provider, external_id=payload.external_id
        )
        if existing is None:
            await self._repo.add_ad_set(
                AdSet(
                    tenant_id=tenant_id,
                    provider=payload.provider,
                    external_id=payload.external_id,
                    name=payload.name,
                    campaign_external_id=payload.campaign_external_id,
                    account_id=payload.account_id,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in ("name", "campaign_external_id", "account_id"):
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if payload.extra and existing.extra != payload.extra:
            existing.extra = {**existing.extra, **dict(payload.extra)}
            changed = True
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ad(
        self, tenant_id: TenantId, payload: AdUpsertIn
    ) -> UpsertResult:
        """Idempotent upsert of one ad on ``(tenant, provider, external_id)``."""
        _require_provider(payload.provider)
        if not payload.external_id.strip():
            raise ValidationError("ad external_id is required")

        existing = await self._repo.get_ad(
            tenant_id, provider=payload.provider, external_id=payload.external_id
        )
        if existing is None:
            await self._repo.add_ad(
                Ad(
                    tenant_id=tenant_id,
                    provider=payload.provider,
                    external_id=payload.external_id,
                    name=payload.name,
                    adset_external_id=payload.adset_external_id,
                    campaign_external_id=payload.campaign_external_id,
                    account_id=payload.account_id,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in (
            "name",
            "adset_external_id",
            "campaign_external_id",
            "account_id",
        ):
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if payload.extra and existing.extra != payload.extra:
            existing.extra = {**existing.extra, **dict(payload.extra)}
            changed = True
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ad_metric_daily(
        self, tenant_id: TenantId, payload: AdMetricDailyAdUpsertIn
    ) -> UpsertResult:
        """Idempotent upsert of one ad's metrics on one day (ENG-512).

        Natural key ``(tenant, provider, ad_external_id, metric_date)``.
        """
        _require_provider(payload.provider)
        if not payload.ad_external_id.strip():
            raise ValidationError("metric ad_external_id is required")

        existing = await self._repo.get_ad_metric(
            tenant_id,
            provider=payload.provider,
            ad_external_id=payload.ad_external_id,
            metric_date=payload.metric_date,
        )
        if existing is None:
            await self._repo.add_ad_metric(
                AdMetricDailyAd(
                    tenant_id=tenant_id,
                    provider=payload.provider,
                    ad_external_id=payload.ad_external_id,
                    adset_external_id=payload.adset_external_id,
                    campaign_external_id=payload.campaign_external_id,
                    metric_date=payload.metric_date,
                    spend=payload.spend,
                    impressions=payload.impressions,
                    clicks=payload.clicks,
                    conversions=payload.conversions,
                    currency=payload.currency,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        if not _num_equal(existing.spend, payload.spend):
            existing.spend = payload.spend
            changed = True
        if existing.impressions != payload.impressions:
            existing.impressions = payload.impressions
            changed = True
        if existing.clicks != payload.clicks:
            existing.clicks = payload.clicks
            changed = True
        if not _num_equal(existing.conversions, payload.conversions):
            existing.conversions = payload.conversions
            changed = True
        for field in ("adset_external_id", "campaign_external_id"):
            if getattr(payload, field) is not None and getattr(
                existing, field
            ) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if payload.currency is not None and existing.currency != payload.currency:
            existing.currency = payload.currency
            changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    # --- cost-per-lead allocator reads (ENG-512) -----------------------------

    async def list_ads(
        self, tenant_id: TenantId, *, provider: str | None = None
    ) -> list[AdRefOut]:
        """Ad identity rows for the cost-per-lead bridge (slug ↔ id/name)."""
        return [AdRefOut.model_validate(r) for r in await self._repo.list_ads(
            tenant_id, provider=provider
        )]

    async def list_campaigns(
        self, tenant_id: TenantId, *, provider: str | None = None
    ) -> list[AdCampaignRefOut]:
        """Campaign identity rows for the cost-per-lead bridge (slug ↔ id/name)."""
        return [
            AdCampaignRefOut.model_validate(r)
            for r in await self._repo.list_campaigns(tenant_id, provider=provider)
        ]

    async def ad_daily_spend(
        self, tenant_id: TenantId, *, start_date: date, end_date: date
    ) -> list[AdDailySpendOut]:
        """Per-(ad, day) spend over a window for the allocator's ad tier."""
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        rows = await self._repo.ad_daily_spend(
            tenant_id, start_date=start_date, end_date=end_date
        )
        return [AdDailySpendOut(**row) for row in rows]

    async def campaign_daily_spend(
        self, tenant_id: TenantId, *, start_date: date, end_date: date
    ) -> list[CampaignDailySpendOut]:
        """Per-(campaign, day) spend over a window for the allocator's fallback tier."""
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        rows = await self._repo.campaign_daily_spend(
            tenant_id, start_date=start_date, end_date=end_date
        )
        return [CampaignDailySpendOut(**row) for row in rows]

    async def upsert_gsc_query_daily(
        self, tenant_id: TenantId, payload: GscQueryDailyUpsertIn
    ) -> UpsertResult:
        if not payload.site_url.strip():
            raise ValidationError("gsc site_url is required")
        query_hash = hashlib.sha256(payload.query.encode("utf-8")).hexdigest()

        existing = await self._repo.get_gsc_query(
            tenant_id,
            site_url=payload.site_url,
            metric_date=payload.metric_date,
            query_hash=query_hash,
        )
        if existing is None:
            await self._repo.add_gsc_query(
                GscQueryDaily(
                    tenant_id=tenant_id,
                    site_url=payload.site_url,
                    metric_date=payload.metric_date,
                    query=payload.query,
                    query_hash=query_hash,
                    clicks=payload.clicks,
                    impressions=payload.impressions,
                    ctr=payload.ctr,
                    position=payload.position,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        if existing.clicks != payload.clicks:
            existing.clicks = payload.clicks
            changed = True
        if existing.impressions != payload.impressions:
            existing.impressions = payload.impressions
            changed = True
        if not _num_equal(existing.ctr, payload.ctr):
            existing.ctr = payload.ctr
            changed = True
        if not _num_equal(existing.position, payload.position):
            existing.position = payload.position
            changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ga_metric_daily(
        self, tenant_id: TenantId, payload: GaMetricDailyUpsertIn
    ) -> UpsertResult:
        if not payload.property_id.strip():
            raise ValidationError("ga property_id is required")

        existing = await self._repo.get_ga_metric(
            tenant_id, property_id=payload.property_id, metric_date=payload.metric_date
        )
        if existing is None:
            await self._repo.add_ga_metric(
                GaMetricDaily(
                    tenant_id=tenant_id,
                    property_id=payload.property_id,
                    metric_date=payload.metric_date,
                    sessions=payload.sessions,
                    total_users=payload.total_users,
                    new_users=payload.new_users,
                    screen_page_views=payload.screen_page_views,
                    conversions=payload.conversions,
                    engaged_sessions=payload.engaged_sessions,
                    engagement_rate=payload.engagement_rate,
                    avg_session_duration=payload.avg_session_duration,
                    bounce_rate=payload.bounce_rate,
                    event_count=payload.event_count,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in ("sessions", "total_users", "new_users", "screen_page_views"):
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if not _num_equal(existing.conversions, payload.conversions):
            existing.conversions = payload.conversions
            changed = True
        # Engagement columns (ENG-478): only overwrite when the incoming pull
        # carried the value (``None`` = not requested → leave the stored value).
        for int_field in ("engaged_sessions", "event_count"):
            incoming = getattr(payload, int_field)
            if incoming is not None and getattr(existing, int_field) != incoming:
                setattr(existing, int_field, incoming)
                changed = True
        for num_field in ("engagement_rate", "avg_session_duration", "bounce_rate"):
            incoming = getattr(payload, num_field)
            if incoming is not None and not _num_equal(
                getattr(existing, num_field), incoming
            ):
                setattr(existing, num_field, incoming)
                changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ga_channel_daily(
        self, tenant_id: TenantId, payload: GaChannelDailyUpsertIn
    ) -> UpsertResult:
        if not payload.property_id.strip():
            raise ValidationError("ga property_id is required")
        if not payload.channel.strip():
            raise ValidationError("ga channel is required")

        existing = await self._repo.get_ga_channel(
            tenant_id,
            property_id=payload.property_id,
            metric_date=payload.metric_date,
            channel=payload.channel,
        )
        if existing is None:
            await self._repo.add_ga_channel(
                GaChannelDaily(
                    tenant_id=tenant_id,
                    property_id=payload.property_id,
                    metric_date=payload.metric_date,
                    channel=payload.channel,
                    sessions=payload.sessions,
                    total_users=payload.total_users,
                    new_users=payload.new_users,
                    screen_page_views=payload.screen_page_views,
                    conversions=payload.conversions,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in ("sessions", "total_users", "new_users", "screen_page_views"):
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if not _num_equal(existing.conversions, payload.conversions):
            existing.conversions = payload.conversions
            changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def upsert_ga_page_daily(
        self, tenant_id: TenantId, payload: GaPageDailyUpsertIn
    ) -> UpsertResult:
        if not payload.property_id.strip():
            raise ValidationError("ga property_id is required")
        if not payload.page_path.strip():
            raise ValidationError("ga page_path is required")
        page_hash = hashlib.sha256(payload.page_path.encode("utf-8")).hexdigest()

        existing = await self._repo.get_ga_page(
            tenant_id,
            property_id=payload.property_id,
            metric_date=payload.metric_date,
            page_hash=page_hash,
        )
        if existing is None:
            await self._repo.add_ga_page(
                GaPageDaily(
                    tenant_id=tenant_id,
                    property_id=payload.property_id,
                    metric_date=payload.metric_date,
                    page_path=payload.page_path,
                    page_hash=page_hash,
                    sessions=payload.sessions,
                    total_users=payload.total_users,
                    new_users=payload.new_users,
                    screen_page_views=payload.screen_page_views,
                    conversions=payload.conversions,
                    raw_event_id=payload.raw_event_id,
                    extra=dict(payload.extra),
                )
            )
            return UpsertResult(was_created=True, was_changed=True)

        changed = False
        for field in ("sessions", "total_users", "new_users", "screen_page_views"):
            if getattr(existing, field) != getattr(payload, field):
                setattr(existing, field, getattr(payload, field))
                changed = True
        if not _num_equal(existing.conversions, payload.conversions):
            existing.conversions = payload.conversions
            changed = True
        if payload.raw_event_id is not None and existing.raw_event_id != payload.raw_event_id:
            existing.raw_event_id = payload.raw_event_id
        if changed:
            await self._session.flush()
        return UpsertResult(was_created=False, was_changed=changed)

    async def ad_spend_totals(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> AdSpendTotalsOut:
        """Tenant-wide spend totals + per-campaign breakdown over a window."""
        if provider is not None:
            _require_provider(provider)
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        rows = await self._repo.aggregate_spend(
            tenant_id, start_date=start_date, end_date=end_date, provider=provider
        )
        out_rows = [AdSpendRowOut(**row) for row in rows]
        return AdSpendTotalsOut(
            spend=sum(r.spend for r in out_rows),
            impressions=sum(r.impressions for r in out_rows),
            clicks=sum(r.clicks for r in out_rows),
            conversions=sum(r.conversions for r in out_rows),
            rows=out_rows,
        )

    async def spend_breakdown(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> MarketingSpendBreakdownOut:
        """Dashboard spend aggregates over a window: daily trend, provider
        split, per-campaign rows, and tenant-wide totals — in one read.

        Each cut is computed by its own group-by in the repository; the
        per-campaign rows reuse :meth:`ad_spend_totals` so the campaign table
        and the KPI totals stay byte-identical to the existing read.
        """
        if provider is not None:
            _require_provider(provider)
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        totals = await self.ad_spend_totals(
            tenant_id, start_date=start_date, end_date=end_date, provider=provider
        )
        daily_rows = await self._repo.aggregate_daily_by_provider(
            tenant_id, start_date=start_date, end_date=end_date, provider=provider
        )
        provider_rows = await self._repo.aggregate_provider_totals(
            tenant_id, start_date=start_date, end_date=end_date, provider=provider
        )
        return MarketingSpendBreakdownOut(
            spend=totals.spend,
            impressions=totals.impressions,
            clicks=totals.clicks,
            conversions=totals.conversions,
            daily=[AdSpendDailyPointOut(**row) for row in daily_rows],
            providers=[AdSpendProviderTotalOut(**row) for row in provider_rows],
            campaigns=totals.rows,
        )

    async def monthly_spend_by_provider(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> list[AdSpendMonthlyPointOut]:
        """Spend/impressions/clicks/conversions per (month, provider).

        Feeds the ENG-472 full-funnel report's monthly spend row. The month
        bucket keys off ``metric_date``; the caller maps provider→channel
        (google_ads→google, meta_ads→facebook).
        """
        if provider is not None:
            _require_provider(provider)
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        rows = await self._repo.aggregate_monthly_by_provider(
            tenant_id, start_date=start_date, end_date=end_date, provider=provider
        )
        return [AdSpendMonthlyPointOut(**row) for row in rows]

    async def ga_metric_totals(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        top_pages_limit: int = _GA_TOP_PAGES_DEFAULT_LIMIT,
    ) -> GaMetricTotalsOut:
        """GA4 window totals + daily trend for the SEO dashboard (ENG-471/478).

        Sums sessions/users/new_users/pageviews/conversions across every
        captured GA4 property over the window; the daily series feeds the
        trend chart. ``total_users`` / ``new_users`` are day-summed (GA4 keeps
        only the per-day rollup), not deduplicated unique counts. Also composes
        the engagement rollup, the acquisition-channel split, and the top pages
        (ENG-478) — each from its own ``marketing`` projection table.
        """
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        daily_rows = await self._repo.aggregate_ga_daily(
            tenant_id, start_date=start_date, end_date=end_date
        )
        daily = [GaMetricDailyPointOut(**row) for row in daily_rows]
        engagement = await self._repo.aggregate_ga_engagement(
            tenant_id, start_date=start_date, end_date=end_date
        )
        channel_rows = await self._repo.aggregate_ga_channels(
            tenant_id, start_date=start_date, end_date=end_date
        )
        page_rows = await self._repo.aggregate_ga_top_pages(
            tenant_id, start_date=start_date, end_date=end_date, limit=top_pages_limit
        )
        return GaMetricTotalsOut(
            sessions=sum(p.sessions for p in daily),
            total_users=sum(p.total_users for p in daily),
            new_users=sum(p.new_users for p in daily),
            screen_page_views=sum(p.screen_page_views for p in daily),
            conversions=sum(p.conversions for p in daily),
            daily=daily,
            engagement=GaEngagementTotalsOut(**engagement),
            channels=[GaChannelRowOut(**row) for row in channel_rows],
            top_pages=[GaPageRowOut(**row) for row in page_rows],
        )

    async def gsc_query_totals(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        top_queries_limit: int = _GSC_TOP_QUERIES_DEFAULT_LIMIT,
    ) -> GscQueryTotalsOut:
        """GSC window totals + top-queries table for the SEO dashboard (ENG-471).

        Summed clicks/impressions, distinct query count, impression-weighted
        CTR and average position (both ``None`` on a zero-impression window),
        plus the top queries by clicks.
        """
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={"start_date": str(start_date), "end_date": str(end_date)},
            )
        totals = await self._repo.aggregate_gsc_totals(
            tenant_id, start_date=start_date, end_date=end_date
        )
        top_rows = await self._repo.aggregate_gsc_top_queries(
            tenant_id,
            start_date=start_date,
            end_date=end_date,
            limit=top_queries_limit,
        )
        return GscQueryTotalsOut(
            clicks=totals["clicks"],
            impressions=totals["impressions"],
            ctr=totals["ctr"],
            avg_position=totals["avg_position"],
            distinct_queries=totals["distinct_queries"],
            top_queries=[GscQueryRowOut(**row) for row in top_rows],
        )
