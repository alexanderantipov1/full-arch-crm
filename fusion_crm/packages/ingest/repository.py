"""Ingest repository — capture/inspect raw events and normalised hints.

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128). The mutation methods (``mark_processed`` / ``mark_error``)
also require the tenant id so a stray UUID can't update a row in a
different tenant by accident.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import (
    CareStackProvider,
    NormalizedPersonHint,
    RawEvent,
    SourceObjectField,
)

if TYPE_CHECKING:
    from packages.identity.models import SourceLink


class IngestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: RawEvent) -> RawEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    # --- Full-fidelity schema registry (ENG-426) ---

    async def list_object_fields(
        self, tenant_id: TenantId, *, provider: str, object_name: str
    ) -> list[SourceObjectField]:
        """All registry rows for one ``(provider, object_name)`` (active or not)."""
        stmt = (
            for_tenant(select(SourceObjectField), tenant_id, SourceObjectField)
            .where(SourceObjectField.provider == provider)
            .where(SourceObjectField.object_name == object_name)
            .order_by(SourceObjectField.field_name.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_object_field(self, field: SourceObjectField) -> SourceObjectField:
        self._session.add(field)
        await self._session.flush()
        return field

    async def get(self, tenant_id: TenantId, event_id: UUID) -> RawEvent | None:
        stmt = for_tenant(select(RawEvent), tenant_id, RawEvent).where(
            RawEvent.id == event_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_unprocessed(
        self, tenant_id: TenantId, limit: int = 100, source: str | None = None
    ) -> list[RawEvent]:
        stmt = (
            for_tenant(select(RawEvent), tenant_id, RawEvent)
            .where(RawEvent.processed_at.is_(None))
            .order_by(RawEvent.received_at.asc())
            .limit(limit)
        )
        if source is not None:
            stmt = stmt.where(RawEvent.source == source)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_recent(
        self,
        tenant_id: TenantId,
        limit: int = 50,
        provider: str | None = None,
    ) -> list[RawEvent]:
        stmt = (
            for_tenant(select(RawEvent), tenant_id, RawEvent)
            .order_by(RawEvent.received_at.desc())
            .limit(limit)
        )
        if provider is not None:
            stmt = stmt.where(RawEvent.source == provider)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count(
        self, tenant_id: TenantId, provider: str | None = None
    ) -> int:
        from sqlalchemy import func

        stmt = for_tenant(
            select(func.count()).select_from(RawEvent), tenant_id, RawEvent
        )
        if provider is not None:
            stmt = stmt.where(RawEvent.source == provider)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def distinct_payload_int_values(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        payload_key: str,
    ) -> list[int]:
        """Distinct integer ``payload[payload_key]`` values for an event type.

        Backs the by-id procedure-code catalog sync (ENG-538): the set of
        distinct ``procedureCodeId`` values observed across captured
        ``carestack.treatment_procedure.upsert`` raw_events is the work-list of
        ids to resolve via the by-id endpoint. Non-numeric / null values are
        dropped (the JSON value is read as text then parsed in Python).
        Returns a sorted, deduped list. Tenant-scoped.
        """
        value_col = RawEvent.payload[payload_key].astext
        stmt = (
            for_tenant(select(value_col), tenant_id, RawEvent)
            .where(RawEvent.event_type == event_type)
            .where(value_col.is_not(None))
            .distinct()
        )
        out: set[int] = set()
        for (value,) in (await self._session.execute(stmt)).all():
            if value is None:
                continue
            try:
                out.add(int(str(value).strip()))
            except (TypeError, ValueError):
                continue
        return sorted(out)

    async def treatment_procedure_code_ids_by_patient(
        self, tenant_id: TenantId
    ) -> dict[str, list[int]]:
        """``patientId -> [procedureCodeId, ...]`` over distinct treatment procedures.

        Backs the analytics implant ``case_type`` resolver (ENG-539). For every
        DISTINCT captured treatment procedure (``DISTINCT ON (external_id)`` keeps
        the newest payload per procedure, so a re-pulled procedure counts once),
        extract its ``patientId`` and ``procedureCodeId`` and group the code ids
        under the CareStack patient id. One list entry per procedure, so the
        D6010 placement COUNT downstream is the number of placement procedures —
        not inflated by a procedure's multiple lifecycle re-captures.

        Returns CareStack-id-space scalars only (patient id + integer
        procedure-code id) — NO clinical fields, tooth numbers, surfaces, or
        financials leave the raw layer. The caller (the fact builder) maps
        ``patientId -> person_uid`` via ``IdentityService`` and
        ``procedureCodeId -> CDT`` via ``CatalogService``. Tenant-scoped.
        """
        patient_col = func.coalesce(
            RawEvent.payload["patientId"].astext,
            RawEvent.payload["PatientId"].astext,
        )
        code_col = func.coalesce(
            RawEvent.payload["procedureCodeId"].astext,
            RawEvent.payload["ProcedureCodeId"].astext,
        )
        stmt = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    patient_col.label("patient_id"),
                    code_col.label("code_id"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(
                RawEvent.event_type == "carestack.treatment_procedure.upsert",
                RawEvent.external_id.is_not(None),
            )
            .distinct(RawEvent.external_id)
            .order_by(
                RawEvent.external_id,
                RawEvent.received_at.desc(),
                RawEvent.id.desc(),
            )
        )
        out: dict[str, list[int]] = {}
        for _external_id, patient_id, code_id in (
            await self._session.execute(stmt)
        ).all():
            if patient_id is None or code_id is None:
                continue
            try:
                code = int(str(code_id).strip())
            except (TypeError, ValueError):
                continue
            patient_key = str(patient_id).strip()
            if not patient_key:
                continue
            out.setdefault(patient_key, []).append(code)
        return out
    async def count_distinct_external_ids_by_type(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        since: datetime | None = None,
    ) -> int:
        """Count distinct ``external_id`` values captured for an event type.

        Backs the dry-run candidate count for the treatment-procedure replay
        (ENG-540) — the number of procedures that WOULD be re-projected —
        without loading any payloads or hitting CareStack. Tenant-scoped.
        """
        stmt = (
            for_tenant(
                select(func.count(func.distinct(RawEvent.external_id))),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.event_type == event_type)
            .where(RawEvent.external_id.is_not(None))
        )
        if since is not None:
            stmt = stmt.where(RawEvent.received_at >= since)
        return int((await self._session.execute(stmt)).scalar_one())

    async def max_payload_watermark(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        watermark_key: str = "lastUpdatedOn",
    ) -> str | None:
        """Return the maximum ``payload[watermark_key]`` for an event type.

        Used to derive an incremental ``modifiedSince`` cursor for
        CareStack sync pulls from the rows already captured in
        ``raw_event`` (no separate cursor table). CareStack
        ``lastUpdatedOn`` is a fixed-format ISO 8601 string, so the
        lexical ``max`` over the JSONB text is also the chronological
        max. Returns ``None`` when no row of this type exists yet.
        """
        watermark_col = RawEvent.payload[watermark_key].astext
        stmt = for_tenant(
            select(func.max(watermark_col)), tenant_id, RawEvent
        ).where(RawEvent.event_type == event_type)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def latest_payload_values(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        external_ids: Sequence[str],
        payload_key: str,
    ) -> dict[str, str]:
        """Highest ``payload[payload_key]`` per ``external_id`` for a batch.

        Backs the capture change-guard (ENG-381): a puller fetches the
        already-captured modified-stamp for every candidate row in ONE
        query and skips re-capturing rows whose provider stamp did not
        move. Both SF ``LastModifiedDate`` and CareStack ``lastUpdatedOn``
        are fixed-format ISO 8601 strings, so the lexical ``max`` is the
        chronological max (same argument as ``max_payload_watermark``).
        External ids with no captured row are absent from the result.
        """
        if not external_ids:
            return {}
        value_col = RawEvent.payload[payload_key].astext
        stmt = (
            for_tenant(
                select(RawEvent.external_id, func.max(value_col)),
                tenant_id,
                RawEvent,
            )
            .where(
                RawEvent.event_type == event_type,
                RawEvent.external_id.in_(list(external_ids)),
                value_col.is_not(None),
            )
            .group_by(RawEvent.external_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(external_id): str(value) for external_id, value in rows}

    async def latest_payload(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        external_id: str,
    ) -> dict[str, object] | None:
        """Newest captured payload for one ``(event_type, external_id)``.

        Used by snapshot-style feeds (payment summary) that have no
        provider modified-stamp: the caller compares snapshot CONTENT
        against the latest stored one and skips identical writes.
        """
        stmt = (
            for_tenant(select(RawEvent.payload), tenant_id, RawEvent)
            .where(
                RawEvent.event_type == event_type,
                RawEvent.external_id == external_id,
            )
            .order_by(RawEvent.received_at.desc(), RawEvent.id.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return dict(row) if row is not None else None

    async def sample_recent_payloads(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        """Most-recent captured payloads for an event type (ENG-429).

        Backs the REST observed-key schema snapshot: a source without a
        ``describe`` (CareStack) has its schema derived from the union of keys
        across a sample of recently-captured raw payloads. Newest first so the
        sample reflects the current shape.
        """
        stmt = (
            for_tenant(select(RawEvent.payload), tenant_id, RawEvent)
            .where(RawEvent.event_type == event_type)
            .order_by(RawEvent.received_at.desc(), RawEvent.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [dict(row) for row in rows]

    async def list_latest_by_type_since(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        since: datetime,
    ) -> list[tuple[UUID, dict[str, object]]]:
        """Latest raw ``(id, payload)`` per ``external_id`` for an event type.

        Used by SF-task reconciliation (ENG-462) to re-project tasks that
        were captured before their ``WhoId`` lead was linked. ``DISTINCT ON``
        keeps exactly one row per external id (the newest), so a task with
        re-pull rows projects once from its freshest payload.
        """
        stmt = (
            for_tenant(
                select(RawEvent.id, RawEvent.payload, RawEvent.external_id),
                tenant_id,
                RawEvent,
            )
            .where(
                RawEvent.event_type == event_type,
                RawEvent.received_at >= since,
                RawEvent.external_id.is_not(None),
            )
            .distinct(RawEvent.external_id)
            .order_by(
                RawEvent.external_id,
                RawEvent.received_at.desc(),
                RawEvent.id.desc(),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], dict(row[1])) for row in rows]

    async def list_latest_by_type_paginated(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        limit: int,
        after_external_id: str | None = None,
        since: datetime | None = None,
    ) -> list[tuple[UUID, str, dict[str, object]]]:
        """One ``external_id``-cursored page of latest ``(id, external_id, payload)``.

        Like :meth:`list_latest_by_type_since` (``DISTINCT ON (external_id)``
        keeps the newest raw row per external id), but bounded + resumable for
        the ENG-540 replay: results are ordered by ``external_id`` ascending so
        ``after_external_id`` is a stable forward cursor and ``limit`` caps the
        batch. ``since`` optionally windows by ``received_at``. The returned
        ``external_id`` is the cursor the caller passes as ``after_external_id``
        for the next page.
        """
        stmt = for_tenant(
            select(RawEvent.id, RawEvent.external_id, RawEvent.payload),
            tenant_id,
            RawEvent,
        ).where(
            RawEvent.event_type == event_type,
            RawEvent.external_id.is_not(None),
        )
        if since is not None:
            stmt = stmt.where(RawEvent.received_at >= since)
        if after_external_id is not None:
            stmt = stmt.where(RawEvent.external_id > after_external_id)
        stmt = (
            stmt.distinct(RawEvent.external_id)
            .order_by(
                RawEvent.external_id.asc(),
                RawEvent.received_at.desc(),
                RawEvent.id.desc(),
            )
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1], dict(row[2])) for row in rows]

    async def list_source_records(
        self,
        tenant_id: TenantId,
        *,
        sources: tuple[str, ...],
        limit: int,
    ) -> list[tuple[RawEvent, NormalizedPersonHint | None]]:
        """Return recent raw events plus their optional normalized person hint."""
        if not sources:
            return []
        stmt = (
            for_tenant(select(RawEvent, NormalizedPersonHint), tenant_id, RawEvent)
            .outerjoin(
                NormalizedPersonHint,
                (NormalizedPersonHint.tenant_id == RawEvent.tenant_id)
                & (NormalizedPersonHint.raw_event_id == RawEvent.id),
            )
            .where(RawEvent.source.in_(sources))
            .order_by(RawEvent.received_at.desc())
            .limit(limit)
        )
        return [
            (raw_event, hint)
            for raw_event, hint in (await self._session.execute(stmt)).all()
        ]

    async def mark_processed(
        self, tenant_id: TenantId, event_id: UUID, when: datetime
    ) -> None:
        event = await self.get(tenant_id, event_id)
        if event is None:
            return
        event.processed_at = when

    async def mark_error(
        self, tenant_id: TenantId, event_id: UUID, error: str
    ) -> None:
        event = await self.get(tenant_id, event_id)
        if event is None:
            return
        event.error = error[:1024]

    # --- Normalized person hints (ENG-185) ---

    async def add_normalized_person_hint(
        self, hint: NormalizedPersonHint
    ) -> NormalizedPersonHint:
        self._session.add(hint)
        await self._session.flush()
        return hint

    async def find_hint_by_raw_event(
        self, tenant_id: TenantId, raw_event_id: UUID
    ) -> NormalizedPersonHint | None:
        """Return the hint extracted from a given raw event, if any.

        Mirrors the ``(tenant_id, raw_event_id)`` unique constraint — at
        most one row matches for this slice.
        """
        stmt = (
            for_tenant(select(NormalizedPersonHint), tenant_id, NormalizedPersonHint)
            .where(NormalizedPersonHint.raw_event_id == raw_event_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_carestack_invoice_refs(
        self,
        tenant_id: TenantId,
        invoice_ids: Sequence[str],
    ) -> dict[str, dict[str, str | None]]:
        """Resolve CareStack invoice ids to their human number + date.

        Reads ONLY two non-PII scalar fields — ``invoiceNumber`` and the ISO
        date prefix of ``paymentDate`` — from the LATEST invoice raw_event per
        ``external_id``. It never selects or returns the verbatim payload, so
        the no-raw-payload-on-dashboard contract holds. Used by the PM
        Payments route to show which invoice a payment belongs to (ENG-303).

        Returns ``{invoice_id: {"invoice_number": str|None,
        "invoice_date": str|None}}``. Invoice ids with no captured invoice row
        are simply absent from the map (the row renders without invoice info).
        """
        ids = [i for i in invoice_ids if i]
        if not ids:
            return {}

        latest_subq = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    func.max(RawEvent.received_at).label("latest_received_at"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.invoice.upsert")
            .where(RawEvent.external_id.in_(ids))
            .group_by(RawEvent.external_id)
            .subquery()
        )

        stmt = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    RawEvent.payload["invoiceNumber"].astext.label(
                        "invoice_number"
                    ),
                    func.left(
                        RawEvent.payload["paymentDate"].astext, 10
                    ).label("invoice_date"),
                ),
                tenant_id,
                RawEvent,
            )
            .join(
                latest_subq,
                (RawEvent.external_id == latest_subq.c.external_id)
                & (RawEvent.received_at == latest_subq.c.latest_received_at),
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.invoice.upsert")
        )

        result: dict[str, dict[str, str | None]] = {}
        for row in (await self._session.execute(stmt)).all():
            external_id = row.external_id
            if external_id is None:
                continue
            result[external_id] = {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date,
            }
        return result

    async def get_carestack_accounting_codes(
        self,
        tenant_id: TenantId,
        raw_event_ids: Sequence[UUID],
    ) -> dict[UUID, tuple[int | None, int | None]]:
        """Resolve accounting-transaction raw events → ``(procedureCodeId, providerId)``.

        Each PM Payments row carries ``source_event_id`` — the UUID PK of the
        ``carestack.accounting_transaction.upsert`` raw_event it was projected
        from. We read back ONLY two non-PII id scalars from those raw payloads —
        ``procedureCodeId`` and ``providerId`` — so the operator can see what a
        payment was for and who performed it (ENG-547). The verbatim payload
        (clinical notes, tooth/surface) is never selected, so the
        no-raw-payload-on-dashboard contract holds.

        Returns ``{raw_event_id: (procedure_code_id, provider_id)}`` — either
        scalar may be ``None`` (advances, unallocated legs, adjustments), and
        raw ids with no captured row are simply absent. Keyed by the raw_event
        PK (exact 1:1 link), not the transaction id, so there is no ambiguity
        from re-pull rows.
        """
        ids = [rid for rid in raw_event_ids if rid is not None]
        if not ids:
            return {}

        stmt = (
            for_tenant(
                select(
                    RawEvent.id,
                    RawEvent.payload["procedureCodeId"].astext.label(
                        "procedure_code_id"
                    ),
                    RawEvent.payload["providerId"].astext.label("provider_id"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(
                RawEvent.event_type == "carestack.accounting_transaction.upsert"
            )
            .where(RawEvent.id.in_(ids))
        )

        result: dict[UUID, tuple[int | None, int | None]] = {}
        for row in (await self._session.execute(stmt)).all():
            result[row.id] = (
                _parse_optional_int(row.procedure_code_id),
                _parse_optional_int(row.provider_id),
            )
        return result

    async def get_treatment_procedure_refs(
        self,
        tenant_id: TenantId,
        tp_ids: Sequence[int],
    ) -> dict[int, tuple[int | None, int | None]]:
        """Resolve treatment-procedure INSTANCE ids → ``(cdt_code_id, provider_id)``.

        ENG-551: ``accounting_transaction.procedureCodeId`` is NOT a CDT catalog
        id — its value is a ``treatment_procedure.id`` (the procedure INSTANCE
        id). To resolve the real operation we hop through the treatment
        procedure: read each ``carestack.treatment_procedure.upsert`` raw payload
        by its payload ``id`` and return ONLY the two id scalars the dashboard
        needs — the real CDT ``procedureCodeId`` and the performing
        ``providerId``. The verbatim payload (tooth, surfaces, notes, statusId,
        dates) is NEVER selected, so no clinical field leaves the raw layer.

        Returns ``{tp_id: (cdt_code_id, provider_id)}`` from the NEWEST captured
        payload per ``id`` (a procedure is re-pulled on every lifecycle change;
        ``DISTINCT ON`` over the payload id keeps the latest). Either scalar may
        be ``None``; tp ids with no captured treatment-procedure row are absent.
        Tenant-scoped and event_type-pinned.
        """
        wanted = sorted({int(t) for t in tp_ids if t is not None})
        if not wanted:
            return {}
        wanted_text = [str(w) for w in wanted]

        id_col = RawEvent.payload["id"].astext
        code_col = RawEvent.payload["procedureCodeId"].astext
        provider_col = RawEvent.payload["providerId"].astext
        stmt = (
            for_tenant(
                select(
                    id_col.label("tp_id"),
                    code_col.label("cdt_code_id"),
                    provider_col.label("provider_id"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(
                RawEvent.event_type == "carestack.treatment_procedure.upsert"
            )
            .where(id_col.in_(wanted_text))
            .distinct(id_col)
            .order_by(id_col, RawEvent.received_at.desc(), RawEvent.id.desc())
        )

        result: dict[int, tuple[int | None, int | None]] = {}
        for row in (await self._session.execute(stmt)).all():
            tp_id = _parse_optional_int(row.tp_id)
            if tp_id is None:
                continue
            result[tp_id] = (
                _parse_optional_int(row.cdt_code_id),
                _parse_optional_int(row.provider_id),
            )
        return result

    async def sum_latest_payment_summary_balances(
        self,
        tenant_id: TenantId,
        *,
        ar_risk_threshold: float,
    ) -> dict[str, object]:
        """Sum the LATEST CareStack payment-summary snapshot per patient.

        The sweep (``CareStackPaymentSummaryIngestService``) writes one
        ``carestack.payment_summary.snapshot`` raw_event per patient per
        run, with ``external_id`` = the CareStack patient id. The latest
        snapshot per ``external_id`` is the current balance; older ones
        are intentionally retained for the snapshot timeline.

        Returns a row with the summed ``balance_due_patient``,
        ``balance_due_insurance``, the snapshot ``patient_count``, and
        ``ar_risk_count`` = the number of patients whose latest
        ``balanceDuePatient`` is strictly greater than
        ``ar_risk_threshold`` (ENG-266). A patient exactly AT the
        threshold is NOT counted — the rule is "above the line, not on
        it". Tenant-scoped.
        """
        from sqlalchemy import Numeric, case, cast, func, select

        latest_subq = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    func.max(RawEvent.received_at).label("latest_received_at"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.payment_summary.snapshot")
            .where(RawEvent.external_id.is_not(None))
            .group_by(RawEvent.external_id)
            .subquery()
        )

        latest_rows = (
            for_tenant(select(RawEvent), tenant_id, RawEvent)
            .join(
                latest_subq,
                (RawEvent.external_id == latest_subq.c.external_id)
                & (RawEvent.received_at == latest_subq.c.latest_received_at),
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.payment_summary.snapshot")
            .subquery()
        )

        balance_patient = cast(
            latest_rows.c.payload["balanceDuePatient"].astext, Numeric(14, 2)
        )
        balance_insurance = cast(
            latest_rows.c.payload["balanceDueInsurance"].astext, Numeric(14, 2)
        )

        agg_stmt = select(
            func.coalesce(func.sum(balance_patient), 0).label("balance_due_patient"),
            func.coalesce(func.sum(balance_insurance), 0).label("balance_due_insurance"),
            func.count().label("patient_count"),
            func.coalesce(
                func.sum(case((balance_patient > ar_risk_threshold, 1), else_=0)),
                0,
            ).label("ar_risk_count"),
        )

        row = (await self._session.execute(agg_stmt)).one()
        return dict(row._mapping)

    async def latest_payment_summary_by_patient(
        self,
        tenant_id: TenantId,
        patient_ids: Sequence[str],
    ) -> dict[str, dict[str, object]]:
        """Return the LATEST payment-summary snapshot per CareStack patient id.

        Used by the per-person financial summary (ENG-306) and the PM
        Payments row balance pill. For each requested patient id, picks
        the highest ``received_at`` ``carestack.payment_summary.snapshot``
        raw_event and extracts ``balanceDuePatient + balanceDueInsurance``
        (= Balance) plus ``appliedPatientPayment + appliedInsPayments``
        (= Paid). Patient ids with no captured snapshot are absent from
        the returned dict — the caller (UI) renders ``"—"`` in their
        place; ``"$0"`` would falsely imply we know the balance is zero.

        Returns ``{patient_id: {"balance": float, "paid": float,
        "received_at": datetime}}``. Tenant-scoped.
        """
        ids = sorted({pid for pid in patient_ids if pid})
        if not ids:
            return {}

        from sqlalchemy import Numeric, cast, func, select

        latest_subq = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    func.max(RawEvent.received_at).label("latest_received_at"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.payment_summary.snapshot")
            .where(RawEvent.external_id.in_(ids))
            .group_by(RawEvent.external_id)
            .subquery()
        )

        balance_patient = cast(
            RawEvent.payload["balanceDuePatient"].astext, Numeric(14, 2)
        )
        balance_insurance = cast(
            RawEvent.payload["balanceDueInsurance"].astext, Numeric(14, 2)
        )
        applied_patient = cast(
            RawEvent.payload["appliedPatientPayment"].astext, Numeric(14, 2)
        )
        applied_insurance = cast(
            RawEvent.payload["appliedInsPayments"].astext, Numeric(14, 2)
        )

        stmt = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    RawEvent.received_at,
                    func.coalesce(balance_patient, 0).label("balance_due_patient"),
                    func.coalesce(balance_insurance, 0).label("balance_due_insurance"),
                    func.coalesce(applied_patient, 0).label("applied_patient_payment"),
                    func.coalesce(applied_insurance, 0).label("applied_ins_payments"),
                ),
                tenant_id,
                RawEvent,
            )
            .join(
                latest_subq,
                (RawEvent.external_id == latest_subq.c.external_id)
                & (RawEvent.received_at == latest_subq.c.latest_received_at),
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.payment_summary.snapshot")
        )

        result: dict[str, dict[str, object]] = {}
        for row in (await self._session.execute(stmt)).all():
            external_id = row.external_id
            if external_id is None:
                continue
            balance = float(row.balance_due_patient or 0) + float(
                row.balance_due_insurance or 0
            )
            paid = float(row.applied_patient_payment or 0) + float(
                row.applied_ins_payments or 0
            )
            result[external_id] = {
                "balance": balance,
                "paid": paid,
                "received_at": row.received_at,
            }
        return result

    async def sum_accounting_totals_by_patient(
        self,
        tenant_id: TenantId,
        patient_ids: Sequence[str],
        *,
        transaction_codes: Sequence[str],
    ) -> dict[str, float]:
        """Sum accounting-journal amounts per patient for a transaction-code set.

        Used by the per-person financial summary (ENG-306) for the Billed
        (``PROCEDURECOMPLETED``) and Adjustments (``PATIENTADJUSTMENT`` +
        ``FEEUPDATION``) columns. Walks
        ``carestack.accounting_transaction.upsert`` raw_events whose
        ``payload->>'transactionCode'`` matches, deduped by ``external_id``
        (latest ``received_at`` wins — the raw feed has ~15% intentional
        duplicates). The amount is summed as signed:
        ``transactionType='debit'`` contributes ``+amount``,
        ``transactionType='credit'`` contributes ``-amount`` — so an
        Adjustments column with a refund credit nets the way an
        operator expects.

        Returns ``{patient_id: signed_total_float}``. Patients with no
        matching transaction are absent.
        """
        ids = sorted({pid for pid in patient_ids if pid})
        codes = [code for code in transaction_codes if code]
        if not ids or not codes:
            return {}

        from sqlalchemy import Numeric, case, cast, func, select

        patient_id_value = RawEvent.payload["patientId"].astext
        transaction_code_value = RawEvent.payload["transactionCode"].astext
        transaction_type_value = RawEvent.payload["transactionType"].astext
        amount_value = cast(RawEvent.payload["amount"].astext, Numeric(14, 2))

        # ENG-412: narrow to the requested patients FIRST (uses
        # ``ix_raw_event_patient_id``), then dedup with ``DISTINCT ON`` —
        # instead of computing ``max(received_at)`` per external_id across
        # the whole accounting feed and joining back. The code filter stays
        # OUTSIDE the dedup so it applies to the LATEST row per external_id
        # (matching the previous join-on-max semantics). DISTINCT ON also
        # avoids the double-count the old equality-join risked on a
        # received_at tie.
        dedup_subq = (
            for_tenant(
                select(
                    patient_id_value.label("patient_id"),
                    transaction_code_value.label("transaction_code"),
                    transaction_type_value.label("transaction_type"),
                    amount_value.label("amount"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.accounting_transaction.upsert")
            .where(RawEvent.external_id.is_not(None))
            .where(patient_id_value.in_(ids))
            .distinct(RawEvent.external_id)
            .order_by(RawEvent.external_id, RawEvent.received_at.desc())
            .subquery()
        )

        signed_amount = case(
            (func.lower(dedup_subq.c.transaction_type) == "credit", -dedup_subq.c.amount),
            else_=dedup_subq.c.amount,
        )

        stmt = (
            select(
                dedup_subq.c.patient_id,
                func.coalesce(func.sum(signed_amount), 0).label("total"),
            )
            .where(dedup_subq.c.transaction_code.in_(codes))
            .group_by(dedup_subq.c.patient_id)
        )

        result: dict[str, float] = {}
        for row in (await self._session.execute(stmt)).all():
            patient_id = row.patient_id
            if patient_id is None:
                continue
            result[patient_id] = float(row.total or 0)
        return result

    async def list_carestack_patients_with_payment_activity(
        self,
        tenant_id: TenantId,
        *,
        payment_codes: Sequence[str],
        limit: int,
    ) -> list[SourceLink]:
        """Return CareStack patient ``SourceLink`` rows with payment activity (ENG-307).

        Filters ``identity.source_link`` to the CS patient links whose
        ``source_id`` appears in the distinct set of
        ``payload->>'patientId'`` values across the tenant's
        ``carestack.accounting_transaction.upsert`` raw_events whose
        ``payload->>'transactionCode'`` is in the provided allow-list.

        Used by the ``--only-with-payments`` path of
        ``infra/scripts/backfill_payment_summary.py``. On the prod tenant
        we have ~55,677 linked CareStack patients but only ~1803 with
        any payment activity, and the default
        :meth:`IdentityRepository.list_source_links_for_dashboard`
        ordering (``first_seen_at DESC``) misses most of the active set
        under ``--max-patients 2000``. This resolver targets the
        active set directly so the throttled sweep covers it.

        The ``payment_codes`` set must match the codes the accounting
        ingest service treats as payment-related (see
        :data:`packages.ingest.carestack_accounting_transaction_service._PAYMENT_CODE_TO_KIND`
        + :data:`packages.ingest.carestack_accounting_transaction_service._REFUND_TRANSACTION_CODES`).
        The caller hard-codes / imports those values so this method
        stays a pure SQL utility.

        Returns up to ``limit`` rows, ordered ``first_seen_at DESC, id
        DESC`` — same envelope as ``list_source_links_for_dashboard`` so
        the caller's extraction loop is unchanged. Tenant-scoped on both
        the raw-event filter and the source_link select; no cross-tenant
        patient_id collision can surface.
        """
        # Localised import: ``packages.identity.models`` is the only
        # identity surface this method needs. Importing at module load
        # would create a layering dependency for every IngestRepository
        # consumer, even those that never touch source_link.
        from packages.identity.models import SourceLink

        codes = [code for code in payment_codes if code]
        if not codes:
            return []

        patient_id_value = RawEvent.payload["patientId"].astext
        transaction_code_value = RawEvent.payload["transactionCode"].astext

        has_payments_subq = (
            for_tenant(
                select(patient_id_value.label("patient_id")),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.accounting_transaction.upsert")
            .where(transaction_code_value.in_(codes))
            .where(patient_id_value.is_not(None))
            .distinct()
        )

        stmt = (
            for_tenant(select(SourceLink), tenant_id, SourceLink)
            .where(SourceLink.source_system == "carestack")
            .where(SourceLink.source_kind == "patient")
            .where(SourceLink.source_id.in_(has_payments_subq))
            .order_by(SourceLink.first_seen_at.desc(), SourceLink.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_unresolved_hints(
        self, tenant_id: TenantId, limit: int = 100
    ) -> list[NormalizedPersonHint]:
        """Return hints not yet linked to a ``person_uid``, oldest first.

        ``person_uid IS NULL`` is the matching backlog the identity match
        policy (ENG-185) will drain. Ordering by ``observed_at`` keeps
        first-observed-first-decided semantics.
        """
        stmt = (
            for_tenant(select(NormalizedPersonHint), tenant_id, NormalizedPersonHint)
            .where(NormalizedPersonHint.person_uid.is_(None))
            .order_by(NormalizedPersonHint.observed_at.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # ----------------------------------------------------- ENG-308 CareStack providers

    async def upsert_providers(
        self,
        tenant_id: TenantId,
        providers: Sequence[dict[str, Any]],
    ) -> int:
        """Idempotent upsert of CareStack provider rows (ENG-308).

        Keyed on ``(tenant_id, provider_carestack_id)``. The verbatim
        provider payload is kept under ``payload`` so future column
        extensions don't require a re-pull. Returns the number of input
        rows persisted (insert OR update).

        Empty input short-circuits without SQL — the backfill resolver
        page may be empty.
        """
        if not providers:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # Dedup by provider id so Postgres ON CONFLICT fires at most once
        # per key in a single command (otherwise it raises
        # ``cardinality_violation``).
        seen: set[int] = set()
        rows: list[dict[str, Any]] = []
        for entry in providers:
            raw_id = entry.get("id")
            if raw_id is None:
                continue
            try:
                provider_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if provider_id in seen:
                continue
            seen.add(provider_id)

            def _str_or_none(value: Any) -> str | None:
                if value is None:
                    return None
                text = str(value).strip()
                return text or None

            is_active_raw = entry.get("isActive")
            is_active = bool(is_active_raw) if is_active_raw is not None else True

            rows.append(
                {
                    "tenant_id": tenant_id,
                    "provider_carestack_id": provider_id,
                    "first_name": _str_or_none(entry.get("firstName")),
                    "last_name": _str_or_none(entry.get("lastName")),
                    "middle_name": _str_or_none(entry.get("middleName")),
                    "short_name": _str_or_none(entry.get("shortName")),
                    "provider_type": _str_or_none(entry.get("providerType")),
                    "is_active": is_active,
                    "payload": dict(entry),
                }
            )

        if not rows:
            return 0

        stmt = pg_insert(CareStackProvider).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_carestack_provider_tenant_provider_id",
            set_={
                "first_name": stmt.excluded.first_name,
                "last_name": stmt.excluded.last_name,
                "middle_name": stmt.excluded.middle_name,
                "short_name": stmt.excluded.short_name,
                "provider_type": stmt.excluded.provider_type,
                "is_active": stmt.excluded.is_active,
                "payload": stmt.excluded.payload,
            },
        )
        await self._session.execute(stmt)
        return len(rows)

    async def list_provider_directory(
        self, tenant_id: TenantId
    ) -> dict[int, str]:
        """Return ``{provider_carestack_id: display_name}`` for ALL providers.

        Used by the analytics doctor-actor backfill (ENG-510) to link every
        CareStack provider in the directory to an ``actor.actor`` (kind
        ``carestack_provider_id``) with a proper "Dr First Last" name — not just
        the providers already seen on a consult. Display-name policy mirrors
        :meth:`lookup_provider_names`.
        """
        stmt = for_tenant(
            select(
                CareStackProvider.provider_carestack_id,
                CareStackProvider.first_name,
                CareStackProvider.last_name,
                CareStackProvider.short_name,
                CareStackProvider.provider_type,
            ),
            tenant_id,
            CareStackProvider,
        )
        out: dict[int, str] = {}
        for row in (await self._session.execute(stmt)).all():
            name = _format_provider_display_name(
                first_name=row.first_name,
                last_name=row.last_name,
                short_name=row.short_name,
                provider_type=row.provider_type,
                provider_id=row.provider_carestack_id,
            )
            if name is not None:
                out[row.provider_carestack_id] = name
        return out

    async def lookup_provider_names(
        self,
        tenant_id: TenantId,
        provider_ids: Iterable[int],
    ) -> dict[int, str]:
        """Return ``{provider_carestack_id: display_name}`` for the requested ids.

        Display-name policy (ENG-308):
        * "Dr First Last" when ``provider_type`` looks like a doctor
          (``doctor`` / ``dr`` / ``dds`` / ``md`` substring, case-insensitive).
        * "First Last" otherwise (or just whichever name part is non-empty).
        * Falls back to ``shortName`` then ``f"Provider #{id}"`` when both
          firstName + lastName are absent.

        Empty input short-circuits without SQL — empty pages should not
        pay a DB round-trip.
        """
        wanted = sorted({int(pid) for pid in provider_ids if pid is not None})
        if not wanted:
            return {}

        stmt = (
            for_tenant(
                select(
                    CareStackProvider.provider_carestack_id,
                    CareStackProvider.first_name,
                    CareStackProvider.last_name,
                    CareStackProvider.short_name,
                    CareStackProvider.provider_type,
                ),
                tenant_id,
                CareStackProvider,
            )
            .where(CareStackProvider.provider_carestack_id.in_(wanted))
        )

        out: dict[int, str] = {}
        for row in (await self._session.execute(stmt)).all():
            name = _format_provider_display_name(
                first_name=row.first_name,
                last_name=row.last_name,
                short_name=row.short_name,
                provider_type=row.provider_type,
                provider_id=row.provider_carestack_id,
            )
            if name is not None:
                out[row.provider_carestack_id] = name
        return out

    async def person_carestack_origin_context(
        self,
        tenant_id: TenantId,
        patient_ids: Sequence[str],
        *,
        provider_name_resolver: Callable[
            [Iterable[int]], Awaitable[dict[int, str]]
        ]
        | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Per-CareStack-patient-id origin context (ENG-308).

        Returns ``{patient_id: {earliest_activity_at, latest_activity_at,
        default_location_id, default_provider_id, city, state}}`` —
        empty dict when the input is empty.

        Tenant-scoped via :func:`for_tenant`. The earliest/latest
        anchors come from BOTH ``carestack.appointment.upsert``
        ``payload->>'createdOn'`` AND
        ``carestack.accounting_transaction.upsert``
        ``payload->>'TransactionDate'`` — these are the two raw_event
        types that documentation confirms carry a CareStack-side activity
        timestamp. Each per-(patient, event_type) row is deduped by
        ``external_id`` (latest ``received_at`` wins) so the ~15%
        intentional duplicates in the accounting feed do not throw the
        MIN/MAX off.

        ``default_location_id`` / ``default_provider_id`` and the
        address city/state come from the LATEST
        ``carestack.patient.upsert`` row per ``patientId``. Address read
        is deliberately limited to city + state — HIPAA Safe Harbor.

        ``provider_name_resolver`` is optional; when not supplied the
        caller is expected to resolve provider names itself (the service
        layer does this).
        """
        from sqlalchemy import DateTime as SADateTime
        from sqlalchemy import cast as sa_cast

        ids = sorted({pid for pid in patient_ids if pid})
        if not ids:
            return {}

        # ENG-412: each of the three reads narrows by the requested patient
        # ids FIRST (``ix_raw_event_patient_id`` for appt/txn,
        # ``ix_raw_event_dedup`` for patient) then dedups with ``DISTINCT
        # ON (external_id)`` — instead of a max(received_at) GROUP BY over
        # the whole event type joined back. ``_fold_activity`` skips a None
        # ``activity_at``, so the previous post-join ``createdOn IS NOT
        # NULL`` / ``TransactionDate IS NOT NULL`` guards are unnecessary:
        # the latest row is taken and a null timestamp folds to a no-op,
        # exactly as before.

        # --- earliest/latest from appointment.upsert payload->>'createdOn'
        appt_created_on = RawEvent.payload["createdOn"].astext
        appt_stmt = (
            for_tenant(
                select(
                    RawEvent.payload["patientId"].astext.label("patient_id"),
                    sa_cast(appt_created_on, SADateTime(timezone=True)).label(
                        "activity_at"
                    ),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.appointment.upsert")
            .where(RawEvent.external_id.is_not(None))
            .where(RawEvent.payload["patientId"].astext.in_(ids))
            .distinct(RawEvent.external_id)
            .order_by(RawEvent.external_id, RawEvent.received_at.desc())
        )

        # --- earliest/latest from accounting_transaction.upsert
        # payload->>'TransactionDate' (spec confirms no createdOn here).
        txn_date = RawEvent.payload["TransactionDate"].astext
        txn_stmt = (
            for_tenant(
                select(
                    RawEvent.payload["patientId"].astext.label("patient_id"),
                    sa_cast(txn_date, SADateTime(timezone=True)).label("activity_at"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.accounting_transaction.upsert")
            .where(RawEvent.external_id.is_not(None))
            .where(RawEvent.payload["patientId"].astext.in_(ids))
            .distinct(RawEvent.external_id)
            .order_by(RawEvent.external_id, RawEvent.received_at.desc())
        )

        # --- latest patient.upsert per patientId for address + defaults.
        # The patient ingest sets ``external_id`` to the patientId, so we
        # narrow by ``external_id IN (ids)`` (``ix_raw_event_dedup``) and
        # keep the latest row per id with ``DISTINCT ON`` (ENG-412).
        patient_stmt = (
            for_tenant(
                select(
                    RawEvent.external_id.label("patient_id"),
                    RawEvent.payload["defaultLocationId"].astext.label(
                        "default_location_id"
                    ),
                    RawEvent.payload["defaultProviderId"].astext.label(
                        "default_provider_id"
                    ),
                    RawEvent.payload["addressDetail"]["city"].astext.label("city"),
                    RawEvent.payload["addressDetail"]["state"].astext.label("state"),
                    # ENG-310 per-pid identity / patient details.
                    RawEvent.payload["firstName"].astext.label("first_name"),
                    RawEvent.payload["lastName"].astext.label("last_name"),
                    RawEvent.payload["dateOfBirth"].astext.label("dob"),
                    RawEvent.payload["gender"].astext.label("gender"),
                    RawEvent.payload["maritalStatus"].astext.label(
                        "marital_status"
                    ),
                    RawEvent.payload["mobile"].astext.label("mobile"),
                    RawEvent.payload["phoneWithExt"].astext.label("phone_with_ext"),
                    RawEvent.payload["workPhoneWithExt"].astext.label(
                        "work_phone_with_ext"
                    ),
                    RawEvent.payload["email"].astext.label("email"),
                    RawEvent.payload["addressDetail"]["addressLine1"].astext.label(
                        "address_line1"
                    ),
                    RawEvent.payload["addressDetail"]["addressLine2"].astext.label(
                        "address_line2"
                    ),
                    RawEvent.payload["addressDetail"]["zipCode"].astext.label(
                        "address_zip"
                    ),
                    RawEvent.payload["patientIdentifier"].astext.label(
                        "patient_identifier"
                    ),
                    RawEvent.payload["accountId"].astext.label("account_id"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.patient.upsert")
            .where(RawEvent.external_id.in_(ids))
            .distinct(RawEvent.external_id)
            .order_by(RawEvent.external_id, RawEvent.received_at.desc())
        )

        # Initialise the result with empty per-pid records so callers
        # downstream don't have to re-check `.get(pid, default)`.
        result: dict[str, dict[str, Any]] = {
            pid: {
                "earliest_activity_at": None,
                "latest_activity_at": None,
                "default_location_id": None,
                "default_provider_id": None,
                "city": None,
                "state": None,
                "first_name": None,
                "last_name": None,
                "dob": None,
                "gender": None,
                "marital_status": None,
                "mobile": None,
                "phone_with_ext": None,
                "work_phone_with_ext": None,
                "email": None,
                "address_line1": None,
                "address_line2": None,
                "address_zip": None,
                "patient_identifier": None,
                "account_id": None,
            }
            for pid in ids
        }

        def _fold_activity(row_patient: str | None, row_at: datetime | None) -> None:
            if row_patient is None or row_at is None:
                return
            bucket = result.get(row_patient)
            if bucket is None:
                return
            current_min = bucket["earliest_activity_at"]
            current_max = bucket["latest_activity_at"]
            if current_min is None or row_at < current_min:
                bucket["earliest_activity_at"] = row_at
            if current_max is None or row_at > current_max:
                bucket["latest_activity_at"] = row_at

        for row in (await self._session.execute(appt_stmt)).all():
            _fold_activity(row.patient_id, row.activity_at)
        for row in (await self._session.execute(txn_stmt)).all():
            _fold_activity(row.patient_id, row.activity_at)

        def _int_or_none(value: object) -> int | None:
            if value is None:
                return None
            try:
                return int(str(value).strip())
            except (TypeError, ValueError):
                return None

        def _str_or_none(value: object) -> str | None:
            if not isinstance(value, str):
                return None
            text = value.strip()
            return text or None

        for row in (await self._session.execute(patient_stmt)).all():
            bucket = result.get(row.patient_id)
            if bucket is None:
                continue
            bucket["default_location_id"] = _int_or_none(row.default_location_id)
            bucket["default_provider_id"] = _int_or_none(row.default_provider_id)
            bucket["city"] = _str_or_none(row.city)
            bucket["state"] = _str_or_none(row.state)
            # ENG-310 patient details. ``dateOfBirth`` arrives as an
            # ISO-8601 date or datetime string in the CareStack payload;
            # we forward the raw value so the frontend can pick the
            # display format (date-only vs. localised).
            bucket["first_name"] = _str_or_none(row.first_name)
            bucket["last_name"] = _str_or_none(row.last_name)
            bucket["dob"] = _str_or_none(row.dob)
            bucket["gender"] = _str_or_none(row.gender)
            bucket["marital_status"] = _str_or_none(row.marital_status)
            bucket["mobile"] = _str_or_none(row.mobile)
            bucket["phone_with_ext"] = _str_or_none(row.phone_with_ext)
            bucket["work_phone_with_ext"] = _str_or_none(row.work_phone_with_ext)
            bucket["email"] = _str_or_none(row.email)
            bucket["address_line1"] = _str_or_none(row.address_line1)
            bucket["address_line2"] = _str_or_none(row.address_line2)
            bucket["address_zip"] = _str_or_none(row.address_zip)
            bucket["patient_identifier"] = _str_or_none(row.patient_identifier)
            bucket["account_id"] = _str_or_none(row.account_id)

        if provider_name_resolver is not None:
            wanted_provider_ids = [
                bucket["default_provider_id"]
                for bucket in result.values()
                if bucket["default_provider_id"] is not None
            ]
            if wanted_provider_ids:
                names = await provider_name_resolver(wanted_provider_ids)
                for bucket in result.values():
                    pid = bucket["default_provider_id"]
                    if pid is not None and pid in names:
                        bucket["default_provider_name"] = names[pid]

        return result


    async def person_household_members(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[dict[str, str | None]]:
        """Return OTHER persons in this tenant sharing a normalised phone/email (ENG-310).

        Household resolver. Reads the verbatim
        ``carestack.patient.upsert`` payload — NOT
        ``identity.person_identifier``: the global
        ``UNIQUE(kind, value)`` constraint puts a shared phone on a
        single Person row after ENG-311, so PersonIdentifier would miss
        the siblings.

        The household key is the union of normalised phone (digits-only)
        OR lowered email. ``accountId`` is FORBIDDEN (clinic-level
        default value worth ~55K patients).

        Algorithm (tenant-scoped throughout):

        1. Resolve THIS person's CareStack patient_ids from
           ``identity.source_link``.
        2. Read the latest ``carestack.patient.upsert`` payload per
           self-pid; normalise its phones (``mobile`` /
           ``phoneWithExt`` / ``workPhoneWithExt``) and email.
        3. Find OTHER patient.upsert rows (latest per external_id)
           whose payload contains a digit substring (last-7 of any
           normalised self-phone) OR an exact lowered email match.
           This is a SQL pre-filter; final confirmation is in Python
           against the normalised sets.
        4. Resolve each candidate pid → ``identity.source_link.person_uid``;
           exclude the input person; dedup by sibling person_uid.
        5. Display-name preference: ``identity.person`` then CareStack
           payload ``firstName + lastName``.

        Query-cost bound: the pre-filter is a tenant-scoped seq-scan of
        the latest patient.upsert per external_id (~60K rows in prod),
        with the join on ``MAX(received_at) GROUP BY external_id``
        identical to the existing ``person_carestack_origin_context``
        aggregator. PostgreSQL evaluates the OR-of-ILIKEs server-side
        and returns ONLY rows that contain at least one substring
        match; for a real household the candidate count is in the low
        single digits. Python then normalises and confirms — no
        50K-row Python-side scan.

        Returns ``[{person_uid, display_name, shared_via,
        shared_value_masked}]``. Empty input or zero matches → ``[]``.
        """
        # Local import — packages.ingest may read identity, but the
        # module-top import would force every IngestRepository consumer
        # to pull in identity even when they never reach this method.
        from sqlalchemy import or_

        from packages.core.exceptions import ValidationError
        from packages.identity.models import Person, SourceLink
        from packages.identity.service import normalise_email, normalise_phone

        # 1. Self pids.
        self_pids_stmt = (
            for_tenant(select(SourceLink.source_id), tenant_id, SourceLink)
            .where(SourceLink.person_uid == person_uid)
            .where(SourceLink.source_system == "carestack")
            .where(SourceLink.source_kind == "patient")
            .where(SourceLink.source_id.is_not(None))
        )
        self_pids = sorted(
            {
                row[0]
                for row in (await self._session.execute(self_pids_stmt)).all()
                if row[0]
            }
        )
        if not self_pids:
            return []

        # 2. Read latest patient.upsert per self-pid → normalised
        #    phones + emails.
        self_latest_subq = (
            for_tenant(
                select(
                    RawEvent.external_id,
                    func.max(RawEvent.received_at).label("latest_received_at"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.patient.upsert")
            .where(RawEvent.external_id.in_(self_pids))
            .group_by(RawEvent.external_id)
            .subquery()
        )
        self_payload_stmt = (
            for_tenant(
                select(
                    RawEvent.payload["mobile"].astext.label("mobile"),
                    RawEvent.payload["phoneWithExt"].astext.label("phone_with_ext"),
                    RawEvent.payload["workPhoneWithExt"].astext.label(
                        "work_phone_with_ext"
                    ),
                    RawEvent.payload["email"].astext.label("email"),
                ),
                tenant_id,
                RawEvent,
            )
            .join(
                self_latest_subq,
                (RawEvent.external_id == self_latest_subq.c.external_id)
                & (
                    RawEvent.received_at
                    == self_latest_subq.c.latest_received_at
                ),
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.patient.upsert")
        )

        self_phones: set[str] = set()
        self_emails: set[str] = set()
        for row in (await self._session.execute(self_payload_stmt)).all():
            for raw_phone in (row.mobile, row.phone_with_ext, row.work_phone_with_ext):
                if not raw_phone:
                    continue
                try:
                    self_phones.add(normalise_phone(raw_phone))
                except ValidationError:  # noqa: S112 — invalid phone, skip silently
                    continue
            if row.email:
                try:
                    self_emails.add(normalise_email(row.email))
                except ValidationError:  # noqa: S112 — invalid email, skip silently
                    continue

        if not self_phones and not self_emails:
            return []

        # 3. Candidate query — patient.upsert rows (excluding self_pids)
        #    whose payload contains a phone-digit substring or matches an
        #    email.
        last7s = sorted({digits[-7:] for digits in self_phones if len(digits) >= 7})
        emails_lower = sorted(self_emails)

        # CareStack stores FORMATTED phones, e.g. "(916) 215-4258". The
        # pre-filter must compare against a digits-only projection of the
        # payload phone — otherwise a normalized last-7 like "2154258"
        # never substring-matches "(916) 215-4258" (the dash breaks it),
        # the candidate set is empty, and no household sibling is ever
        # found. regexp_replace strips every non-digit before the LIKE.
        # The expression matches ``ix_raw_event_cs_patient_*_trgm`` /
        # ``ix_raw_event_cs_patient_email_lower`` exactly so the OR resolves
        # to a BitmapOr of index scans (ENG-412).
        def _digits_only(field: str) -> Any:
            return func.regexp_replace(
                RawEvent.payload[field].astext, r"\D", "", "g"
            )

        or_clauses: list[Any] = []
        for last7 in last7s:
            pattern = f"%{last7}%"
            or_clauses.append(_digits_only("mobile").ilike(pattern))
            or_clauses.append(_digits_only("phoneWithExt").ilike(pattern))
            or_clauses.append(_digits_only("workPhoneWithExt").ilike(pattern))
        for email in emails_lower:
            or_clauses.append(
                func.lower(RawEvent.payload["email"].astext) == email
            )

        if not or_clauses:
            return []

        # ENG-412: narrow to the matched pids via an indexed BitmapOr
        # subquery (the trgm phone + email partial indexes), then keep the
        # latest patient.upsert row per matched external_id with DISTINCT
        # ON — instead of a max(received_at) GROUP BY over every
        # patient.upsert row. ``correlate(None)`` keeps the subquery's own
        # FROM so it stays an independent IN-list, not a correlated
        # reference to the outer raw_event (same physical table). The
        # Python confirm below re-checks the match against this latest row,
        # so a pid whose match exists only in stale history is dropped —
        # identical result to the previous join-on-max form, which also
        # required the latest row to match.
        matched_pids_subq = (
            for_tenant(select(RawEvent.external_id), tenant_id, RawEvent)
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.patient.upsert")
            .where(RawEvent.external_id.is_not(None))
            .where(RawEvent.external_id.notin_(self_pids))
            .where(or_(*or_clauses))
            .correlate(None)
        )

        candidate_stmt = (
            for_tenant(
                select(
                    RawEvent.external_id.label("patient_id"),
                    RawEvent.payload["mobile"].astext.label("mobile"),
                    RawEvent.payload["phoneWithExt"].astext.label("phone_with_ext"),
                    RawEvent.payload["workPhoneWithExt"].astext.label(
                        "work_phone_with_ext"
                    ),
                    RawEvent.payload["email"].astext.label("email"),
                    RawEvent.payload["firstName"].astext.label("first_name"),
                    RawEvent.payload["lastName"].astext.label("last_name"),
                ),
                tenant_id,
                RawEvent,
            )
            .where(RawEvent.source == "carestack")
            .where(RawEvent.event_type == "carestack.patient.upsert")
            .where(RawEvent.external_id.in_(matched_pids_subq))
            .distinct(RawEvent.external_id)
            .order_by(RawEvent.external_id, RawEvent.received_at.desc())
        )

        # 4. Python confirm + collect per-pid signals.
        per_pid_shared: dict[str, dict[str, object]] = {}
        for row in (await self._session.execute(candidate_stmt)).all():
            candidate_phones: set[str] = set()
            for raw_phone in (row.mobile, row.phone_with_ext, row.work_phone_with_ext):
                if not raw_phone:
                    continue
                try:
                    candidate_phones.add(normalise_phone(raw_phone))
                except ValidationError:  # noqa: S112 — invalid phone, skip silently
                    continue
            shared_phones = candidate_phones & self_phones

            candidate_email: str | None = None
            if row.email:
                try:
                    candidate_email = normalise_email(row.email)
                except ValidationError:
                    candidate_email = None
            shared_email_match = (
                candidate_email if candidate_email in self_emails else None
            )

            if not shared_phones and shared_email_match is None:
                continue

            via_phone = bool(shared_phones)
            via_email = shared_email_match is not None
            if via_phone and via_email:
                shared_via = "both"
            elif via_phone:
                shared_via = "phone"
            else:
                shared_via = "email"

            if via_phone:
                shared_value_masked = _mask_phone(next(iter(shared_phones)))
            else:
                assert shared_email_match is not None
                shared_value_masked = _mask_email(shared_email_match)

            per_pid_shared[row.patient_id] = {
                "shared_via": shared_via,
                "shared_value_masked": shared_value_masked,
                "payload_first_name": (
                    row.first_name.strip()
                    if isinstance(row.first_name, str) and row.first_name.strip()
                    else None
                ),
                "payload_last_name": (
                    row.last_name.strip()
                    if isinstance(row.last_name, str) and row.last_name.strip()
                    else None
                ),
            }

        if not per_pid_shared:
            return []

        # 5. Map matched pids → SourceLink.person_uid (tenant-scoped),
        #    exclude self person, dedup.
        candidate_pids = sorted(per_pid_shared.keys())
        sibling_link_stmt = (
            for_tenant(
                select(SourceLink.source_id, SourceLink.person_uid),
                tenant_id,
                SourceLink,
            )
            .where(SourceLink.source_system == "carestack")
            .where(SourceLink.source_kind == "patient")
            .where(SourceLink.source_id.in_(candidate_pids))
            .where(SourceLink.person_uid != person_uid)
        )
        # Many pids may resolve to the same sibling; keep the FIRST
        # signal we see per sibling so the masked-value display stays
        # deterministic.
        per_sibling: dict[UUID, dict[str, object]] = {}
        for row in (await self._session.execute(sibling_link_stmt)).all():
            sibling_uid: UUID = row.person_uid
            signal = per_pid_shared.get(row.source_id)
            if signal is None:
                continue
            if sibling_uid in per_sibling:
                continue
            per_sibling[sibling_uid] = signal

        if not per_sibling:
            return []

        # 6. Display-name resolution from identity.person (batched).
        sibling_uids = list(per_sibling.keys())
        person_name_stmt = (
            for_tenant(
                select(
                    Person.id,
                    Person.given_name,
                    Person.family_name,
                    Person.display_name,
                ),
                tenant_id,
                Person,
            )
            .where(Person.id.in_(sibling_uids))
        )
        identity_names: dict[UUID, str] = {}
        for row in (await self._session.execute(person_name_stmt)).all():
            display = _person_display_name(
                given_name=row.given_name,
                family_name=row.family_name,
                display_name=row.display_name,
            )
            if display is not None:
                identity_names[row.id] = display

        results: list[dict[str, str | None]] = []
        for sibling_uid in sibling_uids:
            signal = per_sibling[sibling_uid]
            display = identity_names.get(sibling_uid)
            if display is None:
                payload_first = signal.get("payload_first_name")
                payload_last = signal.get("payload_last_name")
                parts = [
                    p
                    for p in (payload_first, payload_last)
                    if isinstance(p, str) and p
                ]
                display = " ".join(parts) if parts else None
            shared_via_val = signal["shared_via"]
            shared_value_masked_val = signal["shared_value_masked"]
            assert isinstance(shared_via_val, str)
            assert isinstance(shared_value_masked_val, str)
            results.append(
                {
                    "person_uid": str(sibling_uid),
                    "display_name": display,
                    "shared_via": shared_via_val,
                    "shared_value_masked": shared_value_masked_val,
                }
            )
        return results

    async def person_household_members_by_identifier(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[dict[str, str | None]]:
        """OTHER persons sharing a phone (last-7 digits) or email via
        ``identity.person_identifier`` (ENG-463).

        Complements :meth:`person_household_members` (which is
        CareStack-payload based) so households among Salesforce-lead-only
        persons — who have no CareStack patient row — also surface in the
        card. Phone match is on the **last 7 digits** so cross-form
        numbers (``9258125438`` vs ``19258125438``) still link before the
        E.164 backfill lands. Returns the same
        ``{person_uid, display_name, shared_via, shared_value_masked}``
        shape; never returns the input person.

        Known limit (ENG-341): when two persons hold the **byte-identical**
        normalised value, identity skips the second identifier row (the
        global ``UNIQUE(kind, value)`` constraint), so that sibling is
        invisible here. The current household population is visible
        precisely because it is stored in *different* forms (10- vs
        11-digit) — once ENG-341 makes shared contacts first-class, fold
        the skipped-identifier case in (payload/hint-derived).
        """
        import re

        from sqlalchemy import func, or_

        from packages.core.exceptions import ValidationError
        from packages.identity.models import Person, PersonIdentifier
        from packages.identity.service import normalise_phone

        self_stmt = for_tenant(
            select(PersonIdentifier.kind, PersonIdentifier.value),
            tenant_id,
            PersonIdentifier,
        ).where(PersonIdentifier.person_id == person_uid)
        self_last7: set[str] = set()
        self_canonical: set[str] = set()
        self_emails: set[str] = set()
        for kind, value in (await self._session.execute(self_stmt)).all():
            if not value:
                continue
            if kind == "phone":
                digits = re.sub(r"\D", "", value)
                if len(digits) >= 7:
                    self_last7.add(digits[-7:])
                try:
                    self_canonical.add(normalise_phone(value))
                except ValidationError:  # noqa: S110 — junk phone, skip
                    pass
            elif kind == "email":
                self_emails.add(value.strip().lower())
        if not self_last7 and not self_emails:
            return []

        phone_last7 = func.right(
            func.regexp_replace(PersonIdentifier.value, r"\D", "", "g"), 7
        )
        conds = []
        if self_last7:
            conds.append(
                (PersonIdentifier.kind == "phone") & phone_last7.in_(self_last7)
            )
        if self_emails:
            conds.append(
                (PersonIdentifier.kind == "email")
                & func.lower(PersonIdentifier.value).in_(self_emails)
            )
        cand_stmt = (
            for_tenant(
                select(
                    PersonIdentifier.person_id,
                    PersonIdentifier.kind,
                    PersonIdentifier.value,
                ),
                tenant_id,
                PersonIdentifier,
            )
            .where(or_(*conds))
            .where(PersonIdentifier.person_id != person_uid)
        )
        # Prefer a phone signal over email when a sibling matches on both.
        # The last-7 SQL filter is only a cheap pre-filter — confirm each
        # phone candidate in Python by full E.164 equality so unrelated
        # numbers that merely share the last 7 digits are dropped (the
        # same pre-filter-then-confirm pattern as the CareStack resolver).
        per_sibling: dict[UUID, tuple[str, str]] = {}
        for person_id, kind, value in (
            await self._session.execute(cand_stmt)
        ).all():
            if per_sibling.get(person_id, ("", ""))[0] == "phone":
                continue
            if kind == "phone":
                try:
                    canonical = normalise_phone(value or "")
                except ValidationError:  # noqa: S112 — junk phone, skip
                    continue
                if canonical not in self_canonical:
                    continue  # last-7 collision with an unrelated number
                digits = re.sub(r"\D", "", value or "")
                per_sibling[person_id] = ("phone", _mask_phone(digits))
            elif kind == "email" and person_id not in per_sibling:
                per_sibling[person_id] = (
                    "email",
                    _mask_email((value or "").strip().lower()),
                )
        if not per_sibling:
            return []

        name_stmt = for_tenant(
            select(
                Person.id,
                Person.given_name,
                Person.family_name,
                Person.display_name,
            ),
            tenant_id,
            Person,
        ).where(Person.id.in_(list(per_sibling.keys())))
        names: dict[UUID, str | None] = {}
        for row in (await self._session.execute(name_stmt)).all():
            names[row.id] = _person_display_name(
                given_name=row.given_name,
                family_name=row.family_name,
                display_name=row.display_name,
            )
        return [
            {
                "person_uid": str(sib),
                "display_name": names.get(sib),
                "shared_via": via,
                "shared_value_masked": masked,
            }
            for sib, (via, masked) in per_sibling.items()
        ]

    async def person_household_members_by_hint(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[dict[str, str | None]]:
        """OTHER persons sharing a normalised phone/email via
        ``ingest.normalized_person_hint`` (ENG-542).

        Complements :meth:`person_household_members` (CareStack-payload based)
        and :meth:`person_household_members_by_identifier`
        (``identity.person_identifier`` based) by surfacing siblings whose
        shared phone/email lives ONLY in a normalized person hint. This is the
        Salesforce-lead case where the matcher created a SEPARATE, NON-merged
        person but never persisted the shared phone as an identifier — the
        global ``UNIQUE(kind, value)`` constraint blocks a second identifier
        row holding the byte-identical value (see ``packages/identity``
        ENG-340; the constraint rework is ENG-341). The hint row, captured
        verbatim from the lead, still carries ``phone_normalized`` /
        ``email_normalized`` so the shared contact stays visible on the card
        even when the records are not merged.

        A hint carries no ``person_uid`` of its own, so it is mapped back to a
        person through ``identity.source_link`` on the
        ``(source_system, source_instance, source_kind, source_id)`` key.

        Symmetric by construction: BOTH the self-value set and the sibling
        search read the union of ``person_identifier`` AND
        ``normalized_person_hint``, so A-shows-B iff B-shows-A regardless of
        which side stored the value as an identifier vs a hint.

        Returns the same ``{person_uid, display_name, shared_via,
        shared_value_masked}`` shape; never returns the input person. Empty
        when the person has no phone/email in either store, or no sibling.
        """
        import re

        from sqlalchemy import or_

        from packages.identity.models import Person, PersonIdentifier, SourceLink
        from packages.ingest.models import NormalizedPersonHint

        # 1. Self phone/email values — union of identifiers + hints.
        self_phones: set[str] = set()
        self_emails: set[str] = set()

        ident_self_stmt = for_tenant(
            select(PersonIdentifier.kind, PersonIdentifier.value),
            tenant_id,
            PersonIdentifier,
        ).where(PersonIdentifier.person_id == person_uid)
        for kind, value in (await self._session.execute(ident_self_stmt)).all():
            if not value:
                continue
            if kind == "phone":
                self_phones.add(value)
            elif kind == "email":
                self_emails.add(value.strip().lower())

        hint_self_stmt = (
            for_tenant(
                select(
                    NormalizedPersonHint.phone_normalized,
                    NormalizedPersonHint.email_normalized,
                ),
                tenant_id,
                NormalizedPersonHint,
            )
            .join(
                SourceLink,
                (SourceLink.source_system == NormalizedPersonHint.source_system)
                & (
                    SourceLink.source_instance
                    == NormalizedPersonHint.source_instance
                )
                & (SourceLink.source_kind == NormalizedPersonHint.source_kind)
                & (SourceLink.source_id == NormalizedPersonHint.source_id),
            )
            .where(SourceLink.tenant_id == tenant_id)
            .where(SourceLink.person_uid == person_uid)
        )
        for phone_n, email_n in (
            await self._session.execute(hint_self_stmt)
        ).all():
            if phone_n:
                self_phones.add(phone_n)
            if email_n:
                self_emails.add(email_n.strip().lower())

        if not self_phones and not self_emails:
            return []

        # 2. Siblings — other persons holding any self value in EITHER store.
        #    ``per_sibling`` maps the sibling uid -> (shared_via, masked).
        #    A phone signal always wins over an email signal for the label.
        per_sibling: dict[UUID, tuple[str, str]] = {}

        def _record(sib_uid: UUID, via: str, masked: str) -> None:
            current = per_sibling.get(sib_uid)
            if current is None or (current[0] == "email" and via == "phone"):
                per_sibling[sib_uid] = (via, masked)

        # 2a. Hint-side siblings (the lead-only case this method exists for).
        hint_conds: list[Any] = []
        if self_phones:
            hint_conds.append(
                NormalizedPersonHint.phone_normalized.in_(self_phones)
            )
        if self_emails:
            hint_conds.append(
                func.lower(NormalizedPersonHint.email_normalized).in_(self_emails)
            )
        hint_sib_stmt = (
            for_tenant(
                select(
                    SourceLink.person_uid,
                    NormalizedPersonHint.phone_normalized,
                    NormalizedPersonHint.email_normalized,
                ),
                tenant_id,
                NormalizedPersonHint,
            )
            .join(
                SourceLink,
                (SourceLink.source_system == NormalizedPersonHint.source_system)
                & (
                    SourceLink.source_instance
                    == NormalizedPersonHint.source_instance
                )
                & (SourceLink.source_kind == NormalizedPersonHint.source_kind)
                & (SourceLink.source_id == NormalizedPersonHint.source_id),
            )
            .where(SourceLink.tenant_id == tenant_id)
            .where(SourceLink.person_uid != person_uid)
            .where(or_(*hint_conds))
        )
        for sib_uid, phone_n, email_n in (
            await self._session.execute(hint_sib_stmt)
        ).all():
            if sib_uid is None:
                continue
            if phone_n and phone_n in self_phones:
                _record(sib_uid, "phone", _mask_phone(re.sub(r"\D", "", phone_n)))
            elif email_n and email_n.strip().lower() in self_emails:
                _record(sib_uid, "email", _mask_email(email_n.strip().lower()))

        # 2b. Identifier-side siblings (so a lead-only input person still sees
        #     a CareStack/identifier sibling holding the same value). The
        #     overlap with ``person_household_members_by_identifier`` is
        #     harmless — the service dedups by sibling uid.
        ident_conds: list[Any] = []
        if self_phones:
            ident_conds.append(
                (PersonIdentifier.kind == "phone")
                & PersonIdentifier.value.in_(self_phones)
            )
        if self_emails:
            ident_conds.append(
                (PersonIdentifier.kind == "email")
                & func.lower(PersonIdentifier.value).in_(self_emails)
            )
        ident_sib_stmt = (
            for_tenant(
                select(
                    PersonIdentifier.person_id,
                    PersonIdentifier.kind,
                    PersonIdentifier.value,
                ),
                tenant_id,
                PersonIdentifier,
            )
            .where(PersonIdentifier.person_id != person_uid)
            .where(or_(*ident_conds))
        )
        for sib_uid, kind, value in (
            await self._session.execute(ident_sib_stmt)
        ).all():
            if sib_uid is None or not value:
                continue
            if kind == "phone" and value in self_phones:
                _record(sib_uid, "phone", _mask_phone(re.sub(r"\D", "", value)))
            elif kind == "email" and value.strip().lower() in self_emails:
                _record(sib_uid, "email", _mask_email(value.strip().lower()))

        if not per_sibling:
            return []

        name_stmt = for_tenant(
            select(
                Person.id,
                Person.given_name,
                Person.family_name,
                Person.display_name,
            ),
            tenant_id,
            Person,
        ).where(Person.id.in_(list(per_sibling.keys())))
        names: dict[UUID, str | None] = {}
        for row in (await self._session.execute(name_stmt)).all():
            names[row.id] = _person_display_name(
                given_name=row.given_name,
                family_name=row.family_name,
                display_name=row.display_name,
            )
        return [
            {
                "person_uid": str(sib),
                "display_name": names.get(sib),
                "shared_via": via,
                "shared_value_masked": masked,
            }
            for sib, (via, masked) in per_sibling.items()
        ]

    async def lead_person_identifier_hints(
        self,
        tenant_id: TenantId,
        *,
        limit: int | None = None,
    ) -> list[tuple[UUID, str | None, str | None]]:
        """Return ``(person_uid, phone_normalized, email_normalized)`` rows for
        Salesforce-lead persons, derived from their normalized hints (ENG-542).

        The backfill source: a lead-person whose shared phone/email was never
        persisted as an ``identity.person_identifier`` (the matcher dropped it
        to avoid the global ``UNIQUE(kind, value)`` violation) still has the
        value in its ``ingest.normalized_person_hint`` row. Mapped to the
        person through ``identity.source_link`` on the external key.

        One row per ``(person, hint)``; the caller attaches idempotently and
        collision-safe via ``IdentityService.attach_identifier`` so duplicate
        rows here are harmless. Rows with neither a phone nor an email are
        excluded. Tenant-scoped on both tables.
        """
        from sqlalchemy import or_

        from packages.identity.models import SourceLink

        stmt = (
            for_tenant(
                select(
                    SourceLink.person_uid,
                    NormalizedPersonHint.phone_normalized,
                    NormalizedPersonHint.email_normalized,
                ),
                tenant_id,
                NormalizedPersonHint,
            )
            .join(
                SourceLink,
                (SourceLink.source_system == NormalizedPersonHint.source_system)
                & (
                    SourceLink.source_instance
                    == NormalizedPersonHint.source_instance
                )
                & (SourceLink.source_kind == NormalizedPersonHint.source_kind)
                & (SourceLink.source_id == NormalizedPersonHint.source_id),
            )
            .where(SourceLink.tenant_id == tenant_id)
            .where(SourceLink.source_system == "salesforce")
            .where(SourceLink.source_kind == "lead")
            .where(
                or_(
                    NormalizedPersonHint.phone_normalized.is_not(None),
                    NormalizedPersonHint.email_normalized.is_not(None),
                )
            )
            .distinct()
            .order_by(SourceLink.person_uid)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return [
            (row[0], row[1], row[2])
            for row in (await self._session.execute(stmt)).all()
        ]


def _parse_optional_int(value: str | None) -> int | None:
    """Parse a JSONB ``->>`` text scalar into an int, or ``None``.

    ``RawEvent.payload[...].astext`` yields the text form of a JSON value
    (or ``None`` when the key is absent). CareStack ids arrive as JSON
    integers, so the text is a digit string; anything unparseable (blank,
    a stray decimal, a non-numeric value) collapses to ``None`` rather than
    raising — the caller renders ``—``.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _mask_phone(digits: str) -> str:
    """Return the last-4 digit mask for a household phone, e.g. ``"···4258"``.

    The digit string is assumed already normalised; we only show the
    last four characters so the operator never sees the full number in
    the navigational hint.
    """
    tail = digits[-4:] if len(digits) >= 4 else digits
    return f"···{tail}"


def _mask_email(email: str) -> str:
    """Return the masked household email, e.g. ``"g···@gmail.com"``.

    Preserves the first character of the local part + the domain so the
    operator can tell whose email a sibling shares without seeing the
    raw alias. The local part is collapsed to a single ``···`` glyph
    so length is not leaked either. Inputs without ``@`` fall back to
    ``"···"`` (defensive — :func:`normalise_email` rejects them
    upstream).
    """
    if "@" not in email:
        return "···"
    local, _, domain = email.partition("@")
    if not local:
        return f"···@{domain}"
    return f"{local[0]}···@{domain}"


def _person_display_name(
    *,
    given_name: str | None,
    family_name: str | None,
    display_name: str | None,
) -> str | None:
    """Format an identity.person display label, given_name+family_name first."""
    parts = [
        p
        for p in (
            (given_name or "").strip(),
            (family_name or "").strip(),
        )
        if p
    ]
    if parts:
        return " ".join(parts)
    text = (display_name or "").strip()
    return text or None


def _format_provider_display_name(
    *,
    first_name: str | None,
    last_name: str | None,
    short_name: str | None,
    provider_type: str | None,
    provider_id: int,
) -> str | None:
    """Format a CareStack provider's display name per ENG-308 policy.

    * ``"Dr <First> <Last>"`` when ``provider_type`` substring suggests
      a doctor (``doctor`` / ``dr`` / ``dds`` / ``md``, case-insensitive).
    * ``"<First> <Last>"`` otherwise.
    * Falls back to whichever name part is non-empty, then ``shortName``,
      then ``f"Provider #{id}"`` so the UI always has SOMETHING to
      render.
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    short = (short_name or "").strip()
    ptype = (provider_type or "").lower()
    is_doctor = any(token in ptype for token in ("doctor", "dr", "dds", "md"))

    parts = [p for p in (first, last) if p]
    if parts:
        body = " ".join(parts)
        return f"Dr {body}" if is_doctor else body
    if short:
        return short
    return f"Provider #{provider_id}"
