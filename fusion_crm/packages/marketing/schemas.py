"""Marketing DTOs — inputs end with ``In``, outputs with ``Out``."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AdCampaignUpsertIn(BaseModel):
    """Upsert payload for one ad-platform campaign."""

    provider: str
    external_id: str
    name: str | None = None
    status: str | None = None
    objective: str | None = None
    account_id: str | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdMetricDailyUpsertIn(BaseModel):
    """Upsert payload for one campaign's metrics on one day."""

    provider: str
    campaign_external_id: str
    metric_date: date
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    currency: str | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdSetUpsertIn(BaseModel):
    """Upsert payload for one ad set (Meta) / ad group (ENG-512)."""

    provider: str
    external_id: str
    name: str | None = None
    campaign_external_id: str | None = None
    account_id: str | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdUpsertIn(BaseModel):
    """Upsert payload for one ad / creative (ENG-512)."""

    provider: str
    external_id: str
    name: str | None = None
    adset_external_id: str | None = None
    campaign_external_id: str | None = None
    account_id: str | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdMetricDailyAdUpsertIn(BaseModel):
    """Upsert payload for one ad's metrics on one day (ENG-512)."""

    provider: str
    ad_external_id: str
    adset_external_id: str | None = None
    campaign_external_id: str | None = None
    metric_date: date
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    currency: str | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdRefOut(BaseModel):
    """Ad identity row for the cost-per-lead bridge (ENG-512).

    The allocator reads these to bridge an ``attribution.source_node`` (level
    ``ad``) to platform spend: it matches the node slug against ``external_id``
    (utm=id) OR a slug of ``name`` (utm=name).
    """

    model_config = ConfigDict(from_attributes=True)

    provider: str
    external_id: str
    name: str | None
    campaign_external_id: str | None


class AdCampaignRefOut(BaseModel):
    """Campaign identity row for the cost-per-lead bridge (ENG-512)."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    external_id: str
    name: str | None


class AdDailySpendOut(BaseModel):
    """One (ad, day) spend point for the cost-per-lead allocator (ENG-512)."""

    ad_external_id: str
    campaign_external_id: str | None
    metric_date: date
    spend: float


class CampaignDailySpendOut(BaseModel):
    """One (campaign, day) spend point for the cost-per-lead allocator (ENG-512)."""

    campaign_external_id: str
    metric_date: date
    spend: float


class UpsertResult(BaseModel):
    """Whether an upsert created a row and/or changed watched fields."""

    was_created: bool
    was_changed: bool


class GscQueryDailyUpsertIn(BaseModel):
    """Upsert payload for one GSC (site, day, query) row."""

    site_url: str
    metric_date: date
    query: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class GaMetricDailyUpsertIn(BaseModel):
    """Upsert payload for one GA4 property's metrics on one day.

    Engagement fields (ENG-478) are optional/nullable — a pull that did not
    request them leaves them ``None`` rather than overwriting with 0.
    """

    property_id: str
    metric_date: date
    sessions: int = 0
    total_users: int = 0
    new_users: int = 0
    screen_page_views: int = 0
    conversions: float = 0.0
    engaged_sessions: int | None = None
    engagement_rate: float | None = None
    avg_session_duration: float | None = None
    bounce_rate: float | None = None
    event_count: int | None = None
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class GaChannelDailyUpsertIn(BaseModel):
    """Upsert payload for one GA4 (property, day, channel) row."""

    property_id: str
    metric_date: date
    channel: str
    sessions: int = 0
    total_users: int = 0
    new_users: int = 0
    screen_page_views: int = 0
    conversions: float = 0.0
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class GaPageDailyUpsertIn(BaseModel):
    """Upsert payload for one GA4 (property, day, page) row."""

    property_id: str
    metric_date: date
    page_path: str
    sessions: int = 0
    total_users: int = 0
    new_users: int = 0
    screen_page_views: int = 0
    conversions: float = 0.0
    raw_event_id: uuid.UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class AdSpendRowOut(BaseModel):
    """Aggregated spend for a campaign over a date range (dashboard read)."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    campaign_external_id: str
    campaign_name: str | None
    spend: float
    impressions: int
    clicks: int
    conversions: float


class AdSpendTotalsOut(BaseModel):
    """Tenant-wide spend totals over a date range, with per-row breakdown."""

    spend: float
    impressions: int
    clicks: int
    conversions: float
    rows: list[AdSpendRowOut]


class AdSpendDailyPointOut(BaseModel):
    """One (day, provider) point of the marketing dashboard daily trend."""

    metric_date: date
    provider: str
    spend: float
    impressions: int
    clicks: int
    conversions: float


class AdSpendProviderTotalOut(BaseModel):
    """One provider's spend totals over the window (provider-split tile)."""

    provider: str
    spend: float
    impressions: int
    clicks: int
    conversions: float


class AdSpendMonthlyPointOut(BaseModel):
    """One (month, provider) point of monthly spend (full-funnel report).

    ``month`` is the ``metric_date`` calendar month (``"YYYY-MM"``).
    """

    month: str
    provider: str
    spend: float
    impressions: int
    clicks: int
    conversions: float


class MarketingSpendBreakdownOut(BaseModel):
    """Marketing spend aggregates for the dashboard over one date window.

    ``daily`` carries one row per (day, provider) for the trend chart;
    ``providers`` carries the window totals per provider for the split tile;
    ``campaigns`` reuses the per-campaign rows from :meth:`ad_spend_totals`.
    The scalar totals are the tenant-wide sums over the window.
    """

    spend: float
    impressions: int
    clicks: int
    conversions: float
    daily: list[AdSpendDailyPointOut]
    providers: list[AdSpendProviderTotalOut]
    campaigns: list[AdSpendRowOut]


# ---------------------------------------------------------------------------
# Web-analytics window aggregation reads (ENG-471 SEO dashboard).
# GA4 (``ga_metric_daily``) and GSC (``gsc_query_daily``) window rollups for
# the staff SEO dashboard. Read-only; no upsert counterpart.
# ---------------------------------------------------------------------------


class GaMetricDailyPointOut(BaseModel):
    """One day of the GA4 daily trend (summed across all properties)."""

    metric_date: date
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class GaEngagementTotalsOut(BaseModel):
    """GA4 engagement window rollup (ENG-478).

    ``engaged_sessions`` / ``event_count`` are window sums. The rates are
    session-weighted over the window (``engagement_rate`` /
    ``avg_session_duration`` weighted by ``sessions``; ``bounce_rate`` weighted
    by ``sessions``) and are ``None`` when no engagement columns were captured
    for the window — the UI renders ``"—"`` rather than a fabricated 0. Rows
    pulled before ENG-478 have NULL engagement columns and contribute nothing.
    """

    engaged_sessions: int | None = None
    engagement_rate: float | None = None
    avg_session_duration: float | None = None
    bounce_rate: float | None = None
    event_count: int | None = None


class GaChannelRowOut(BaseModel):
    """One acquisition channel's window totals (GA4 channel split)."""

    channel: str
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class GaPageRowOut(BaseModel):
    """One page's window totals (GA4 top-pages table)."""

    page_path: str
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class GaMetricTotalsOut(BaseModel):
    """GA4 window totals + the daily trend for the SEO dashboard.

    Sums are over every captured GA4 property in the tenant for the window.
    ``total_users`` / ``new_users`` are summed across days, so they are a
    day-summed approximation, not a deduplicated unique-user count (GA4 keeps
    only the per-day rollup; the unduplicated figure is not ingested).
    ``engagement`` carries the additive engagement rollup (ENG-478);
    ``channels`` / ``top_pages`` carry the channel split and top pages.
    """

    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float
    daily: list[GaMetricDailyPointOut]
    engagement: GaEngagementTotalsOut
    channels: list[GaChannelRowOut]
    top_pages: list[GaPageRowOut]


class GscQueryRowOut(BaseModel):
    """One search query's window totals (GSC top-queries table)."""

    query: str
    clicks: int
    impressions: int
    # Impression-weighted over the window: clicks / impressions (None when the
    # query had zero impressions in the window — the UI renders "—").
    ctr: float | None = None
    # Impression-weighted average position over the window (None when the
    # query had zero impressions in the window).
    position: float | None = None


class GscQueryTotalsOut(BaseModel):
    """GSC window totals + the top-queries table for the SEO dashboard.

    ``ctr`` is impression-weighted (``SUM(clicks) / SUM(impressions)``) and
    ``avg_position`` is impression-weighted (``SUM(position * impressions) /
    SUM(impressions)``); both are ``None`` when no impressions were recorded
    in the window so the UI renders ``"—"`` rather than a fabricated ``0``.
    ``distinct_queries`` counts distinct ``query_hash`` values in the window.
    """

    clicks: int
    impressions: int
    ctr: float | None = None
    avg_position: float | None = None
    distinct_queries: int
    top_queries: list[GscQueryRowOut]
