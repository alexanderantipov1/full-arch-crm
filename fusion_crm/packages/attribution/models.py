"""Attribution models (schema ``attribution``) — ENG-447.

Three tables:

* ``source_node`` — controlled-vocabulary node in the distribution chain.
  The chain is the ``parent_id`` ladder (ad → ad_set → campaign → channel →
  vendor). One row per ``(tenant_id, level, slug)``.
* ``lead_attribution`` — the resolved chain for one lead (one row per
  ``(tenant_id, person_uid)``). Denormalized levels so a funnel GROUP BY any
  level is a single join.
* ``mapping_rule`` — editable ``pattern → chain node`` rules the resolver
  applies (e.g. ``utm_campaign ILIKE 'Dima%' → vendor=Dima``). This is how the
  chain learns the VENDOR, which is not present in the source data.

All tables are tenant-scoped (leads are per tenant). ``person_uid`` is the
canonical ``identity.person.id`` reference (plain UUID column, no Python
import). Attribution is DERIVED data — re-buildable from raw evidence by the
resolver — so it carries no PHI.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "attribution"

# The chain levels, outermost → innermost. ``agent`` is a parallel axis (the
# staff member who manually created a lead), not part of the parent chain.
LEVELS = ("vendor", "channel", "campaign", "ad_set", "ad", "form")

# How a per-lead attribution was produced.
METHODS = ("auto", "rule", "manual")

# A vendor is WHO manages the traffic: an external agency or our own in-house
# marketing team. The in-house team is a vendor too — bound explicitly, never a
# catch-all (ENG-570). Unbound traffic stays Unassigned (NULL), not a vendor.
VENDOR_KINDS = ("agency", "in_house")


class SourceNode(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One node in the attribution distribution chain (ENG-447)."""

    __tablename__ = "source_node"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "level", "slug", name="uq_source_node_tenant_level_slug"
        ),
        Index("ix_source_node_tenant_id", "tenant_id"),
        Index("ix_source_node_level", "tenant_id", "level"),
        Index("ix_source_node_parent", "parent_id"),
        {"schema": SCHEMA},
    )

    level: Mapped[str] = mapped_column(String(16), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.source_node.id", ondelete="SET NULL"),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


def _node_fk() -> Mapped[uuid.UUID | None]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.source_node.id", ondelete="SET NULL"),
        nullable=True,
    )


class LeadAttribution(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Resolved attribution chain for one lead/person (ENG-447)."""

    __tablename__ = "lead_attribution"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "person_uid", name="uq_lead_attribution_tenant_person"
        ),
        Index("ix_lead_attribution_tenant_id", "tenant_id"),
        Index("ix_lead_attribution_vendor", "tenant_id", "vendor_id"),
        Index("ix_lead_attribution_channel", "tenant_id", "channel_id"),
        Index("ix_lead_attribution_method", "tenant_id", "method"),
        {"schema": SCHEMA},
    )

    # Canonical person reference (identity.person.id) — plain UUID, no import.
    person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    sf_lead_id: Mapped[str | None] = mapped_column(String(32))
    vendor_id: Mapped[uuid.UUID | None] = _node_fk()
    channel_id: Mapped[uuid.UUID | None] = _node_fk()
    campaign_id: Mapped[uuid.UUID | None] = _node_fk()
    ad_set_id: Mapped[uuid.UUID | None] = _node_fk()
    ad_id: Mapped[uuid.UUID | None] = _node_fk()
    form_id: Mapped[uuid.UUID | None] = _node_fk()
    # Staff member who manually created the lead (CreatedBy.Name). Parallel
    # axis, stored verbatim — operational metadata, not PHI.
    created_by_name: Mapped[str | None] = mapped_column(String(240))
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    # Which waterfall branch produced this (digital / phone / campaign / manual /
    # reactivation / needs_review).
    source_signal: Mapped[str | None] = mapped_column(String(32))
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MappingRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Editable ``pattern → chain node`` rule applied by the resolver (ENG-449)."""

    __tablename__ = "mapping_rule"
    __table_args__ = (
        Index("ix_mapping_rule_tenant_id", "tenant_id"),
        Index("ix_mapping_rule_active", "tenant_id", "active", "priority"),
        {"schema": SCHEMA},
    )

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # Captured field the rule matches on, e.g. "utm_campaign", "hubspot_lead_source".
    match_field: Mapped[str] = mapped_column(String(64), nullable=False)
    # eq | ilike | prefix
    match_op: Mapped[str] = mapped_column(String(16), nullable=False, default="ilike")
    match_value: Mapped[str] = mapped_column(String(240), nullable=False)
    # The chain level + node this rule assigns.
    set_level: Mapped[str] = mapped_column(String(16), nullable=False)
    set_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.source_node.id", ondelete="CASCADE"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A configured traffic vendor — the operator-facing "who" (ENG-570).

    The vendor-level ``source_node`` stays the resolver's chain vocabulary; this
    entity is the operator record (name, kind, color, notes, and money later)
    linked 1:1 to that node via ``source_node_id``. ``slug`` mirrors the node
    slug so the resolver can ensure the entity by slug as it learns vendors.

    ``lead_attribution.vendor_id`` keeps pointing at ``source_node`` in Block A
    to avoid touching the proven funnel tree / fact builder; it is repointed to
    this table in Block C (ENG-572), when the tree is re-rooted on vendors.
    """

    __tablename__ = "vendor"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "slug", name="uq_vendor_tenant_slug"),
        sa.UniqueConstraint(
            "tenant_id", "source_node_id", name="uq_vendor_tenant_source_node"
        ),
        Index("ix_vendor_tenant_id", "tenant_id"),
        Index("ix_vendor_active", "tenant_id", "active"),
        {"schema": SCHEMA},
    )

    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="agency")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(String(2000))
    # Monthly spend (ENG-573). Two modes:
    # * flat_monthly_fee=True  → ``monthly_fee`` applies to EVERY month (the
    #   common case: a fixed retainer), no per-month rows needed;
    # * flat_monthly_fee=False → the amount varies, taken per-month from
    #   ``vendor_cost`` rows instead. Percentages may arrive later as a separate
    #   mode without reworking this.
    monthly_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    flat_monthly_fee: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.true(), default=True
    )
    fee_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD", default="USD"
    )
    # 1:1 link to the vendor-level source_node this entity owns; NULL until the
    # resolver/rules first produce that vendor node from traffic.
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.source_node.id", ondelete="SET NULL"),
        nullable=True,
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


class VendorCost(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A vendor's fee for one specific month (ENG-573).

    Only used when the vendor's fee is NOT flat (it varies month to month). When
    ``vendor.flat_monthly_fee`` is true, ``vendor.monthly_fee`` applies to every
    month and there are no rows here. ``period_month`` is ``'YYYY-MM'``; amount
    is in the vendor's ``fee_currency``.
    """

    __tablename__ = "vendor_cost"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "period_month",
            name="uq_vendor_cost_tenant_vendor_month",
        ),
        Index("ix_vendor_cost_vendor", "tenant_id", "vendor_id"),
        {"schema": SCHEMA},
    )

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.vendor.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))


# How a vendor_claim was produced.
CLAIM_ORIGINS = ("manual", "agent")


class VendorClaim(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A rule that binds matching traffic to a vendor (ENG-571).

    A ``mapping_rule`` specialised to the vendor level and tied to a configured
    ``vendor`` entity instead of a raw ``source_node``: "traffic whose
    ``match_field`` ``match_op`` ``match_value`` belongs to this vendor". The
    resolver loads active claims as vendor-level rules, so a lead matching a
    claim resolves to that vendor. ``origin`` records whether the operator made
    it (``manual``) or accepted an agent suggestion (``agent``).
    """

    __tablename__ = "vendor_claim"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "match_field",
            "match_op",
            "match_value",
            name="uq_vendor_claim_signature",
        ),
        Index("ix_vendor_claim_tenant_active", "tenant_id", "active", "priority"),
        Index("ix_vendor_claim_vendor", "tenant_id", "vendor_id"),
        {"schema": SCHEMA},
    )

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.vendor.id", ondelete="CASCADE"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # Captured signal the claim matches on, e.g. "utm_source", "utm_campaign".
    match_field: Mapped[str] = mapped_column(String(64), nullable=False)
    match_op: Mapped[str] = mapped_column(String(16), nullable=False, default="eq")
    match_value: Mapped[str] = mapped_column(String(240), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
