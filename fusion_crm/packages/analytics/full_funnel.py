"""Full Funnel v2 — person-anchored read model (ENG-481).

A read-only composition service that stitches the Full Funnel report from each
stage's system of truth, anchored on the global ``identity.person`` rather than
on the Salesforce lead table:

- **Leads** = distinct persons in ``ops.lead`` ∪
  ``identity.source_link(carestack/patient)`` (the same union
  ``project-manager/leads`` uses).
- **Consults (scheduled / showed / no-show / cancelled / rescheduled /
  pending)** = ``ops.consultation`` rows (CareStack truth), counted at the
  APPOINTMENT level (one count per row, NOT distinct persons), bucketed on
  ``scheduled_at``. The five status counters balance:
  ``scheduled = showed + no_show + cancelled + rescheduled + pending``.
- **Closed won (money) / revenue** = Net Collected from ``interaction.event``
  (``payment_recorded − payment_refunded − payment_reversed``) by person, on
  ``occurred_at``.

Each stage is windowed and month-bucketed on its OWN timestamp (a person can
land in different months at different stages — that is correct lag).

A single ``audience`` toggle (``marketing`` | ``all``) filters every stage:
``marketing`` keeps only persons whose lead resolves to an ad channel via the
single shared ops resolver; ``all`` is the whole universe. ``marketing ⊆ all``
holds for every stage and month because both share one person→channel map.

This service is the composition boundary the API route depends on. It owns NO
SQL — every cross-domain read goes through the owning domain's service
(``OpsService`` / ``IdentityService`` / ``InteractionService`` /
``MarketingService``), honouring the ``packages/CLAUDE.md`` import matrix. The
route stays a thin wiring layer; the per-stage aggregation reads live on the
owning domains.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from packages.core.types import TenantId
from packages.identity.service import IdentityService
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.service import OpsService

from .schemas import (
    FullFunnelV2ChannelRowOut,
    FullFunnelV2HeadlineOut,
    FullFunnelV2MonthOut,
    FullFunnelV2Out,
    FullFunnelV2WindowOut,
)

Audience = Literal["all", "marketing"]

# Fixed three-channel ladder. ``other`` collects every non-ad source plus
# CareStack-direct patients (no lead). Keep in sync with the ops resolver's
# ``_funnel_channel_label`` collapse.
_FUNNEL_CHANNELS: tuple[str, ...] = ("google", "facebook", "other")
_AD_CHANNELS: frozenset[str] = frozenset({"google", "facebook"})

# Provider → funnel channel for ad spend (mirrors the ENG-472 route map).
_PROVIDER_TO_CHANNEL: dict[str, str] = {
    "google_ads": "google",
    "meta_ads": "facebook",
    "tiktok_ads": "other",
}

# Window guards (mirror the shipped endpoint).
_DEFAULT_MONTHS = 6
_MAX_MONTHS = 24

# ENG-481 CareStack-direct dating sentinel. A CareStack-direct person with zero
# real activity (no consultation, no timeline event) falls to this instant. It
# sits before the default trailing-6-month window, so such persons drop out of
# the leads count — correct: they are a bulk-loaded patient base, not organic
# leads. Timezone-aware UTC so the half-open month spans compare cleanly.
_CARESTACK_DIRECT_SENTINEL = datetime(2025, 1, 1, tzinfo=UTC)


def _add_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _sub_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


@dataclass
class _StageCell:
    """One month×channel accumulator for the person-anchored funnel.

    Leads and closed-won stay distinct-person sets (and revenue is summed
    cash). The consultation stages are counted at the APPOINTMENT level —
    one count per ``ops.consultation`` row, NOT distinct persons — so the
    statuses balance:

        consults_scheduled = showed + no_show + cancelled + rescheduled + pending

    ``consults_scheduled`` is the total appointment rows in the cell; each raw
    ``ops.consultation.status`` maps to exactly one status counter
    (completed→showed, no_show→no_show, cancelled→cancelled,
    rescheduled→rescheduled, scheduled→pending), so the five sub-counters sum
    to ``consults_scheduled``.
    """

    leads: set[UUID] = field(default_factory=set)
    consults_scheduled: int = 0
    showed: int = 0
    no_show: int = 0
    cancelled: int = 0
    rescheduled: int = 0
    pending: int = 0
    revenue: float = 0.0
    closed_won: set[UUID] = field(default_factory=set)


class FullFunnelService:
    """Read-only composition for the Full Funnel v2 report (ENG-481)."""

    def __init__(
        self,
        *,
        ops: OpsService,
        identity: IdentityService,
        interaction: InteractionService,
        marketing: MarketingService,
    ) -> None:
        self._ops = ops
        self._identity = identity
        self._interaction = interaction
        self._marketing = marketing

    def _resolve_window(
        self, start_date: date | None, end_date: date | None
    ) -> tuple[list[tuple[str, datetime, datetime]], tuple[int, int], tuple[int, int]]:
        """Resolve the inclusive month window → per-month UTC half-open spans."""
        resolved_end = end_date or datetime.now(tz=UTC).date()
        end_month = (resolved_end.year, resolved_end.month)
        if start_date is not None:
            start_month = (start_date.year, start_date.month)
        else:
            y, m = end_month
            for _ in range(_DEFAULT_MONTHS - 1):
                y, m = _sub_month(y, m)
            start_month = (y, m)
        if start_month > end_month:
            start_month = end_month

        windows: list[tuple[str, datetime, datetime]] = []
        y, m = start_month
        while (y, m) <= end_month:
            start = datetime(y, m, 1, tzinfo=UTC)
            ny, nm = _add_month(y, m)
            windows.append((f"{y:04d}-{m:02d}", start, datetime(ny, nm, 1, tzinfo=UTC)))
            y, m = ny, nm
        if len(windows) > _MAX_MONTHS:
            windows = windows[-_MAX_MONTHS:]
            start_month = (int(windows[0][0][:4]), int(windows[0][0][5:7]))
        return windows, start_month, end_month

    async def compute(
        self,
        tenant_id: TenantId,
        *,
        audience: Audience = "all",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FullFunnelV2Out:
        windows, start_month, end_month = self._resolve_window(start_date, end_date)
        if not windows:
            return FullFunnelV2Out(
                audience=audience,
                window=FullFunnelV2WindowOut(
                    start_month=f"{start_month[0]:04d}-{start_month[1]:02d}",
                    end_month=f"{end_month[0]:04d}-{end_month[1]:02d}",
                ),
                channels=list(_FUNNEL_CHANNELS),
                headline=FullFunnelV2HeadlineOut(),
                by_month=[],
                by_channel=[],
            )

        month_keys = [w[0] for w in windows]
        span_from = windows[0][1]
        span_to = windows[-1][2]

        # One person→channel map drives both the audience filter and per-stage
        # channel attribution, so marketing ⊆ all holds by construction.
        person_channels = await self._ops.full_funnel_person_channels(tenant_id)

        def channel_of(person_uid: UUID) -> str:
            return person_channels.get(person_uid, "other")

        def in_audience(person_uid: UUID) -> bool:
            if audience == "all":
                return True
            return person_channels.get(person_uid) in _AD_CHANNELS

        # cells[(month, channel)] -> _StageCell
        cells: dict[tuple[str, str], _StageCell] = {
            (mk, ch): _StageCell() for mk in month_keys for ch in _FUNNEL_CHANNELS
        }

        def cell(month: str, person_uid: UUID) -> _StageCell | None:
            key = (month, channel_of(person_uid))
            return cells.get(key)

        # --- Leads (universe): SF leads ∪ CareStack-direct patients ---
        #
        # SF-lead persons (SF-only and SF+CareStack linked) keep their existing
        # lead-date logic: windowed + month-bucketed on the provider lead
        # created-at (``extra.sf_created_at`` ?? ``created_at``).
        lead_rows = await self._ops.full_funnel_lead_rows(
            tenant_id, created_from=span_from, created_to=span_to
        )
        for row in lead_rows:
            if not in_audience(row.person_uid):
                continue
            c = cell(row.month, row.person_uid)
            if c is not None:
                c.leads.add(row.person_uid)

        # CareStack-direct persons (a ``carestack/patient`` link AND no
        # ``ops.lead`` anywhere, any time) have NO meaningful lead date: every
        # CareStack patient was bulk-pulled in one 2026-05 batch, so
        # ``source_link.first_seen_at`` clusters them all into that month — a
        # fake spike of ~52k leads (ENG-481). Instead date each such person by
        # their earliest REAL activity, all-time:
        #
        #     funnel_entry = COALESCE(
        #         MIN(consultation.scheduled_at),
        #         MIN(interaction.event.occurred_at),
        #         2025-01-01,  # sentinel: a bulk-loaded base, not an organic lead
        #     )
        #
        # then bucket into the month of funnel_entry, counting the person as a
        # lead ONLY if funnel_entry falls inside the report window. The sentinel
        # sits outside the default trailing-6-month window, so zero-activity
        # persons correctly drop out.
        await self._add_carestack_direct_leads(
            tenant_id,
            cells=cells,
            month_keys=month_keys,
            channel_of=channel_of,
            in_audience=in_audience,
        )

        # --- Consults (CareStack truth) — APPOINTMENT-LEVEL counts ---
        #
        # One count per non-deleted ``ops.consultation`` row (NOT distinct
        # persons), so the five status sub-counters sum to ``consults_scheduled``:
        #   completed→showed, no_show→no_show, cancelled→cancelled,
        #   rescheduled→rescheduled, scheduled→pending (future) OR no_show (past).
        # ``deleted`` rows are EXCLUDED entirely (note/admin rows + deleted
        # appointments — never a real visit). A still-``scheduled`` appointment
        # whose slot has already passed (``is_past``) reads as a no-show.
        # Audience filter + per-channel attribution still apply per appointment
        # via the person's channel, so ``marketing ⊆ all`` holds.
        consult_rows = await self._ops.full_funnel_consultation_rows(
            tenant_id, scheduled_from=span_from, scheduled_to=span_to
        )
        for crow in consult_rows:
            if not in_audience(crow.person_uid):
                continue
            c = cell(crow.month, crow.person_uid)
            if c is None:
                continue
            # ENG-481 appointment classification:
            #   deleted     → SKIP entirely (excluded; not a real appointment)
            #   completed   → showed
            #   no_show     → no_show
            #   cancelled   → cancelled
            #   rescheduled → rescheduled
            #   scheduled   → no_show if the slot has already passed (is_past),
            #                 else pending (future appointment not yet held)
            # consults_scheduled is the SUM of the five buckets, i.e. every
            # non-deleted appointment, so the sum identity holds per cell.
            if crow.status == "deleted":
                continue
            if crow.status == "completed":
                c.showed += 1
            elif crow.status == "no_show":
                c.no_show += 1
            elif crow.status == "cancelled":
                c.cancelled += 1
            elif crow.status == "rescheduled":
                c.rescheduled += 1
            elif crow.status == "scheduled":
                if crow.is_past:
                    c.no_show += 1
                else:
                    c.pending += 1
            else:
                # Unknown status defends the sum identity: count it as the
                # catch-all pending bucket rather than dropping it silently.
                c.pending += 1
            c.consults_scheduled += 1

        # --- Closed won (money) / revenue (CareStack payments) ---
        money_rows = await self._interaction.collected_by_person_month(
            tenant_id, occurred_from=span_from, occurred_to=span_to
        )
        for person_uid, month, net in money_rows:
            if not in_audience(person_uid):
                continue
            c = cells.get((month, channel_of(person_uid)))
            if c is None:
                continue
            c.revenue += net
            if net > 0:
                c.closed_won.add(person_uid)

        # --- Monthly ad spend (marketing channels only) ---
        span_start_date = date(int(month_keys[0][:4]), int(month_keys[0][5:7]), 1)
        span_end_date = (span_to.date() - timedelta(days=1))
        spend_rows = await self._marketing.monthly_spend_by_provider(
            tenant_id, start_date=span_start_date, end_date=span_end_date
        )
        spend_by_month_channel: dict[tuple[str, str], float] = {}
        for point in spend_rows:
            ch = _PROVIDER_TO_CHANNEL.get(point.provider, "other")
            key = (point.month, ch)
            spend_by_month_channel[key] = spend_by_month_channel.get(key, 0.0) + point.spend

        return self._assemble(
            audience=audience,
            month_keys=month_keys,
            start_month=start_month,
            end_month=end_month,
            cells=cells,
            spend_by_month_channel=spend_by_month_channel,
        )

    async def _add_carestack_direct_leads(
        self,
        tenant_id: TenantId,
        *,
        cells: dict[tuple[str, str], _StageCell],
        month_keys: list[str],
        channel_of: Callable[[UUID], str],
        in_audience: Callable[[UUID], bool],
    ) -> None:
        """Add CareStack-direct (no-lead) persons to the leads stage (ENG-481).

        The CareStack-direct universe is the DISTINCT persons with a
        ``carestack/patient`` source link MINUS every person that has any
        ``ops.lead`` (the "no lead" exclusion — cross-domain, so it lives here
        in the composition layer, not in identity). Each surviving person is
        dated by their earliest real activity, all-time:

            funnel_entry = COALESCE(
                MIN(consultation.scheduled_at),
                MIN(interaction.event.occurred_at),
                2025-01-01 sentinel,
            )

        and counted as a lead only when ``funnel_entry`` lands inside the report
        window. CareStack-direct persons have no lead → channel ``other``, never
        marketing; ``in_audience`` already drops them under the marketing toggle.
        """
        carestack_uids = set(
            await self._identity.full_funnel_carestack_patient_person_uids(tenant_id)
        )
        if not carestack_uids:
            return
        lead_person_uids = await self._ops.full_funnel_lead_person_uids(tenant_id)
        direct_uids = [uid for uid in carestack_uids if uid not in lead_person_uids]
        if not direct_uids:
            return

        # MIN aggregates are computed over the whole table (one GROUP BY each)
        # rather than via a bound IN over the ~50k-person CareStack-direct
        # universe (past asyncpg's parameter cap). We index into them per person.
        earliest_consult = (
            await self._ops.full_funnel_earliest_consultation_at_by_person(tenant_id)
        )
        earliest_event = await self._interaction.earliest_event_at_by_person(
            tenant_id
        )

        # Map each window month → its half-open [start, next) UTC span so a
        # funnel_entry instant buckets into exactly the rendered month and any
        # entry outside the window (notably the 2025-01-01 sentinel) drops out.
        month_spans: dict[str, tuple[datetime, datetime]] = {}
        for mk in month_keys:
            y, m = int(mk[:4]), int(mk[5:7])
            ny, nm = _add_month(y, m)
            month_spans[mk] = (
                datetime(y, m, 1, tzinfo=UTC),
                datetime(ny, nm, 1, tzinfo=UTC),
            )

        for person_uid in direct_uids:
            if not in_audience(person_uid):
                continue
            entry = earliest_consult.get(person_uid)
            if entry is None:
                entry = earliest_event.get(person_uid)
            if entry is None:
                entry = _CARESTACK_DIRECT_SENTINEL
            month_key = f"{entry.year:04d}-{entry.month:02d}"
            span = month_spans.get(month_key)
            # Guard: only bucket when the entry instant actually lands inside a
            # rendered month span (handles the sentinel + any edge instants).
            if span is None or not (span[0] <= entry < span[1]):
                continue
            c = cells.get((month_key, channel_of(person_uid)))
            if c is not None:
                c.leads.add(person_uid)

    def _assemble(
        self,
        *,
        audience: Audience,
        month_keys: list[str],
        start_month: tuple[int, int],
        end_month: tuple[int, int],
        cells: dict[tuple[str, str], _StageCell],
        spend_by_month_channel: dict[tuple[str, str], float],
    ) -> FullFunnelV2Out:
        # Headline: leads / closed-won are distinct persons across the whole
        # window (a person counted once even if active in several
        # months/channels). The consult stages are APPOINTMENT counts, so they
        # aggregate by SUM (ints add — no set union, no person-dedup); summing
        # the per-cell appointment counts across all months/channels is exactly
        # the window total.
        h_leads: set[UUID] = set()
        h_sched = 0
        h_showed = 0
        h_no_show = 0
        h_cancelled = 0
        h_rescheduled = 0
        h_pending = 0
        h_closed_won: set[UUID] = set()
        h_revenue = 0.0

        by_month: list[FullFunnelV2MonthOut] = []
        by_channel: list[FullFunnelV2ChannelRowOut] = []

        for mk in month_keys:
            m_leads: set[UUID] = set()
            m_sched = 0
            m_showed = 0
            m_no_show = 0
            m_cancelled = 0
            m_rescheduled = 0
            m_pending = 0
            m_closed_won: set[UUID] = set()
            m_revenue = 0.0
            m_spend_total = 0.0
            m_any_spend = False

            for ch in _FUNNEL_CHANNELS:
                c = cells[(mk, ch)]
                spend = spend_by_month_channel.get((mk, ch))
                # Spend is never attributed to the catch-all ``other`` lane.
                if ch == "other":
                    spend = None
                if spend is not None:
                    m_any_spend = True
                    m_spend_total += spend

                by_channel.append(
                    FullFunnelV2ChannelRowOut(
                        month=mk,
                        channel=ch,
                        spend=spend,
                        leads=len(c.leads),
                        consults_scheduled=c.consults_scheduled,
                        showed=c.showed,
                        no_show=c.no_show,
                        cancelled=c.cancelled,
                        rescheduled=c.rescheduled,
                        pending=c.pending,
                        revenue=round(c.revenue, 2),
                    )
                )

                m_leads |= c.leads
                m_sched += c.consults_scheduled
                m_showed += c.showed
                m_no_show += c.no_show
                m_cancelled += c.cancelled
                m_rescheduled += c.rescheduled
                m_pending += c.pending
                m_closed_won |= c.closed_won
                m_revenue += c.revenue

            by_month.append(
                FullFunnelV2MonthOut(
                    month=mk,
                    spend=round(m_spend_total, 2) if m_any_spend else None,
                    leads=len(m_leads),
                    consults_scheduled=m_sched,
                    showed=m_showed,
                    no_show=m_no_show,
                    cancelled=m_cancelled,
                    rescheduled=m_rescheduled,
                    pending=m_pending,
                    closed_won=len(m_closed_won),
                    revenue=round(m_revenue, 2),
                )
            )

            h_leads |= m_leads
            h_sched += m_sched
            h_showed += m_showed
            h_no_show += m_no_show
            h_cancelled += m_cancelled
            h_rescheduled += m_rescheduled
            h_pending += m_pending
            h_closed_won |= m_closed_won
            h_revenue += m_revenue

        return FullFunnelV2Out(
            audience=audience,
            window=FullFunnelV2WindowOut(
                start_month=f"{start_month[0]:04d}-{start_month[1]:02d}",
                end_month=f"{end_month[0]:04d}-{end_month[1]:02d}",
            ),
            channels=list(_FUNNEL_CHANNELS),
            headline=FullFunnelV2HeadlineOut(
                leads=len(h_leads),
                consults_scheduled=h_sched,
                showed=h_showed,
                no_show=h_no_show,
                cancelled=h_cancelled,
                rescheduled=h_rescheduled,
                pending=h_pending,
                closed_won=len(h_closed_won),
                revenue=round(h_revenue, 2),
            ),
            by_month=by_month,
            by_channel=by_channel,
        )
