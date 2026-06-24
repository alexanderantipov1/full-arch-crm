"""Marketing models: ad campaigns + daily ad metrics (spend).

NON-PHI, non-person aggregate marketing data. Every external object is
still captured at 100% fidelity in ``ingest.raw_event``; these tables are
the curated query projection the dashboards and the lead↔spend join read.

Each table is tenant-scoped (``TenantScopedMixin``) and idempotent on its
natural key so the scheduled pull re-upserts safely on every run.
"""

from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy import Date, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "marketing"

# Ad platforms whose spend/campaign data lands in this schema. Widen the
# tuple AND the CHECK constraints (here + migration) together when a fourth
# platform lands.
AD_PROVIDERS = ("google_ads", "meta_ads", "tiktok_ads")

_AD_PROVIDER_SQL = "provider IN ('google_ads', 'meta_ads', 'tiktok_ads')"


class AdCampaign(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A campaign mirrored from an ad platform (Google/Meta/TikTok).

    Idempotent on ``(tenant_id, provider, external_id)`` — the scheduled
    pull re-upserts on every run. ``account_id`` is the platform account
    the campaign belongs to (multiple child accounts per tenant).
    """

    __tablename__ = "ad_campaign"
    __table_args__ = (
        sa.CheckConstraint(_AD_PROVIDER_SQL, name="ck_ad_campaign_provider"),
        UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ad_campaign_natural"
        ),
        Index("ix_ad_campaign_tenant_id", "tenant_id"),
        Index("ix_ad_campaign_tenant_provider", "tenant_id", "provider"),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    name: Mapped[str | None] = mapped_column(String(480))
    status: Mapped[str | None] = mapped_column(String(64))
    objective: Mapped[str | None] = mapped_column(String(128))
    account_id: Mapped[str | None] = mapped_column(String(128))
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class AdMetricDaily(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily campaign metrics — spend, impressions, clicks, conversions.

    Idempotent on ``(tenant_id, provider, campaign_external_id, metric_date)``.
    Keyed by the campaign's platform ``external_id`` (a string) rather than a
    FK to :class:`AdCampaign` so a metric row can be upserted independently of
    campaign-row ordering within the same pull.
    """

    __tablename__ = "ad_metric_daily"
    __table_args__ = (
        sa.CheckConstraint(_AD_PROVIDER_SQL, name="ck_ad_metric_daily_provider"),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "campaign_external_id",
            "metric_date",
            name="uq_ad_metric_daily_natural",
        ),
        Index("ix_ad_metric_daily_tenant_id", "tenant_id"),
        Index(
            "ix_ad_metric_daily_tenant_provider_date",
            "tenant_id",
            "provider",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    campaign_external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    spend: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    impressions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    clicks: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    conversions: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    currency: Mapped[str | None] = mapped_column(String(8))
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class AdSet(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """An ad set (Meta) / ad group mirrored from an ad platform (ENG-512).

    The middle tier of the ad hierarchy (campaign → ad_set → ad). Idempotent
    on ``(tenant_id, provider, external_id)``. ``campaign_external_id`` is the
    parent campaign's platform id (a string, not a FK) so an ad-set row upserts
    independently of campaign-row ordering within one pull — mirrors how
    :class:`AdMetricDaily` keys by the campaign string.
    """

    __tablename__ = "ad_set"
    __table_args__ = (
        sa.CheckConstraint(_AD_PROVIDER_SQL, name="ck_ad_set_provider"),
        UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ad_set_natural"
        ),
        Index("ix_ad_set_tenant_id", "tenant_id"),
        Index("ix_ad_set_tenant_provider", "tenant_id", "provider"),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    name: Mapped[str | None] = mapped_column(String(480))
    campaign_external_id: Mapped[str | None] = mapped_column(String(240))
    account_id: Mapped[str | None] = mapped_column(String(128))
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class Ad(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A single ad/creative mirrored from an ad platform (ENG-512).

    The innermost tier of the ad hierarchy. Idempotent on ``(tenant_id,
    provider, external_id)``. ``adset_external_id`` / ``campaign_external_id``
    are the parent platform ids (strings, not FKs) so an ad row upserts
    independently of parent-row ordering within one pull. ``name`` is the
    platform ad name — the cost-per-lead allocator (ENG-512) bridges this row to
    an ``attribution.source_node`` (level ``ad``) by matching the node slug
    against the platform ``external_id`` (utm=id convention) OR a slug of
    ``name`` (utm=name convention); see ``packages/analytics/cost_allocation.py``.
    """

    __tablename__ = "ad"
    __table_args__ = (
        sa.CheckConstraint(_AD_PROVIDER_SQL, name="ck_ad_provider"),
        UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ad_natural"
        ),
        Index("ix_ad_tenant_id", "tenant_id"),
        Index("ix_ad_tenant_provider", "tenant_id", "provider"),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    name: Mapped[str | None] = mapped_column(String(480))
    adset_external_id: Mapped[str | None] = mapped_column(String(240))
    campaign_external_id: Mapped[str | None] = mapped_column(String(240))
    account_id: Mapped[str | None] = mapped_column(String(128))
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class AdMetricDailyAd(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily ad-level metrics — spend/impressions/clicks/conversions (ENG-512).

    One row per (ad, day). Idempotent on ``(tenant_id, provider,
    ad_external_id, metric_date)``. Keyed by the ad's platform ``external_id``
    string (not a FK to :class:`Ad`) so a metric row upserts independently of
    ad-row ordering within one pull — mirrors :class:`AdMetricDaily`. Carries
    the parent ``adset_external_id`` / ``campaign_external_id`` denormalised so
    the cost-per-lead allocator can roll ad spend up to the campaign tier
    without a second join.
    """

    __tablename__ = "ad_metric_daily_ad"
    __table_args__ = (
        sa.CheckConstraint(_AD_PROVIDER_SQL, name="ck_ad_metric_daily_ad_provider"),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "ad_external_id",
            "metric_date",
            name="uq_ad_metric_daily_ad_natural",
        ),
        Index("ix_ad_metric_daily_ad_tenant_id", "tenant_id"),
        Index(
            "ix_ad_metric_daily_ad_tenant_provider_date",
            "tenant_id",
            "provider",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ad_external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    adset_external_id: Mapped[str | None] = mapped_column(String(240))
    campaign_external_id: Mapped[str | None] = mapped_column(String(240))
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    spend: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    impressions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    clicks: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    conversions: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    currency: Mapped[str | None] = mapped_column(String(8))
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class GscQueryDaily(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily Google Search Console rows — one per (site, day, search query).

    Aggregate, non-PHI organic-search data pulled read-only from the Webmasters
    API. Idempotent on ``(tenant_id, site_url, metric_date, query_hash)`` —
    ``query_hash`` (sha256 of the raw query) keys the unique constraint because
    search queries can exceed the btree index size limit; the verbatim query is
    kept in ``query`` (Text).
    """

    __tablename__ = "gsc_query_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "site_url",
            "metric_date",
            "query_hash",
            name="uq_gsc_query_daily_natural",
        ),
        Index("ix_gsc_query_daily_tenant_id", "tenant_id"),
        Index(
            "ix_gsc_query_daily_tenant_site_date",
            "tenant_id",
            "site_url",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    site_url: Mapped[str] = mapped_column(String(512), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    clicks: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    impressions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    ctr: Mapped[float] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=sa.text("0")
    )
    position: Mapped[float] = mapped_column(
        Numeric(8, 2), nullable=False, server_default=sa.text("0")
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class GaMetricDaily(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily Google Analytics 4 property metrics (sessions/users/conversions).

    Aggregate, non-PHI web-traffic data pulled read-only from the GA4 Data API.
    Idempotent on ``(tenant_id, property_id, metric_date)``. Full fidelity stays
    in ``ingest.raw_event``; this is the curated projection for dashboards.
    """

    __tablename__ = "ga_metric_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "property_id", "metric_date", name="uq_ga_metric_daily_natural"
        ),
        Index("ix_ga_metric_daily_tenant_id", "tenant_id"),
        Index(
            "ix_ga_metric_daily_tenant_property_date",
            "tenant_id",
            "property_id",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    property_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    total_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    new_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    screen_page_views: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    conversions: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    # Engagement metrics (ENG-478) — additive, NULLABLE so existing rows pulled
    # before this column landed read as "not captured" (UI "—") rather than a
    # fabricated 0. Populated on the next pull.
    engaged_sessions: Mapped[int | None] = mapped_column(sa.BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))
    avg_session_duration: Mapped[float | None] = mapped_column(Numeric(12, 4))
    bounce_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))
    event_count: Mapped[int | None] = mapped_column(sa.BigInteger)
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class GaChannelDaily(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily GA4 metrics split by acquisition channel (``sessionDefaultChannelGroup``).

    The organic vs paid vs direct split for the SEO dashboard. One row per
    (property, day, channel). Idempotent on ``(tenant_id, property_id,
    metric_date, channel)``. Aggregate, non-PHI; full fidelity stays in
    ``ingest.raw_event``.
    """

    __tablename__ = "ga_channel_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "metric_date",
            "channel",
            name="uq_ga_channel_daily_natural",
        ),
        Index("ix_ga_channel_daily_tenant_id", "tenant_id"),
        Index(
            "ix_ga_channel_daily_tenant_property_date",
            "tenant_id",
            "property_id",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    property_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    channel: Mapped[str] = mapped_column(String(128), nullable=False)
    sessions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    total_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    new_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    screen_page_views: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    conversions: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )


class GaPageDaily(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Daily GA4 metrics split by page (landing page / host).

    Feeds the SEO dashboard's top-pages table. One row per (property, day,
    page_path). Idempotent on ``(tenant_id, property_id, metric_date,
    page_path)``. ``page_path`` keys the natural constraint; ``page_hash``
    (sha256 of the path) backs the unique index because page URLs can exceed
    the btree index size limit — mirrors :class:`GscQueryDaily`'s query_hash.
    The verbatim path stays in ``page_path`` (Text).
    """

    __tablename__ = "ga_page_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "metric_date",
            "page_hash",
            name="uq_ga_page_daily_natural",
        ),
        Index("ix_ga_page_daily_tenant_id", "tenant_id"),
        Index(
            "ix_ga_page_daily_tenant_property_date",
            "tenant_id",
            "property_id",
            "metric_date",
        ),
        {"schema": SCHEMA},
    )

    property_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    page_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sessions: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    total_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    new_users: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    screen_page_views: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    conversions: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=sa.text("0")
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )
