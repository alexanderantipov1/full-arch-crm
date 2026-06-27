"""Interaction repository — data access only, NO business logic.

Repositories take an ``AsyncSession`` and return ORM entities. They do not
commit (that is the unit-of-work caller's responsibility).

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Date,
    Numeric,
    Select,
    any_,
    cast,
    func,
    literal,
    or_,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import ARRAY, aggregate_order_by
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import Event, EventResponsibility

# Clinic-local day boundary for the PM Payments same-day grouping (ENG-410).
# CareStack splits one real-world payment into per-invoice legs minutes
# apart; "the same payment" means the same person on the same CLINIC day,
# not the same UTC day (an evening payment would otherwise split across
# two groups). Single-region clinic today; a tenant-level timezone setting
# replaces this constant when a second region onboards.
_CLINIC_TZ = "America/Los_Angeles"


class InteractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_event(self, event: Event) -> Event:
        self._session.add(event)
        await self._session.flush()
        return event

    async def add_responsibilities(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        assignments: list[tuple[UUID, str]],
    ) -> list[EventResponsibility]:
        """Write ``event_responsibility`` rows for an event in one flush.

        Idempotent: callers dedupe ``(actor_id, role)`` pairs upstream so
        the composite PK never races itself within a single call. Repeat
        invocations across UoWs are guarded by the PK at the DB level —
        on collision SQLAlchemy raises IntegrityError, which the service
        layer translates into the backfill's "already present" branch.
        """
        rows = [
            EventResponsibility(
                tenant_id=tenant_id,
                event_id=event_id,
                actor_id=actor_id,
                role=role,
            )
            for actor_id, role in assignments
        ]
        for row in rows:
            self._session.add(row)
        if rows:
            await self._session.flush()
        return rows

    async def find_existing_responsibility(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        actor_id: UUID,
        role: str,
    ) -> EventResponsibility | None:
        """Return the single ``event_responsibility`` row, if any.

        Used by the backfill script to skip already-written assignments
        instead of relying on a PK IntegrityError. Tenant-scoped per
        ADR-0003 even though ``event_id`` is globally unique.
        """
        stmt = (
            for_tenant(select(EventResponsibility), tenant_id, EventResponsibility)
            .where(EventResponsibility.event_id == event_id)
            .where(EventResponsibility.actor_id == actor_id)
            .where(EventResponsibility.role == role)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_responsibilities_for_event(
        self, tenant_id: TenantId, event_id: UUID
    ) -> list[EventResponsibility]:
        """Return every ``event_responsibility`` row for an event.

        Tenant-scoped via :func:`for_tenant` to satisfy the cross-tenant
        isolation safety net even though ``event_id`` is unique — keeps
        the structural contract uniform across responsibility readers.
        """
        stmt = (
            for_tenant(select(EventResponsibility), tenant_id, EventResponsibility)
            .where(EventResponsibility.event_id == event_id)
            .order_by(EventResponsibility.role.asc(), EventResponsibility.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_events_missing_responsibility(
        self,
        tenant_id: TenantId,
        *,
        limit: int,
        after_occurred_at: datetime | None = None,
        kinds: tuple[str, ...] | None = None,
        expected_roles: tuple[str, ...] | None = None,
    ) -> list[Event]:
        """Backfill helper: events missing one or more responsibility rows.

        When ``expected_roles`` is ``None`` (the legacy contract), return
        events with ZERO ``event_responsibility`` rows.

        When ``expected_roles`` is provided, return events where at least
        one of those roles has no row — so a partially-seeded event with
        ``operational`` written but ``clinical`` missing is still
        selected. The resolver's `set_responsibilities_idempotent` then
        fills the gap without re-writing the existing row.

        Ordered ascending by ``occurred_at`` so the backfill makes
        deterministic forward progress and can resume from the last
        ``occurred_at`` watermark across runs.
        """
        stmt = for_tenant(select(Event), tenant_id, Event)

        if expected_roles:
            # Event is "missing" if for SOME role in expected_roles there
            # is no event_responsibility row of that role. OR over the
            # per-role NOT EXISTS subqueries — the join-table PK index
            # (event_id, actor_id, role) and the (event_id, role) index
            # cover each subquery, keeping cost bounded.
            per_role_missing = [
                ~(
                    select(EventResponsibility.event_id)
                    .where(EventResponsibility.event_id == Event.id)
                    .where(EventResponsibility.role == role)
                    .exists()
                )
                for role in expected_roles
            ]
            stmt = stmt.where(or_(*per_role_missing))
        else:
            # NOT EXISTS keeps the query selective even on large tables —
            # the join-table PK index on (event_id, actor_id, role) covers
            # the subquery scan.
            subq = (
                select(EventResponsibility.event_id)
                .where(EventResponsibility.event_id == Event.id)
                .exists()
            )
            stmt = stmt.where(~subq)

        stmt = stmt.order_by(Event.occurred_at.asc(), Event.id.asc()).limit(limit)
        if after_occurred_at is not None:
            stmt = stmt.where(Event.occurred_at > after_occurred_at)
        if kinds:
            stmt = stmt.where(Event.kind.in_(kinds))
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_event_by_source(
        self,
        tenant_id: TenantId,
        source_provider: str,
        source_event_id: UUID,
    ) -> Event | None:
        """Look up an event by its provider + raw-ingest event id.

        Used to recover from the partial-UNIQUE collision path: when a
        replay tries to create a duplicate, we fetch the existing row and
        return it instead of raising.
        """
        stmt = (
            for_tenant(select(Event), tenant_id, Event)
            .where(Event.source_provider == source_provider)
            .where(Event.source_event_id == source_event_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_provider_event_by_external_id(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_kind: str,
        source_external_id: str,
        kind: str,
    ) -> Event | None:
        """Look up a provider event by stable external id and kind.

        Used by pull workers whose raw capture row changes on each re-pull,
        while the provider object id stays stable.
        """
        stmt = (
            for_tenant(select(Event), tenant_id, Event)
            .where(Event.source_provider == source_provider)
            .where(Event.source_kind == source_kind)
            .where(Event.source_external_id == source_external_id)
            .where(Event.kind == kind)
            .order_by(Event.created_at.asc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_provider_events_by_external_id(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_kind: str,
        source_external_id: str,
        kind: str,
    ) -> list[Event]:
        """Return provider events by stable external id and kind."""
        stmt = (
            for_tenant(select(Event), tenant_id, Event)
            .where(Event.source_provider == source_provider)
            .where(Event.source_kind == source_kind)
            .where(Event.source_external_id == source_external_id)
            .where(Event.kind == kind)
            .order_by(Event.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_person(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Event]:
        """Return the timeline for a person, newest-first.

        Cursor pagination on ``occurred_at`` matches the
        ``ix_event_person_occurred`` composite index.
        """
        stmt = (
            for_tenant(select(Event), tenant_id, Event)
            .where(Event.person_uid == person_uid)
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(Event.occurred_at < before)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_for_person(self, tenant_id: TenantId, person_uid: UUID) -> int:
        """Return the total event count for a person in a tenant."""
        stmt = for_tenant(select(func.count()).select_from(Event), tenant_id, Event).where(
            Event.person_uid == person_uid
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def max_event_occurred_at(
        self, tenant_id: TenantId, kind: str
    ) -> datetime | None:
        """Return ``max(Event.occurred_at)`` for a tenant scoped to one ``kind``.

        Used by ``/health/ingest`` payment-freshness (ENG-327): the worker
        emits ``payment_recorded`` events as CareStack accounting
        transactions land, so the timestamp of the latest one is the
        canonical "last cash collected" data freshness signal. Returns
        ``None`` when the tenant has zero events of ``kind`` — the route
        translates that into ``status="unknown"`` rather than ``stale``.
        Tenant-scoped via :func:`for_tenant`; the aggregate filter mirrors
        the pattern used in
        :meth:`get_treatment_payment_aggregate` (``func.max(...).filter(...)``).
        """
        stmt = for_tenant(
            select(func.max(Event.occurred_at)).select_from(Event),
            tenant_id,
            Event,
        ).where(Event.kind == kind)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def count_events_by_kind(
        self,
        tenant_id: TenantId,
        kinds: list[str],
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> dict[str, int]:
        """Return ``{kind: count}`` for ``kinds`` in an optional window.

        Tenant-scoped via :func:`for_tenant`; ``[occurred_from, occurred_to)``
        is a half-open window when both bounds are supplied. Kinds with zero
        rows are absent from the result — the caller decides how to render a
        missing kind (the calls dashboard renders ``0`` only because the
        window genuinely had no calls, never as a fabricated source value).
        """
        if not kinds:
            return {}
        stmt = (
            for_tenant(
                select(Event.kind, func.count()).select_from(Event),
                tenant_id,
                Event,
            )
            .where(Event.kind.in_(kinds))
            .group_by(Event.kind)
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        rows = (await self._session.execute(stmt)).all()
        return {str(kind): int(count) for kind, count in rows}

    async def call_volume_aggregate(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> dict[str, int | float]:
        """Aggregate ``call_logged`` direction + duration over a window.

        Reads the PHI-free ``payload`` keys the call lane writes
        (``direction`` ∈ {inbound, outbound}, ``call_duration_seconds`` int).
        Returns inbound / outbound / unknown-direction counts, the count of
        calls with a non-zero duration, and the summed talk-time seconds (the
        route derives the average so a zero-call window yields ``None`` rather
        than a divide-by-zero). Tenant-scoped; ``[from, to)`` half-open window.

        Disposition (connected / voicemail / missed), agent identity, QA,
        recordings, transcripts and sentiment are NOT aggregated here — those
        are the Phase-3 comms-ingest fields the dashboard marks pending.
        """
        direction = Event.payload["direction"].astext
        duration = cast(Event.payload["call_duration_seconds"].astext, Numeric)
        stmt = for_tenant(
            select(
                func.count().filter(direction == "inbound").label("inbound"),
                func.count().filter(direction == "outbound").label("outbound"),
                func.count()
                .filter(or_(direction.is_(None), direction.notin_(("inbound", "outbound"))))
                .label("unknown_direction"),
                func.count().filter(duration > 0).label("with_duration"),
                func.coalesce(func.sum(func.greatest(duration, 0)), 0).label(
                    "total_duration_seconds"
                ),
            ).select_from(Event),
            tenant_id,
            Event,
        ).where(Event.kind == "call_logged")
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        row = (await self._session.execute(stmt)).one()
        return {
            "inbound": int(row.inbound),
            "outbound": int(row.outbound),
            "unknown_direction": int(row.unknown_direction),
            "with_duration": int(row.with_duration),
            "total_duration_seconds": int(row.total_duration_seconds or 0),
        }

    def _payment_events_dashboard_filter(
        self,
        base: Select[Any],
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        source_provider: str | None,
        location_id: UUID | None,
        query: str | None,
        include_applied: bool,
        person_uids: list[UUID] | None = None,
    ) -> Select[Any]:
        """Apply the shared PM Payments WHERE clause to ``base``.

        Both :meth:`list_payment_events_for_dashboard` and
        :meth:`count_payment_events_for_dashboard` route through this so the
        page rows and the total count can never drift. ``include_applied``
        controls whether the ``payment_applied`` allocation leg is in scope:
        excluded by default (ENG-301) so a page is real cash movements, not
        the ~9:1 allocation noise that otherwise crowds out every recorded
        payment past the newest day.

        ``person_uids`` (ENG-408 lead-source resource filter) restricts rows
        to the given persons. The caller (route layer) resolves a lead-source
        node to its persons on the ops side and passes plain ids here — the
        interaction domain stays lead-agnostic. Bound as ONE PostgreSQL
        array parameter (``= ANY(:ids)``), not an expanding ``IN`` list: a
        channel node can hold tens of thousands of persons and an IN list
        that size would blow the asyncpg parameter limit. An empty list is a
        legitimate "node has no persons" filter and matches nothing.
        """
        kinds: tuple[str, ...] = (
            "payment_recorded",
            "payment_refunded",
            "payment_reversed",
        )
        if include_applied:
            # ENG-283: the allocation leg of CareStack's double-entry ledger.
            # Surfaced only when the PM explicitly opts in via "Show applied".
            # Never contributes to Collected — that math lives in
            # get_treatment_payment_aggregate.
            kinds = (*kinds, "payment_applied")
        stmt = base.where(Event.kind.in_(kinds)).where(
            Event.data_class == "billing"
        )
        if person_uids is not None:
            stmt = stmt.where(
                Event.person_uid
                == any_(cast(literal(person_uids), ARRAY(PG_UUID(as_uuid=True))))
            )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if source_provider is not None:
            stmt = stmt.where(Event.source_provider == source_provider)
        if location_id is not None:
            stmt = stmt.where(
                Event.payload["location_id"].astext == str(location_id)
            )
        if query is not None:
            needle = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Event.summary.ilike(needle),
                    Event.source_external_id.ilike(needle),
                )
            )
        return stmt

    async def list_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """Return one page of payment events for the PM Payments dashboard.

        Newest-first, windowed by the supplied filters, sliced by
        ``limit``/``offset``. ``include_applied=False`` (the default) drops
        the ``payment_applied`` allocation leg so the page shows real cash
        movements (ENG-301). ``location_id`` matches
        ``Event.payload['location_id']`` exactly (events without a payload
        location are excluded when this filter is set, matching the dashboard
        treatment/payment aggregate semantics).

        The repository never reads or returns raw provider payloads; the
        caller surfaces only the structured, no-PII ``Event.payload`` fields
        (``amount``, ``transaction_type``, ``location_id``).
        """
        stmt = self._payment_events_dashboard_filter(
            select(Event),
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=include_applied,
            person_uids=person_uids,
        )
        stmt = for_tenant(stmt, tenant_id, Event)
        stmt = stmt.order_by(Event.occurred_at.desc()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())

    async def summarize_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        person_uids: list[UUID] | None = None,
    ) -> dict[str, object]:
        """Window-wide payment totals for the PM Payments summary bar (ENG-302).

        Shares :meth:`_payment_events_dashboard_filter` (``include_applied``
        is irrelevant here — the aggregate selects per kind) so the summary
        honours exactly the same window/provider/location/query as the row
        list. Returns:

        - ``collected_total`` = Σ ``payment_recorded`` −
          Σ(``payment_refunded`` + ``payment_reversed``) — net cash, the same
          formula as :meth:`get_treatment_payment_aggregate`.
        - ``payment_count`` = number of ``payment_recorded`` rows.
        - ``patient_count`` = distinct ``person_uid`` over ``payment_recorded``.
        """
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"), 0
        )
        returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        base = select(
            (recorded - returned).label("collected_total"),
            func.count()
            .filter(Event.kind == "payment_recorded")
            .label("payment_count"),
            func.count(func.distinct(Event.person_uid))
            .filter(Event.kind == "payment_recorded")
            .label("patient_count"),
        ).select_from(Event)
        stmt = self._payment_events_dashboard_filter(
            base,
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=False,
            person_uids=person_uids,
        )
        stmt = for_tenant(stmt, tenant_id, Event)
        row = (await self._session.execute(stmt)).one()
        return {
            "collected_total": row.collected_total,
            "payment_count": row.payment_count,
            "patient_count": row.patient_count,
        }

    async def count_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
    ) -> int:
        """Count payment events matching the PM Payments filters (window-wide).

        Shares :meth:`_payment_events_dashboard_filter` with the list query so
        the total can never disagree with the rows. Used to drive honest
        pagination (``total`` / ``has_next``) on the PM Payments page.
        """
        stmt = self._payment_events_dashboard_filter(
            select(func.count()).select_from(Event),
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=include_applied,
            person_uids=person_uids,
        )
        stmt = for_tenant(stmt, tenant_id, Event)
        return int((await self._session.execute(stmt)).scalar_one())

    @staticmethod
    def _payment_local_day():
        """Clinic-local calendar day of a payment event (ENG-410)."""
        return cast(func.timezone(_CLINIC_TZ, Event.occurred_at), Date)

    async def list_payment_event_groups_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """One page of same-day payment groups for the PM Payments page (ENG-410).

        CareStack splits one real-world payment into per-invoice legs; the
        dashboard groups them by ``(person_uid, kind, clinic-local day)`` —
        kinds never merge, so a same-day refund stays its own row. Groups
        order newest-first by their latest leg. Each returned dict carries
        the aggregate (``total_amount``, ``leg_count``, ``last_occurred_at``)
        plus the underlying ``legs`` (ORM rows, newest-first) fetched with
        the SAME filter so a location/search-scoped page never shows legs
        the filter excluded.
        """
        local_day = self._payment_local_day()
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        base = (
            select(
                Event.person_uid,
                Event.kind,
                local_day.label("local_day"),
                func.coalesce(func.sum(amount), 0).label("total_amount"),
                func.count().label("leg_count"),
                func.max(Event.occurred_at).label("last_occurred_at"),
            )
            .select_from(Event)
            .group_by(Event.person_uid, Event.kind, local_day)
        )
        stmt = self._payment_events_dashboard_filter(
            base,
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=include_applied,
            person_uids=person_uids,
        )
        stmt = for_tenant(stmt, tenant_id, Event)
        stmt = (
            stmt.order_by(func.max(Event.occurred_at).desc())
            .limit(limit)
            .offset(offset)
        )
        group_rows = (await self._session.execute(stmt)).all()
        if not group_rows:
            return []

        keys = [(r.person_uid, r.kind, r.local_day) for r in group_rows]
        legs_stmt = self._payment_events_dashboard_filter(
            select(Event),
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=include_applied,
            person_uids=person_uids,
        ).where(tuple_(Event.person_uid, Event.kind, local_day).in_(keys))
        legs_stmt = for_tenant(legs_stmt, tenant_id, Event)
        legs_stmt = legs_stmt.order_by(Event.occurred_at.desc(), Event.id.desc())
        legs = (await self._session.execute(legs_stmt)).scalars().all()

        # Recompute the clinic-local day in Python to bucket the fetched
        # legs under their SQL group key (same tz rule as the SQL above).
        tz = ZoneInfo(_CLINIC_TZ)
        legs_by_key: dict[tuple[UUID, str, date], list[Event]] = {}
        for event in legs:
            local = event.occurred_at.astimezone(tz).date()
            legs_by_key.setdefault((event.person_uid, event.kind, local), []).append(
                event
            )

        return [
            {
                "person_uid": r.person_uid,
                "kind": r.kind,
                "local_day": r.local_day,
                "total_amount": r.total_amount,
                "leg_count": int(r.leg_count),
                "last_occurred_at": r.last_occurred_at,
                "legs": legs_by_key.get((r.person_uid, r.kind, r.local_day), []),
            }
            for r in group_rows
        ]

    async def count_payment_event_groups_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
    ) -> int:
        """Window-wide group count driving grouped pagination (ENG-410)."""
        local_day = self._payment_local_day()
        inner = (
            select(Event.person_uid, Event.kind, local_day.label("local_day"))
            .select_from(Event)
            .group_by(Event.person_uid, Event.kind, local_day)
        )
        inner = self._payment_events_dashboard_filter(
            inner,
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=query,
            include_applied=include_applied,
            person_uids=person_uids,
        )
        inner = for_tenant(inner, tenant_id, Event)
        stmt = select(func.count()).select_from(inner.subquery())
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_responsibilities_for_events(
        self, tenant_id: TenantId, event_ids: list[UUID]
    ) -> list[EventResponsibility]:
        """Return ``event_responsibility`` rows for a batch of events.

        ENG-418: powers the per-event responsible-actor strip on the
        person chain UI in one round-trip. Tenant-scoped to keep cross-
        tenant rows out even though `event_id` is unique.
        """
        if not event_ids:
            return []
        stmt = (
            for_tenant(select(EventResponsibility), tenant_id, EventResponsibility)
            .where(EventResponsibility.event_id.in_(event_ids))
            .order_by(
                EventResponsibility.event_id.asc(),
                EventResponsibility.role.asc(),
                EventResponsibility.created_at.asc(),
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # --- Funnel analytics (ENG-419) ----------------------------------

    # Maps every funnel-relevant `event.kind` to the funnel stage it
    # advances the person to. A person's "highest reached stage" is the
    # max(stage_rank(kind)) across their event history; "drop-off" is
    # that max when no strictly-higher-rank event exists.
    _FUNNEL_KIND_TO_STAGE = {
        "lead_created": "lead_new",
        "lead_updated": "lead_new",
        "call_logged": "lead_contacted",
        "call_reference_found": "lead_contacted",
        "task_created": "lead_contacted",
        "task_completed": "lead_contacted",
        "consultation_scheduled": "consult_scheduled",
        "consultation_created": "consult_scheduled",
        "consultation_rescheduled": "consult_scheduled",
        "consultation_cancelled": "consult_scheduled",
        "consultation_no_show": "consult_no_show",
        "consultation_completed": "consult_completed",
        "opportunity_created": "opportunity_open",
        "opportunity_won": "opportunity_won",
        "opportunity_lost": "opportunity_lost",
        # Treatment / payment events keep the person at "won" — the
        # downstream stage only advances when the SF Opportunity does.
        "treatment_proposed": "opportunity_won",
        "treatment_completed": "opportunity_won",
        "invoice_created": "opportunity_won",
        "payment_recorded": "opportunity_won",
        "payment_applied": "opportunity_won",
        "payment_refunded": "opportunity_won",
        "payment_reversed": "opportunity_won",
    }

    _FUNNEL_STAGE_RANK = {
        "lead_new": 1,
        "lead_contacted": 2,
        "consult_scheduled": 3,
        "consult_no_show": 4,
        "consult_completed": 5,
        "opportunity_open": 6,
        "opportunity_won": 7,
        "opportunity_lost": 7,
    }

    def _funnel_stage_case(self) -> Any:
        """Build a SQL CASE that maps ``Event.kind`` to the funnel stage."""
        from sqlalchemy import case, literal

        whens = [
            (Event.kind == kind, literal(stage))
            for kind, stage in self._FUNNEL_KIND_TO_STAGE.items()
        ]
        return case(*whens, else_=None)

    def _funnel_event_filters(
        self,
        *,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        source_provider: str | None,
        location_id: UUID | None,
    ):
        """Shared per-event filters for funnel aggregations.

        Returns a list of SQLAlchemy clauses callers AND into their
        query. Tenant scoping is applied separately by the caller via
        :func:`for_tenant`.
        """
        clauses: list[Any] = [
            Event.kind.in_(tuple(self._FUNNEL_KIND_TO_STAGE.keys()))
        ]
        if occurred_from is not None:
            clauses.append(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            clauses.append(Event.occurred_at < occurred_to)
        if source_provider is not None:
            clauses.append(Event.source_provider == source_provider)
        if location_id is not None:
            clauses.append(
                Event.payload["location_id"].astext == str(location_id)
            )
        return clauses

    async def funnel_aggregate_by_actor(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """``(stage, role, actor_id)`` × (event_count, distinct persons).

        Joins ``event`` to ``event_responsibility`` so every actor on the
        event contributes one row. Excludes events that never received a
        responsibility row (legacy pre-W2 rows surface in the no-actor
        rollup query :meth:`funnel_aggregate_totals`).
        """
        stage_case = self._funnel_stage_case()
        stmt = (
            select(
                stage_case.label("stage"),
                EventResponsibility.role.label("role"),
                EventResponsibility.actor_id.label("actor_id"),
                func.count().label("event_count"),
                func.count(func.distinct(Event.person_uid)).label("person_count"),
            )
            .select_from(Event)
            .join(EventResponsibility, EventResponsibility.event_id == Event.id)
            .where(*self._funnel_event_filters(
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                source_provider=source_provider,
                location_id=location_id,
            ))
            .where(stage_case.is_not(None))
            .group_by(
                stage_case,
                EventResponsibility.role,
                EventResponsibility.actor_id,
            )
        )
        if role is not None:
            stmt = stmt.where(EventResponsibility.role == role)
        stmt = for_tenant(stmt, tenant_id, Event)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "stage": row.stage,
                "role": row.role,
                "actor_id": row.actor_id,
                "event_count": int(row.event_count),
                "person_count": int(row.person_count),
            }
            for row in rows
        ]

    async def funnel_aggregate_totals(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, dict[str, int]]:
        """Per-stage totals (across all actors). ``{stage: {events, persons}}``."""
        stage_case = self._funnel_stage_case()
        stmt = (
            select(
                stage_case.label("stage"),
                func.count().label("event_count"),
                func.count(func.distinct(Event.person_uid)).label("person_count"),
            )
            .select_from(Event)
            .where(*self._funnel_event_filters(
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                source_provider=source_provider,
                location_id=location_id,
            ))
            .where(stage_case.is_not(None))
            .group_by(stage_case)
        )
        stmt = for_tenant(stmt, tenant_id, Event)
        rows = (await self._session.execute(stmt)).all()
        return {
            str(row.stage): {
                "event_count": int(row.event_count),
                "person_count": int(row.person_count),
            }
            for row in rows
            if row.stage is not None
        }

    async def funnel_dropoff_by_person(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Per-person "highest reached stage" + their latest operational actor.

        Returns one row per ``person_uid`` carrying ``{person_uid, stage,
        operational_actor_id}``. The stage is the max-rank funnel stage
        the person ever reached within the filtered window;
        ``operational_actor_id`` is the actor on the latest funnel event
        of that person with role=operational (None when no operational
        responsibility row was ever written for them).

        The caller composes this with ``ops.Opportunity.amount`` and
        the PM Payments aggregate to attach the $ basis per stage (see
        decision-log D-W3-3).
        """
        stage_case = self._funnel_stage_case()
        stage_rank_case = self._funnel_stage_rank_case()
        # Inner: per-person max stage rank
        per_person_rank = (
            select(
                Event.person_uid.label("person_uid"),
                func.max(stage_rank_case).label("max_rank"),
            )
            .select_from(Event)
            .where(*self._funnel_event_filters(
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                source_provider=source_provider,
                location_id=location_id,
            ))
            .where(stage_case.is_not(None))
            .group_by(Event.person_uid)
        )
        per_person_rank = for_tenant(per_person_rank, tenant_id, Event)
        per_person_rank_sq = per_person_rank.subquery("per_person_rank")

        # Outer: per-person max-rank events, with a window ROW_NUMBER so
        # we can keep only the latest event at that rank.
        # ENG-418 fix: when one event has >1 operational responsibility
        # row (e.g. backfill seeded an extra owner), the LEFT JOIN
        # produces duplicate rows that share (occurred_at, event_id);
        # add EventResponsibility.actor_id as a deterministic tie-breaker
        # so the same actor is picked across re-runs and machines. NULL
        # actor_id (LEFT OUTER → no operational row) sorts last.
        rn_col = func.row_number().over(
            partition_by=Event.person_uid,
            order_by=(
                Event.occurred_at.desc(),
                Event.id.desc(),
                EventResponsibility.actor_id.asc().nulls_last(),
            ),
        )
        latest_event_per_person = (
            select(
                Event.person_uid.label("person_uid"),
                stage_case.label("stage"),
                EventResponsibility.actor_id.label("operational_actor_id"),
                rn_col.label("rn"),
            )
            .select_from(Event)
            .join(
                per_person_rank_sq,
                (per_person_rank_sq.c.person_uid == Event.person_uid)
                & (stage_rank_case == per_person_rank_sq.c.max_rank),
            )
            .outerjoin(
                EventResponsibility,
                (EventResponsibility.event_id == Event.id)
                & (EventResponsibility.role == "operational"),
            )
            .where(*self._funnel_event_filters(
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                source_provider=source_provider,
                location_id=location_id,
            ))
        )
        latest_event_per_person = for_tenant(
            latest_event_per_person, tenant_id, Event
        )
        ranked = latest_event_per_person.subquery("ranked")
        stmt = select(
            ranked.c.person_uid,
            ranked.c.stage,
            ranked.c.operational_actor_id,
        ).where(ranked.c.rn == 1)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "person_uid": row.person_uid,
                "stage": row.stage,
                "operational_actor_id": row.operational_actor_id,
            }
            for row in rows
            if row.stage is not None
        ]

    def _funnel_stage_rank_case(self) -> Any:
        from sqlalchemy import case, literal

        whens = [
            (Event.kind == kind, literal(self._FUNNEL_STAGE_RANK[stage]))
            for kind, stage in self._FUNNEL_KIND_TO_STAGE.items()
        ]
        return case(*whens, else_=0)

    async def funnel_revenue_by_actor(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Sum of net realized payments attributed to each actor.

        Joins payment events (``recorded − refunded − reversed``) to
        ``event_responsibility``; the aggregation key is
        ``(actor_id, role)`` so the same actor showing up as both a
        TC (operational) and a doctor (clinical) reports separately.

        Reuses the PM Payments formula (ENG-283) so dashboard revenue
        slices reconcile.
        """
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"), 0
        )
        returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        stmt = (
            select(
                EventResponsibility.actor_id.label("actor_id"),
                EventResponsibility.role.label("role"),
                (recorded - returned).label("collected_total"),
                func.count()
                .filter(Event.kind == "payment_recorded")
                .label("payment_count"),
            )
            .select_from(Event)
            .join(EventResponsibility, EventResponsibility.event_id == Event.id)
            .where(
                Event.kind.in_(
                    ("payment_recorded", "payment_refunded", "payment_reversed")
                )
            )
            .where(Event.data_class == "billing")
            .group_by(EventResponsibility.actor_id, EventResponsibility.role)
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if source_provider is not None:
            stmt = stmt.where(Event.source_provider == source_provider)
        if location_id is not None:
            stmt = stmt.where(
                Event.payload["location_id"].astext == str(location_id)
            )
        if role is not None:
            stmt = stmt.where(EventResponsibility.role == role)
        stmt = for_tenant(stmt, tenant_id, Event)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "actor_id": row.actor_id,
                "role": row.role,
                "collected_total": float(row.collected_total or 0),
                "payment_count": int(row.payment_count or 0),
            }
            for row in rows
        ]

    async def funnel_revenue_by_person(
        self,
        tenant_id: TenantId,
        *,
        person_uids: list[UUID],
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, float]:
        """Per-person net realized payment $ for a specific person set.

        ENG-418 fix: the funnel drop-off "won" bucket needs the $ for the
        EXACT persons who dropped at ``opportunity_won`` — not the
        actor-wide aggregate. Reuses the same PM Payments formula
        (``recorded − refunded − reversed``) so totals reconcile.

        Returns ``{person_uid: collected_total}``. Persons with no
        payment events in the window contribute zero (absent from the
        dict).
        """
        if not person_uids:
            return {}
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"), 0
        )
        returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        stmt = (
            select(
                Event.person_uid.label("person_uid"),
                (recorded - returned).label("collected_total"),
            )
            .select_from(Event)
            .where(Event.person_uid.in_(person_uids))
            .where(
                Event.kind.in_(
                    ("payment_recorded", "payment_refunded", "payment_reversed")
                )
            )
            .where(Event.data_class == "billing")
            .group_by(Event.person_uid)
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if source_provider is not None:
            stmt = stmt.where(Event.source_provider == source_provider)
        if location_id is not None:
            stmt = stmt.where(
                Event.payload["location_id"].astext == str(location_id)
            )
        stmt = for_tenant(stmt, tenant_id, Event)
        rows = (await self._session.execute(stmt)).all()
        return {row.person_uid: float(row.collected_total or 0) for row in rows}

    async def funnel_distinct_actors(
        self,
        tenant_id: TenantId,
        *,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Distinct ``(actor_id, role)`` rows seen on responsibility rows."""
        stmt = (
            select(
                EventResponsibility.actor_id.label("actor_id"),
                EventResponsibility.role.label("role"),
            )
            .group_by(EventResponsibility.actor_id, EventResponsibility.role)
        )
        if role is not None:
            stmt = stmt.where(EventResponsibility.role == role)
        stmt = for_tenant(stmt, tenant_id, EventResponsibility)
        rows = (await self._session.execute(stmt)).all()
        return [
            {"actor_id": row.actor_id, "role": row.role}
            for row in rows
        ]


    async def list_recent_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        query: str | None = None,
        data_classes: tuple[str, ...] = ("public", "operational", "call_recording_ref"),
    ) -> list[Event]:
        """Return recent dashboard-safe events across the tenant.

        The caller chooses the allowed data classes. Raw payloads are never
        selected into DTOs by the service layer.
        """
        stmt = for_tenant(select(Event), tenant_id, Event).where(
            Event.data_class.in_(data_classes)
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if source_provider is not None:
            stmt = stmt.where(Event.source_provider == source_provider)
        if query is not None:
            needle = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Event.summary.ilike(needle),
                    Event.source_external_id.ilike(needle),
                )
            )
        stmt = stmt.order_by(Event.occurred_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_treatment_payment_aggregate(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Aggregate the dashboard-safe treatment/payment timeline slice.

        docs: ``apps/web/lib/docs/paymentsDoc.ts`` is the staff-facing
        explanation of the Collected formula below. If this aggregate
        changes, update that doc (BOTH ``en`` and ``ru``) in the same
        change. See ``apps/web/CLAUDE.md`` and ``packages/ingest/CLAUDE.md``.

        ``collected_total`` is the net cash collected:
        ``sum(payment_recorded.amount) − sum(payment_refunded.amount +
        payment_reversed.amount)`` (ENG-283). The dedicated
        ``payment_applied`` kind — CareStack's allocation leg, written
        every time a recorded payment is applied to an invoice — is
        deliberately excluded from the kind filter so it cannot
        contaminate any aggregate, mirroring the locked product
        decision in the mission ``decision-log``. ``payment_event_count``
        counts ``payment_recorded`` rows only. ``payment_total_amount``
        and first/last payment timestamps continue to track
        ``invoice_created`` rows so the existing widget remains
        backward-compatible.

        When ``location_id`` is set, the aggregate is restricted to events
        whose payload carries ``location_id`` matching the supplied UUID
        (ENG-267). Events without a payload location are excluded from
        the filtered view; events with a different location are also
        excluded. An unset ``location_id`` keeps the tenant-wide
        behaviour unchanged.
        """
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        collected_recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"),
            0,
        )
        collected_returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        stmt = for_tenant(
            select(
                func.count()
                .filter(Event.kind == "treatment_proposed")
                .label("treatment_presented_count"),
                func.count()
                .filter(Event.kind == "treatment_completed")
                .label("treatment_completed_count"),
                func.count()
                .filter(Event.kind == "invoice_created")
                .label("invoice_count"),
                func.coalesce(
                    func.sum(amount).filter(Event.kind == "invoice_created"),
                    0,
                ).label("payment_total_amount"),
                (collected_recorded - collected_returned).label("collected_total"),
                func.count()
                .filter(Event.kind == "payment_recorded")
                .label("payment_event_count"),
                func.min(Event.occurred_at)
                .filter(Event.kind == "invoice_created")
                .label("first_payment_at"),
                func.max(Event.occurred_at)
                .filter(Event.kind == "invoice_created")
                .label("last_payment_at"),
            ).select_from(Event),
            tenant_id,
            Event,
        ).where(
            Event.source_provider == "carestack",
            Event.source_kind.in_(
                (
                    "carestack_treatment_procedure",
                    "carestack_invoice",
                    "carestack_accounting_transaction",
                )
            ),
            # NB: ``payment_applied`` is intentionally absent. It is the
            # allocation leg of CareStack's double-entry ledger and
            # contributes nothing to cash collected, presented, or
            # invoiced totals (ENG-283).
            Event.kind.in_(
                (
                    "treatment_proposed",
                    "treatment_completed",
                    "invoice_created",
                    "payment_recorded",
                    "payment_refunded",
                    "payment_reversed",
                )
            ),
            Event.data_class.in_(("phi_protected", "billing")),
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if location_id is not None:
            stmt = stmt.where(
                Event.payload["location_id"].astext == str(location_id)
            )

        row = (await self._session.execute(stmt)).one()
        return dict(row._mapping)

    async def get_treatment_payment_quality_metrics(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Return aggregate quality counters for billing read models."""
        payment_kinds = ("payment_recorded", "payment_refunded", "payment_reversed")
        all_billing_kinds = (*payment_kinds, "payment_applied")
        stmt = for_tenant(
            select(
                func.count()
                .filter(Event.kind.in_(payment_kinds))
                .label("payment_event_count"),
                func.count()
                .filter(
                    Event.kind.in_(payment_kinds) & Event.person_uid.is_not(None)
                )
                .label("identity_linked_payment_count"),
                func.count()
                .filter(
                    Event.kind.in_(payment_kinds)
                    & Event.source_external_id.is_not(None)
                )
                .label("source_attributed_payment_count"),
                func.count()
                .filter(
                    Event.kind.in_(payment_kinds) & Event.source_external_id.is_(None)
                )
                .label("unmatched_payment_count"),
                func.count()
                .filter(Event.kind == "payment_applied")
                .label("payment_applied_excluded_count"),
            ).select_from(Event),
            tenant_id,
            Event,
        ).where(
            Event.source_provider == "carestack",
            Event.source_kind == "carestack_accounting_transaction",
            Event.kind.in_(all_billing_kinds),
            Event.data_class == "billing",
        )
        if occurred_from is not None:
            stmt = stmt.where(Event.occurred_at >= occurred_from)
        if occurred_to is not None:
            stmt = stmt.where(Event.occurred_at < occurred_to)
        if location_id is not None:
            stmt = stmt.where(Event.payload["location_id"].astext == str(location_id))
        row = (await self._session.execute(stmt)).one()
        return {key: int(value or 0) for key, value in row._mapping.items()}

    async def sum_collected_by_person(self, tenant_id: TenantId) -> dict[UUID, float]:
        """Net collected cash per person for the lead-source explorer (ENG-391).

        Same Collected semantics as :meth:`get_treatment_payment_aggregate`:
        ``sum(payment_recorded) − sum(payment_refunded + payment_reversed)``,
        with the ``payment_applied`` allocation leg excluded — grouped by
        ``person_uid`` so callers can attribute cash to acquisition
        resources via the persons behind each lead bucket.
        """
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"),
            0,
        )
        returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        stmt = (
            for_tenant(
                select(
                    Event.person_uid,
                    (recorded - returned).label("collected"),
                ).select_from(Event),
                tenant_id,
                Event,
            )
            .where(
                Event.source_provider == "carestack",
                Event.source_kind == "carestack_accounting_transaction",
                Event.kind.in_(
                    ("payment_recorded", "payment_refunded", "payment_reversed")
                ),
                Event.data_class == "billing",
            )
            .group_by(Event.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: float(collected)
            for person_uid, collected in rows
            if person_uid is not None
        }

    async def sum_collected_by_person_month(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime,
        occurred_to: datetime,
    ) -> list[tuple[UUID, str, float]]:
        """``(person_uid, YYYY-MM, net_collected)`` for the Full Funnel report.

        Same Collected semantics as :meth:`sum_collected_by_person`
        (``Σ payment_recorded − Σ(payment_refunded + payment_reversed)``,
        ``payment_applied`` allocation legs excluded), but grouped by person
        AND payment month and restricted to the ``[occurred_from,
        occurred_to)`` window on ``occurred_at`` — so the Full Funnel report
        (ENG-481) buckets revenue / paying persons on the payment date, the
        stage's own timestamp. The composition layer keeps only persons whose
        per-window net is positive for the ``closed_won`` count.
        """
        amount = cast(Event.payload["amount"].astext, Numeric(14, 2))
        recorded = func.coalesce(
            func.sum(amount).filter(Event.kind == "payment_recorded"),
            0,
        )
        returned = func.coalesce(
            func.sum(amount).filter(
                Event.kind.in_(("payment_refunded", "payment_reversed"))
            ),
            0,
        )
        month = func.to_char(func.timezone("UTC", Event.occurred_at), "YYYY-MM")
        stmt = (
            for_tenant(
                select(
                    Event.person_uid,
                    month.label("month"),
                    (recorded - returned).label("collected"),
                ).select_from(Event),
                tenant_id,
                Event,
            )
            .where(
                Event.source_provider == "carestack",
                Event.source_kind == "carestack_accounting_transaction",
                Event.kind.in_(
                    ("payment_recorded", "payment_refunded", "payment_reversed")
                ),
                Event.data_class == "billing",
                Event.occurred_at >= occurred_from,
                Event.occurred_at < occurred_to,
            )
            .group_by(Event.person_uid, month)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            (person_uid, str(mon), float(collected))
            for person_uid, mon, collected in rows
            if person_uid is not None
        ]

    async def earliest_event_at_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, datetime]:
        """``person_uid → MIN(event.occurred_at)`` for every person.

        One GROUP BY aggregate over ``interaction.event`` (ENG-481), not N
        queries and no giant bound IN clause (the CareStack-direct universe is
        ~50k persons — past asyncpg's parameter cap). The Full Funnel
        composition layer looks up only the CareStack-direct person_uids it
        cares about (those with no consultation); persons with no event are
        absent.
        """
        stmt = (
            for_tenant(
                select(
                    Event.person_uid,
                    func.min(Event.occurred_at),
                ).select_from(Event),
                tenant_id,
                Event,
            ).group_by(Event.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: earliest
            for person_uid, earliest in rows
            if person_uid is not None
        }

    async def analytics_event_milestones_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None]]:
        """``person_uid → (treatment_presented_date, first_payment_date)``.

        For the analytics fact builder (ENG-506), one GROUP BY aggregate over
        ``interaction.event``:

        - ``treatment_presented_date`` = ``MIN(occurred_at)`` over
          ``treatment_proposed`` events.
        - ``first_payment_date`` = ``MIN(occurred_at)`` over
          ``payment_recorded`` / ``invoice_created`` events (first cash or
          first invoice, whichever is earlier).

        Persons with neither milestone are absent.
        """
        stmt = (
            for_tenant(
                select(
                    Event.person_uid,
                    func.min(Event.occurred_at).filter(
                        Event.kind == "treatment_proposed"
                    ),
                    func.min(Event.occurred_at).filter(
                        Event.kind.in_(("payment_recorded", "invoice_created"))
                    ),
                ).select_from(Event),
                tenant_id,
                Event,
            )
            .where(
                Event.kind.in_(
                    ("treatment_proposed", "payment_recorded", "invoice_created")
                )
            )
            .group_by(Event.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (treatment_presented, first_payment)
            for person_uid, treatment_presented, first_payment in rows
            if person_uid is not None
        }

    async def analytics_surgery_stage_milestones_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None, datetime | None]]:
        """``person_uid → (treatment_accepted, surgery_scheduled, surgery_completed)``.

        For the analytics fact builder (ENG-511, B1.3), one GROUP BY aggregate
        over ``interaction.event``:

        - ``treatment_accepted_date`` = ``MIN(occurred_at)`` over
          ``treatment_accepted`` events (CareStack TreatmentPlan ``StatusId=3``;
          first observed acceptance).
        - ``surgery_scheduled_date`` = ``MIN(occurred_at)`` over
          ``surgery_scheduled`` events (implant-surgery procedure ``statusId=2``).
        - ``surgery_completed_date`` = ``MIN(occurred_at)`` over
          ``surgery_completed`` events (implant-surgery procedure ``statusId=8``).

        Persons with none of the three milestones are absent.
        """
        stmt = (
            for_tenant(
                select(
                    Event.person_uid,
                    func.min(Event.occurred_at).filter(
                        Event.kind == "treatment_accepted"
                    ),
                    func.min(Event.occurred_at).filter(
                        Event.kind == "surgery_scheduled"
                    ),
                    func.min(Event.occurred_at).filter(
                        Event.kind == "surgery_completed"
                    ),
                ).select_from(Event),
                tenant_id,
                Event,
            )
            .where(
                Event.kind.in_(
                    ("treatment_accepted", "surgery_scheduled", "surgery_completed")
                )
            )
            .group_by(Event.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (accepted, scheduled, completed)
            for person_uid, accepted, scheduled, completed in rows
            if person_uid is not None
        }

    async def analytics_clinical_actor_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, UUID]:
        """``person_uid → doctor actor_id`` from clinical responsibility (ENG-510).

        The clinical (doctor) actor attached to the person's EARLIEST clinical
        event. ``interaction.event_responsibility`` rows of ``role='clinical'``
        carry the CareStack appointment-provider actor (resolved during ingest
        by the funnel-responsibility resolver, ENG-417). Picking the earliest
        clinical event gives a deterministic treating-doctor per person. One
        GROUP BY aggregate; persons with no clinical responsibility are absent
        (NULL doctor, method=unresolved in the builder).
        """
        actor_first = func.array_agg(
            aggregate_order_by(  # type: ignore[no-untyped-call]
                EventResponsibility.actor_id, Event.occurred_at.asc()
            )
        )
        stmt = (
            for_tenant(
                select(Event.person_uid, actor_first[1]).select_from(
                    EventResponsibility
                ),
                tenant_id,
                EventResponsibility,
            )
            .join(Event, Event.id == EventResponsibility.event_id)
            .where(EventResponsibility.role == "clinical")
            .group_by(Event.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: actor_id
            for person_uid, actor_id in rows
            if person_uid is not None and actor_id is not None
        }

    async def profile_payment_event_field(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int,
    ) -> dict[str, object]:
        """Aggregate-profile an allowlisted billing event field."""
        if field != "payment_kind":
            raise ValueError(f"unsupported payment event profile field: {field}")

        base_filters = (
            Event.source_provider == "carestack",
            Event.source_kind == "carestack_accounting_transaction",
            Event.kind.in_(
                (
                    "payment_recorded",
                    "payment_refunded",
                    "payment_reversed",
                    "payment_applied",
                )
            ),
            Event.data_class == "billing",
        )
        total_stmt = (
            for_tenant(
                select(
                    func.count().label("row_count"),
                    func.count().filter(Event.kind.is_(None)).label("null_count"),
                ).select_from(Event),
                tenant_id,
                Event,
            )
            .where(*base_filters)
        )
        total_row = (await self._session.execute(total_stmt)).one()

        top_stmt = (
            for_tenant(
                select(Event.kind.label("value"), func.count().label("count")).select_from(Event),
                tenant_id,
                Event,
            )
            .where(*base_filters)
            .where(Event.kind.is_not(None))
            .group_by(Event.kind)
            .order_by(func.count().desc())
            .limit(limit)
        )
        top_rows = (await self._session.execute(top_stmt)).all()
        return {
            "row_count": int(total_row.row_count),
            "null_count": int(total_row.null_count),
            "top_values": [
                {"value": str(value), "count": int(count)}
                for value, count in top_rows
                if value is not None
            ],
        }

    async def list_payment_event_samples(
        self,
        tenant_id: TenantId,
        *,
        limit: int,
    ) -> list[Event]:
        """Return bounded billing events for service-level masked samples."""
        stmt = (
            for_tenant(select(Event), tenant_id, Event)
            .where(
                Event.source_provider == "carestack",
                Event.source_kind == "carestack_accounting_transaction",
                Event.kind.in_(
                    (
                        "payment_recorded",
                        "payment_refunded",
                        "payment_reversed",
                        "payment_applied",
                    )
                ),
                Event.data_class == "billing",
            )
            .order_by(Event.occurred_at.desc(), Event.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
