"""Data access for ``analytics.fact_patient_journey`` (ENG-506).

The ONLY writer of the analytics read-model. Idempotent upsert keyed on
``person_uid`` (``ON CONFLICT DO UPDATE``) so a rebuild produces identical rows.
Reads existing ``field_provenance`` so the builder can merge new provenance over
it without clobbering manual values (manual > auto > unresolved).

Repository is data-only — it never commits; the caller boundary (worker job /
test) owns the transaction.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .filters import AnalyticsFilters, ResolvedWindow
from .models import FactPatientJourney


@dataclass(frozen=True)
class FactAggregateRow:
    """Per-window stage counts + money over ``fact_patient_journey``.

    A persons-cohort aggregate anchored on ``lead_date``: every count is over
    the persons whose ``lead_date`` lands in the window (plus the dimension
    filters), and a count is the number of those persons with a non-null stage
    date. ``revenue`` / ``collected`` sum the money columns.
    """

    leads: int = 0
    contacts: int = 0
    consults: int = 0
    shows: int = 0
    surgeries: int = 0
    patients: int = 0
    revenue: float = 0.0
    collected: float = 0.0


@dataclass(frozen=True)
class ExistingFactRow:
    """A previously-persisted fact row's provenance + value columns.

    Returned by :meth:`FactPatientJourneyRepository.existing_for_merge` so the
    builder can preserve manual values AND provenance across a rebuild.
    ``values`` is keyed by column name (the projected columns, excluding
    ``field_provenance``).
    """

    field_provenance: dict[str, object]
    values: dict[str, object]

# Columns the builder sets (everything except the PK + server-managed
# created_at/updated_at). Kept explicit so an upsert updates exactly the
# projected columns and nothing else.
_UPSERT_COLUMNS: tuple[str, ...] = (
    "campaign_id",
    "campaign_name",
    "source",
    "vendor_id",
    "case_type",
    "caller_id",
    "coordinator_id",
    "doctor_id",
    "location_id",
    "lead_date",
    "first_contact_date",
    "consult_scheduled_date",
    "show_date",
    "treatment_presented_date",
    "treatment_accepted_date",
    "surgery_scheduled_date",
    "surgery_completed_date",
    "first_payment_date",
    "revenue_amount",
    "collected_amount",
    "marketing_cost_allocated",
    "field_provenance",
)


class FactPatientJourneyRepository:
    """Idempotent storage for the per-person revenue-journey fact."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def existing_for_merge(
        self, person_uids: Sequence[UUID]
    ) -> dict[UUID, ExistingFactRow]:
        """``person_uid → (field_provenance, value columns)`` for existing rows.

        Used by the builder to carry BOTH manual provenance AND manual values
        forward across a rebuild: a field resolved ``method='manual'`` keeps its
        stored value (the builder must not overwrite it with the recomputed
        ``auto`` value — manual > auto > unresolved). Chunked to stay well under
        the asyncpg bound-parameter cap.
        """
        out: dict[UUID, ExistingFactRow] = {}
        value_cols = [
            getattr(FactPatientJourney, col)
            for col in _UPSERT_COLUMNS
            if col != "field_provenance"
        ]
        for chunk in _chunked(person_uids, 5000):
            stmt = select(
                FactPatientJourney.person_uid,
                FactPatientJourney.field_provenance,
                *value_cols,
            ).where(FactPatientJourney.person_uid.in_(chunk))
            for row in (await self._session.execute(stmt)).mappings().all():
                provenance = row[FactPatientJourney.field_provenance] or {}
                values = {
                    col: row[getattr(FactPatientJourney, col)]
                    for col in _UPSERT_COLUMNS
                    if col != "field_provenance"
                }
                out[row[FactPatientJourney.person_uid]] = ExistingFactRow(
                    field_provenance=provenance, values=values
                )
        return out

    async def apply_manual_override(
        self,
        person_uid: UUID,
        field: str,
        value: object,
        *,
        provenance_entry: dict[str, object],
    ) -> None:
        """Set ONE fact field to an operator-supplied value (ENG-513).

        ``method='manual'`` provenance is the highest precedence, so this
        unconditionally overwrites the field value and stamps
        ``field_provenance[field]`` with the manual entry. A subsequent builder
        rebuild preserves both (see :meth:`existing_for_merge`). Creates the
        row if the person has no fact row yet (an operator may enrich a person
        the projection has not yet materialised). ``field`` MUST be a member of
        :data:`_UPSERT_COLUMNS` (validated by the caller).
        """
        row = await self.get(person_uid)
        if row is None:
            row = FactPatientJourney(person_uid=person_uid, field_provenance={})
            self._session.add(row)
        setattr(row, field, value)
        provenance = dict(row.field_provenance or {})
        provenance[field] = provenance_entry
        row.field_provenance = provenance
        await self._session.flush()

    async def upsert_many(self, rows: Sequence[dict[str, object]]) -> int:
        """Upsert fact rows keyed on ``person_uid``. Returns the row count.

        ``ON CONFLICT (person_uid) DO UPDATE`` refreshes exactly the projected
        columns; ``updated_at`` is bumped to ``now()`` by the column's
        ``onupdate``. No-op for an empty batch.
        """
        if not rows:
            return 0
        written = 0
        # A multi-row VALUES insert requires every row dict to carry the SAME
        # keys; the builder omits unresolved dimension columns, which makes
        # psycopg/SQLAlchemy fail to render the multiparams VALUES clause.
        # Normalise every row to the full column set (missing → NULL;
        # field_provenance is NOT NULL so default to {}).
        _cols = ("person_uid", *_UPSERT_COLUMNS)
        normalized_rows = [
            {
                col: (
                    row.get(col)
                    if col != "field_provenance"
                    else (row.get("field_provenance") or {})
                )
                for col in _cols
            }
            for row in rows
        ]
        for chunk in _chunked(normalized_rows, 1000):
            stmt = pg_insert(FactPatientJourney).values(list(chunk))
            stmt = stmt.on_conflict_do_update(
                index_elements=[FactPatientJourney.person_uid],
                set_={col: stmt.excluded[col] for col in _UPSERT_COLUMNS},
            )
            await self._session.execute(stmt)
            written += len(chunk)
        return written

    async def count(self) -> int:
        """Total fact rows (test/verification helper)."""
        stmt = select(func.count()).select_from(FactPatientJourney)
        return int((await self._session.execute(stmt)).scalar_one())

    async def get(self, person_uid: UUID) -> FactPatientJourney | None:
        """Fetch one fact row (test/verification helper)."""
        stmt = select(FactPatientJourney).where(
            FactPatientJourney.person_uid == person_uid
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def aggregate(
        self, *, window: ResolvedWindow, filters: AnalyticsFilters
    ) -> FactAggregateRow:
        """Stage counts + money over the window + dimension filters (ENG-507).

        Cohort anchored on ``lead_date`` (the funnel entry); ``location_id=None``
        on the filter means aggregate over all locations. Each stage count is the
        number of in-cohort persons with a non-null stage date.
        """
        m = FactPatientJourney

        stmt = select(
            func.count(m.lead_date).label("leads"),
            func.count(m.first_contact_date).label("contacts"),
            func.count(m.consult_scheduled_date).label("consults"),
            func.count(m.show_date).label("shows"),
            func.count(m.surgery_completed_date).label("surgeries"),
            func.count().label("patients"),
            func.coalesce(func.sum(m.revenue_amount), 0).label("revenue"),
            func.coalesce(func.sum(m.collected_amount), 0).label("collected"),
        ).where(
            m.lead_date >= window.start,
            m.lead_date < window.end,
        )

        # Dimension equality filters — None means "do not filter".
        for column, value in (
            (m.location_id, filters.location_id),
            (m.campaign_id, filters.campaign_id),
            (m.source, filters.source),
            (m.vendor_id, filters.vendor_id),
            (m.caller_id, filters.caller_id),
            (m.coordinator_id, filters.coordinator_id),
            (m.doctor_id, filters.doctor_id),
        ):
            if value is not None:
                stmt = stmt.where(column == value)

        row = (await self._session.execute(stmt)).one()
        return FactAggregateRow(
            leads=int(row.leads),
            contacts=int(row.contacts),
            consults=int(row.consults),
            shows=int(row.shows),
            surgeries=int(row.surgeries),
            patients=int(row.patients),
            revenue=float(row.revenue),
            collected=float(row.collected),
        )


def _chunked(items: Sequence[object], size: int) -> Iterable[Sequence[object]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
