"""Attribution DTOs (ENG-447)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _reject_slash(slug: str) -> str:
    """Slugs are the path separator in the analytics tree key (ENG-450); a
    ``/`` inside one would break the frontend ``key.split("/")`` drill-down.
    The resolver's slugify only emits ``[a-z0-9_]``, so this only ever rejects
    a malformed manual/API slug."""
    if "/" in slug:
        raise ValueError("slug must not contain '/'")
    return slug


class SourceNodeIn(BaseModel):
    level: str = Field(..., min_length=1, max_length=16)
    slug: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=240)
    parent_id: UUID | None = None
    meta: dict[str, object] = Field(default_factory=dict)

    _validate_slug = field_validator("slug")(_reject_slash)


class SourceNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    level: str
    slug: str
    label: str
    parent_id: UUID | None
    active: bool


class LeadAttributionIn(BaseModel):
    person_uid: UUID
    sf_lead_id: str | None = Field(default=None, max_length=32)
    vendor_id: UUID | None = None
    channel_id: UUID | None = None
    campaign_id: UUID | None = None
    ad_set_id: UUID | None = None
    ad_id: UUID | None = None
    form_id: UUID | None = None
    created_by_name: str | None = Field(default=None, max_length=240)
    method: str = Field(default="auto", max_length=16)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_signal: str | None = Field(default=None, max_length=32)


class LeadAttributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    sf_lead_id: str | None
    vendor_id: UUID | None
    channel_id: UUID | None
    campaign_id: UUID | None
    ad_set_id: UUID | None
    ad_id: UUID | None
    form_id: UUID | None
    created_by_name: str | None
    method: str
    confidence: float | None
    source_signal: str | None
    resolved_at: datetime


class MappingRuleIn(BaseModel):
    priority: int = 100
    match_field: str = Field(..., min_length=1, max_length=64)
    match_op: str = Field(default="ilike", max_length=16)
    match_value: str = Field(..., min_length=1, max_length=240)
    set_level: str = Field(..., min_length=1, max_length=16)
    set_node_id: UUID
    active: bool = True


class SourceRef(BaseModel):
    """A chain-node reference for a manual override (ensured by slug)."""

    slug: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=240)

    _validate_slug = field_validator("slug")(_reject_slash)


class LeadOverrideIn(BaseModel):
    """Staff manual override of a lead's attribution chain (ENG-449).

    Any level provided is set; omitted levels are left unchanged on the existing
    row (or empty on a new one). Sets ``method=manual`` — sticky across
    auto/rule re-resolution.
    """

    vendor: SourceRef | None = None
    channel: SourceRef | None = None
    campaign: SourceRef | None = None
    ad_set: SourceRef | None = None
    ad: SourceRef | None = None
    form: SourceRef | None = None
    created_by_name: str | None = Field(default=None, max_length=240)


class MappingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    priority: int
    match_field: str
    match_op: str
    match_value: str
    set_level: str
    set_node_id: UUID
    active: bool


# --- vendor entity (ENG-570) ---


_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"  # YYYY-MM


class VendorIn(BaseModel):
    """Create a configured vendor. ``slug`` is derived from ``name`` if omitted."""

    name: str = Field(..., min_length=1, max_length=240)
    kind: str = Field(default="agency", max_length=16)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    color: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool = True
    # Monthly spend (ENG-573). flat_monthly_fee=True → monthly_fee applies every
    # month; False → amounts come from per-month VendorCost rows.
    monthly_fee: float | None = Field(default=None, ge=0)
    flat_monthly_fee: bool = True
    fee_currency: str = Field(default="USD", min_length=3, max_length=3)


class VendorUpdateIn(BaseModel):
    """Patch a vendor. Omitted fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=240)
    kind: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None
    monthly_fee: float | None = Field(default=None, ge=0)
    flat_monthly_fee: bool | None = None
    fee_currency: str | None = Field(default=None, min_length=3, max_length=3)


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    kind: str
    active: bool
    color: str | None
    notes: str | None
    monthly_fee: float | None
    flat_monthly_fee: bool
    fee_currency: str
    source_node_id: UUID | None


class VendorCostIn(BaseModel):
    """Set a vendor's fee for one month (used when the fee is not flat)."""

    period_month: str = Field(..., pattern=_MONTH_PATTERN)
    amount: float = Field(..., ge=0)
    note: str | None = Field(default=None, max_length=500)


class VendorCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    period_month: str
    amount: float
    note: str | None


# --- vendor claims + unassigned signatures (ENG-571) ---


class VendorClaimIn(BaseModel):
    """Bind matching traffic to a vendor.

    ``priority`` shares the resolver's one rule ladder with mapping rules: rules
    are applied in ascending order and the vendor is overwritten on each match,
    so a HIGHER number wins (applied last). Default 100.
    """

    match_field: str = Field(..., min_length=1, max_length=64)
    match_op: str = Field(default="eq", max_length=16)
    match_value: str = Field(..., min_length=1, max_length=240)
    priority: int = Field(default=100, ge=0)
    # Provenance: "manual" (operator) or "agent" (accepted a suggestion). ENG-574.
    origin: str = Field(default="manual", max_length=16)


class VendorClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    match_field: str
    match_op: str
    match_value: str
    priority: int
    active: bool
    origin: str


class SignatureValueOut(BaseModel):
    """One distinct traffic-signature value seen in the Unassigned bucket."""

    match_field: str
    value: str
    lead_count: int


class UnassignedSignaturesOut(BaseModel):
    """Distinct signature values behind the Unassigned (no-vendor) leads.

    ``scanned`` is how many unassigned leads were inspected; ``capped`` is True
    when the scan hit ``lead_limit`` and there may be more (no silent truncation).
    """

    items: list[SignatureValueOut]
    scanned: int
    capped: bool


class ClaimSuggestionOut(BaseModel):
    """An agent-proposed binding for one Unassigned signature (ENG-574).

    A heuristic suggester matched the signature value against the vendor's
    name/slug tokens. The operator accepts it → a claim with ``origin='agent'``.
    """

    match_field: str
    value: str
    lead_count: int
    rationale: str


class ClaimSuggestionsOut(BaseModel):
    items: list[ClaimSuggestionOut]
    scanned: int
    capped: bool


# --- analytics: funnel by attribution chain level (ENG-450, Block D) ---


class AttributionTreeNodeOut(BaseModel):
    """One node of the resolved attribution funnel tree (ENG-450).

    ``key`` is the slash-joined slug path from the root
    (``vendor`` / ``vendor/channel`` / ``vendor/channel/campaign``) — stable
    across reloads and unique among siblings, suitable for UI row keys and
    drill-down requests. Counts roll up: a parent aggregates its children.
    """

    key: str
    label: str
    level: str  # "vendor" | "channel" | "campaign"
    leads: int
    consults_scheduled: int
    consults_attended: int
    # Net Collected cash (recorded − refunded/reversed) of the persons behind
    # this node's leads. Interaction-domain math, attached by the route layer.
    collected_amount: float = 0.0
    # Vendor entity enrichment (ENG-572) — set only on vendor-level nodes.
    color: str | None = None
    # Monthly spend + cost-per-lead (ENG-573) — set on vendor-level nodes only
    # when a period is requested and the vendor has a fee for that month.
    monthly_cost: float | None = None
    cost_per_lead: float | None = None
    children: list[AttributionTreeNodeOut] = Field(default_factory=list)


class AttributionTreeOut(BaseModel):
    """Hierarchical lead→consult funnel counts sliced by the resolved chain.

    Replaces the dashboard "unknown" bucket with the resolved breakdown.
    ``needs_review`` is the count of leads the resolver could not place
    (``source_signal='needs_review'``) — the explicit gap to drive toward ~0.
    """

    total_leads: int
    needs_review: int
    consults_scheduled: int
    consults_attended: int
    collected_amount: float = 0.0
    nodes: list[AttributionTreeNodeOut]


class AttributionLeadItemOut(BaseModel):
    """One drill-down lead row behind an attribution funnel node (ENG-450).

    Person identity (``display_name``/``email``/``phone``) comes from identity
    — the staff-frontend PHI policy of 2026-06-01 permits it (same surface the
    PM Leads page renders).
    """

    person_uid: UUID
    sf_lead_id: str | None = None
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    vendor: str | None = None
    channel: str | None = None
    campaign: str | None = None
    created_by_name: str | None = None
    method: str
    source_signal: str | None = None
    confidence: float | None = None
    collected_amount: float = 0.0
    resolved_at: datetime


class AttributionLeadListOut(BaseModel):
    """Paginated drill-down list for one attribution funnel node."""

    total: int
    items: list[AttributionLeadItemOut]
