"""IngestService — capture-then-route pattern.

Today this captures raw events and extracts a small, provider-neutral
``NormalizedPersonHint`` per event (ENG-185). As real integrations land
(CareStack, Salesforce), per-source handlers translate ``RawEvent`` rows
into hints and then into identity/ops domain operations and call
``mark_processed``.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument (ENG-128).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.catalog.service import CatalogService
from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.service import (
    SOURCE_KINDS,
    SOURCE_SYSTEMS,
    IdentityService,
    default_source_instance,
    normalise_email,
    normalise_phone,
)

from .models import NormalizedPersonHint, RawEvent, SourceObjectField
from .repository import IngestRepository
from .schemas import (
    CarestackOriginRowOut,
    FieldTypeChange,
    HouseholdMemberOut,
    LatestPaymentSummaryBalancesOut,
    NormalizedPersonHintIn,
    ObservedFieldIn,
    PersonPaymentFinancialSummaryOut,
    RawEventIn,
    SchemaDiffOut,
    SourceDataListOut,
    SourceDataRecordOut,
    SourceDataRelationOut,
)

_SOURCE_DATA_SOURCES = ("salesforce", "carestack")

# Module-scope logger for the per-person CareStack origin aggregator
# (ENG-308). Created at import time so the method body does not pay a
# `get_logger` call per location-resolution failure.
_origin_log = get_logger("ingest.person_carestack_origin")

# Schema-registry drift logger (ENG-426). Drift is also surfaced into
# ``sync_run.meta`` by the Block C refresh job; this structured line is the
# always-on baseline so a new/removed source field is never silent.
_schema_log = get_logger("ingest.schema_registry")

# AR-risk threshold (ENG-266) — a patient is "at AR risk" when their
# LATEST CareStack payment-summary snapshot ``balanceDuePatient`` is
# STRICTLY greater than this dollar amount. A patient exactly AT the
# threshold is excluded; the rule is "above the line, not on it".
#
# Default rationale: $500 is the order-of-magnitude where partial-
# payment plans typically stall in our clinic data. Small enough to
# surface real backlog (a $200 copay overrun is not an AR signal yet);
# large enough that one delayed insurance reconciliation does not light
# up the widget. Tunable here without a migration; revisit once finance
# gives us a calibrated threshold.
AR_RISK_BALANCE_THRESHOLD: float = 500.0

# CareStack accounting ``transactionCode`` sets used by the per-person
# financial summary (ENG-306). Billed = completed procedures; Adjustments
# = patient adjustments + fee updates (net debit−credit). Kept narrow on
# purpose — widening it silently moves money between the columns on the
# UI without a code change is reviewable.
_BILLED_TRANSACTION_CODES: tuple[str, ...] = ("PROCEDURECOMPLETED",)
_ADJUSTMENT_TRANSACTION_CODES: tuple[str, ...] = (
    "PATIENTADJUSTMENT",
    "FEEUPDATION",
)


def _int_from_db(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(str(value))


def _float_from_db(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return float(str(value))

_PAYLOAD_ALLOWLIST_BY_PROVIDER: dict[str, frozenset[str]] = {
    "salesforce": frozenset(
        {
            "Id",
            "attributes",
            "Company",
            "Status",
            "LeadSource",
            "CreatedDate",
            "LastModifiedDate",
        }
    ),
    "carestack": frozenset(
        {
            "id",
            "patientId",
            "PatientId",
            "patientIdentifier",
            "AppointmentId",
            "Status",
            "status",
            "AppointmentType",
            "ScheduledStart",
            "defaultLocationId",
            "LocationId",
            "lastUpdatedOn",
        }
    ),
}

# Keys we refuse to accept in ``NormalizedPersonHint.meta`` or
# ``quality_flags``. The hint table is for parser/matching metadata only;
# clinical text and verbatim provider payloads must never leak in via this
# route. Mirrors the deny-list used by ``IdentityService`` so the two PHI
# guards stay aligned — widen both in lock-step.
_FORBIDDEN_HINT_KEYS: frozenset[str] = frozenset(
    {
        "dob",
        "date_of_birth",
        "birthdate",
        "ssn",
        "allergy",
        "allergies",
        "medication",
        "medications",
        "prescription",
        "diagnosis",
        "chief_complaint",
        "clinical_notes",
        "treatment_notes",
        "raw_payload",
        "raw",
        "payload",
        "phi",
    }
)


def _collect_forbidden_hint_paths(value: object, prefix: str = "") -> list[str]:
    """Return PHI-looking JSON key paths from a hint metadata payload."""
    if isinstance(value, Mapping):
        paths: list[str] = []
        for raw_key, nested_value in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(raw_key, str) and raw_key.lower() in _FORBIDDEN_HINT_KEYS:
                paths.append(path)
            paths.extend(_collect_forbidden_hint_paths(nested_value, path))
        return paths
    if isinstance(value, list | tuple):
        paths = []
        for idx, nested_value in enumerate(value):
            path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            paths.extend(_collect_forbidden_hint_paths(nested_value, path))
        return paths
    return []


def _reject_phi_keys(field_name: str, payload: Mapping[str, object]) -> None:
    """Refuse PHI-looking keys in hint meta / quality_flags payloads."""
    if not payload:
        return
    offending = sorted(_collect_forbidden_hint_paths(payload))
    if offending:
        raise ValidationError(
            f"{field_name} contains forbidden keys",
            details={"field": field_name, "keys": offending},
        )


def _compute_hint_hash(
    *,
    source_system: str,
    source_instance: str,
    source_kind: str,
    source_id: str | None,
    email_normalized: str | None,
    phone_normalized: str | None,
    given_name: str | None,
    family_name: str | None,
) -> str:
    """Stable SHA-256 over the normalised matching features.

    Used as a deterministic dedup/idempotency signal for downstream match
    policy. Inputs are pinned to the normalised form so casing or
    whitespace variations do not produce different hashes. ``None`` is
    serialised as the empty string so absence is distinguishable from
    presence of an empty value.
    """
    parts = [
        source_system or "",
        source_instance or "",
        source_kind or "",
        source_id or "",
        email_normalized or "",
        phone_normalized or "",
        (given_name or "").strip().lower(),
        (family_name or "").strip().lower(),
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _json_value_type(value: object) -> str:
    """JSON-shape label for a payload value (ENG-429 observed-key snapshot)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list | tuple):
        return "array"
    return "unknown"


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return None


def _safe_payload_projection(provider: str, payload: Mapping[str, object]) -> dict[str, object]:
    allowlist = _PAYLOAD_ALLOWLIST_BY_PROVIDER.get(provider, frozenset())
    out: dict[str, object] = {}
    for key in allowlist:
        if key not in payload:
            continue
        value = payload[key]
        if key == "attributes" and isinstance(value, Mapping):
            attr_type = value.get("type")
            if isinstance(attr_type, str):
                out["attributes"] = {"type": attr_type}
            continue
        scalar = _json_scalar(value)
        if scalar is not None:
            out[key] = scalar
    return out


def _parse_source_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    if len(candidate) >= 5 and candidate[-5] in {"+", "-"} and candidate[-3] != ":":
        candidate = f"{candidate[:-2]}:{candidate[-2:]}"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _source_kind_to_entity_kind(source_kind: str | None, event_type: str) -> str:
    if source_kind:
        return source_kind.replace("_", " ").title().replace(" ", "")
    tail = event_type.split(".")[-1] if event_type else "record"
    return tail.replace("_", " ").title().replace(" ", "")


def _infer_source_kind(provider: str, event_type: str, payload: Mapping[str, object]) -> str:
    if provider == "salesforce":
        return "lead"
    if provider == "carestack":
        if "AppointmentId" in payload or "appointment" in event_type.lower():
            return "appointment"
        return "patient"
    return "record"


def _display_name_from_hint(hint: NormalizedPersonHint | None) -> str | None:
    if hint is None:
        return None
    if hint.display_name:
        return hint.display_name
    parts = [part for part in (hint.given_name, hint.family_name) if part]
    return " ".join(parts) if parts else None


def _payload_status(payload: Mapping[str, object]) -> str | None:
    value = payload.get("Status") or payload.get("status")
    return value if isinstance(value, str) else None


def _payload_occurred_at(payload: Mapping[str, object]) -> datetime | None:
    for key in ("CreatedDate", "ScheduledStart", "lastUpdatedOn", "LastModifiedDate"):
        parsed = _parse_source_datetime(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _external_key(
    raw_event: RawEvent, hint: NormalizedPersonHint | None
) -> tuple[str, str, str, str] | None:
    source_id = hint.source_id if hint is not None else raw_event.external_id
    if not source_id:
        return None
    source_system = hint.source_system if hint is not None else raw_event.source
    source_instance = (
        hint.source_instance
        if hint is not None
        else default_source_instance(source_system)
    )
    source_kind = (
        hint.source_kind
        if hint is not None
        else _infer_source_kind(raw_event.source, raw_event.event_type, raw_event.payload)
    )
    return (source_system, source_instance, source_kind, source_id)


def _dedupe_signals(signals: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        if signal in seen:
            continue
        seen.add(signal)
        out.append(signal)
    return out


class IngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IngestRepository(session)
        self._identity = IdentityService(session)

    async def capture(self, tenant_id: TenantId, payload: RawEventIn) -> RawEvent:
        event = RawEvent(
            tenant_id=tenant_id,
            source=payload.source,
            event_type=payload.event_type,
            external_id=payload.external_id,
            received_at=payload.received_at,
            payload=payload.payload,
        )
        return await self._repo.add(event)

    # --- Full-fidelity schema registry (ENG-426) ---

    async def sync_object_schema(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        object_name: str,
        fields: Sequence[ObservedFieldIn],
        observed_at: datetime,
    ) -> SchemaDiffOut:
        """Reconcile an observed source-object schema against the registry.

        ``fields`` is the field set derived from the source: a Salesforce
        ``describe`` merged with the Tooling-API full list (so FLS-blocked
        fields appear with ``readable=False``), or the union of observed
        payload keys for a REST source. Each call:

        * inserts genuinely new fields (``active=True``, ``first_seen`` set);
        * reactivates fields that had gone inactive and reappeared;
        * records type changes and readability transitions;
        * refreshes ``last_seen_at`` and merges ``meta`` for known fields;
        * marks fields absent from ``fields`` as ``active=False`` (never
          deletes — the registry keeps full history like ``raw_event``).

        Returns the :class:`SchemaDiffOut` drift shape and emits a structured
        log line when anything changed. Idempotent: a second call with the
        same ``fields`` yields an empty diff.
        """
        if not provider.strip():
            raise ValidationError("provider is required", details={"provider": provider})
        if not object_name.strip():
            raise ValidationError(
                "object_name is required", details={"object_name": object_name}
            )

        existing = {
            row.field_name: row
            for row in await self._repo.list_object_fields(
                tenant_id, provider=provider, object_name=object_name
            )
        }

        diff = SchemaDiffOut(provider=provider, object_name=object_name)
        observed_names: set[str] = set()

        for obs in fields:
            name = obs.name
            if name in observed_names:
                # Duplicate field in the derivation — keep the first, ignore
                # the rest rather than thrashing the row.
                continue
            observed_names.add(name)
            row = existing.get(name)
            if row is None:
                self._session.add(
                    SourceObjectField(
                        tenant_id=tenant_id,
                        provider=provider,
                        object_name=object_name,
                        field_name=name,
                        field_type=obs.field_type,
                        readable=obs.readable,
                        active=True,
                        first_seen_at=observed_at,
                        last_seen_at=observed_at,
                        meta=dict(obs.meta),
                    )
                )
                diff.added.append(name)
                continue

            # Known field — update in place.
            if obs.field_type is not None and obs.field_type != row.field_type:
                diff.type_changed.append(
                    FieldTypeChange(
                        field=name, old_type=row.field_type, new_type=obs.field_type
                    )
                )
                row.field_type = obs.field_type
            if obs.readable != row.readable:
                if obs.readable:
                    diff.became_readable.append(name)
                else:
                    diff.became_unreadable.append(name)
                row.readable = obs.readable
            if not row.active:
                row.active = True
                diff.added.append(name)
            row.last_seen_at = observed_at
            if obs.meta:
                row.meta = {**row.meta, **dict(obs.meta)}

        for name, row in existing.items():
            if name not in observed_names and row.active:
                row.active = False
                diff.removed.append(name)

        await self._session.flush()

        if diff.has_changes:
            _schema_log.info(
                "ingest.schema_registry.drift",
                tenant_id=str(tenant_id),
                provider=provider,
                object_name=object_name,
                added=sorted(diff.added),
                removed=sorted(diff.removed),
                type_changed=[c.field for c in diff.type_changed],
                became_readable=sorted(diff.became_readable),
                became_unreadable=sorted(diff.became_unreadable),
            )
        return diff

    async def get_object_schema(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        object_name: str,
        active_only: bool = True,
    ) -> list[SourceObjectField]:
        """Return registry rows for a source object (active fields by default)."""
        rows = await self._repo.list_object_fields(
            tenant_id, provider=provider, object_name=object_name
        )
        if active_only:
            return [row for row in rows if row.active]
        return rows

    async def snapshot_observed_schema(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        object_name: str,
        event_type: str,
        sample_limit: int = 200,
    ) -> SchemaDiffOut:
        """Reconcile a REST object's schema from observed payload keys (ENG-429).

        Sources without a ``describe`` (CareStack and future REST systems) have
        their full-fidelity schema derived from the union of top-level keys
        across a sample of recently-captured raw payloads. Each key becomes a
        ``readable`` registry field with its JSON-inferred type. An empty sample
        (no recent rows for the event type) is a no-op — it must NOT deactivate
        the existing registry, which would happen if we synced an empty set.
        """
        payloads = await self._repo.sample_recent_payloads(
            tenant_id, event_type=event_type, limit=sample_limit
        )
        if not payloads:
            return SchemaDiffOut(provider=provider, object_name=object_name)

        types: dict[str, str] = {}
        for payload in payloads:
            if not isinstance(payload, Mapping):
                continue
            for key, value in payload.items():
                inferred = _json_value_type(value)
                existing = types.get(str(key))
                # Prefer a concrete type over one derived from a null sample.
                if existing is None or existing == "null":
                    types[str(key)] = inferred

        observed = [
            ObservedFieldIn(
                name=key,
                field_type=value_type,
                readable=True,
                meta={"source": "observed_keys"},
            )
            for key, value_type in types.items()
        ]
        return await self.sync_object_schema(
            tenant_id,
            provider=provider,
            object_name=object_name,
            fields=observed,
            observed_at=datetime.now(UTC),
        )

    async def list_unprocessed(
        self, tenant_id: TenantId, limit: int = 100, source: str | None = None
    ) -> list[RawEvent]:
        return await self._repo.list_unprocessed(tenant_id, limit=limit, source=source)

    async def mark_processed(self, tenant_id: TenantId, event_id: UUID) -> None:
        await self._repo.mark_processed(tenant_id, event_id, datetime.now(UTC))

    async def mark_error(
        self, tenant_id: TenantId, event_id: UUID, error: str
    ) -> None:
        """Record a non-fatal processing error on a raw event.

        Tenant-scoped; the repository truncates the message. Does NOT set
        ``processed_at`` — the row stays unprocessed so a later run can
        retry. Used by per-source dispatch handlers (e.g. the Mattermost
        inbound mapper) to record a per-row failure without stalling the
        batch.
        """
        await self._repo.mark_error(tenant_id, event_id, error)

    async def list_recent_raw_events(
        self,
        tenant_id: TenantId,
        limit: int = 50,
        provider: str | None = None,
    ) -> list[RawEvent]:
        return await self._repo.list_recent(
            tenant_id, limit=limit, provider=provider
        )

    async def get_raw_event(
        self, tenant_id: TenantId, event_id: UUID
    ) -> RawEvent | None:
        """Return one tenant-scoped raw event by id, or ``None`` if absent.

        Mirrors the tenant-scoped lookup the Inspector list endpoint already
        uses; the single-by-id route exposes the verbatim provider payload
        for the PM Payments page drilldown via the existing local-dev
        Inspector carve-out (``packages/ingest/CLAUDE.md``).
        """
        return await self._repo.get(tenant_id, event_id)

    async def count_raw_events(
        self, tenant_id: TenantId, provider: str | None = None
    ) -> int:
        return await self._repo.count(tenant_id, provider=provider)

    async def list_latest_by_type_since(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        since: datetime,
    ) -> list[tuple[UUID, dict[str, object]]]:
        """Latest raw ``(id, payload)`` per external id for an event type.

        Backs SF-task reconciliation (ENG-462) — re-projecting tasks
        captured before their lead was linked, from already-stored raw.
        """
        return await self._repo.list_latest_by_type_since(
            tenant_id, event_type=event_type, since=since
        )

    async def list_latest_by_type_paginated(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        limit: int,
        after_external_id: str | None = None,
        since: datetime | None = None,
    ) -> list[tuple[UUID, str, dict[str, object]]]:
        """One cursored page of latest raw ``(id, external_id, payload)``.

        Bounded + resumable enumeration backing the treatment-procedure
        replay (ENG-540): the operator script walks pages with
        ``after_external_id`` as a stable forward cursor and commits per
        batch. ``DISTINCT ON (external_id)`` keeps one row (the newest) per
        external id, so a procedure re-projects once from its freshest
        captured payload. See
        :meth:`IngestRepository.list_latest_by_type_paginated`.
        """
        return await self._repo.list_latest_by_type_paginated(
            tenant_id,
            event_type=event_type,
            limit=limit,
            after_external_id=after_external_id,
            since=since,
        )

    async def count_distinct_external_ids_by_type(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        since: datetime | None = None,
    ) -> int:
        """Distinct captured ``external_id`` count for an event type.

        Backs the treatment-procedure replay dry-run (ENG-540): how many
        procedures would be re-projected, with no payload load and no
        CareStack round-trip. See
        :meth:`IngestRepository.count_distinct_external_ids_by_type`.
        """
        return await self._repo.count_distinct_external_ids_by_type(
            tenant_id, event_type=event_type, since=since
        )

    async def distinct_treatment_procedure_code_ids(
        self, tenant_id: TenantId
    ) -> list[int]:
        """Distinct ``procedureCodeId`` ids across captured treatment procedures.

        The work-list for the by-id procedure-code catalog sync (ENG-538):
        every distinct ``procedureCodeId`` observed in
        ``carestack.treatment_procedure.upsert`` raw_events. The catalog
        domain can't read ``ingest`` (the import matrix only allows
        ``ingest -> catalog``), so the caller boundary (operator backfill /
        weekly Cloud Run Job) enumerates here and hands the ids to
        ``CatalogService.sync_procedure_codes_by_id``. Tenant-scoped.
        """
        return await self._repo.distinct_payload_int_values(
            tenant_id,
            event_type="carestack.treatment_procedure.upsert",
            payload_key="procedureCodeId",
        )

    async def treatment_procedure_code_ids_by_patient(
        self, tenant_id: TenantId
    ) -> dict[str, list[int]]:
        """``patientId -> [procedureCodeId, ...]`` over distinct treatment procedures.

        Backs the analytics implant ``case_type`` resolver (ENG-539, B1.5). One
        code id per DISTINCT procedure (newest payload per ``external_id``), so
        the downstream D6010 placement count is the number of placement
        procedures. CareStack-id-space scalars only — no clinical fields leave
        the raw layer. The fact builder maps ``patientId -> person_uid`` via
        ``IdentityService`` and ``procedureCodeId -> CDT`` via ``CatalogService``.
        Tenant-scoped.
        """
        return await self._repo.treatment_procedure_code_ids_by_patient(tenant_id)

    async def max_payload_watermark(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        watermark_key: str = "lastUpdatedOn",
    ) -> str | None:
        """Highest ``payload[watermark_key]`` captured for an event type.

        Backs the incremental ``modifiedSince`` cursor used by the
        scheduled CareStack sync pulls (see
        :mod:`packages.ingest.sync_window`).
        """
        return await self._repo.max_payload_watermark(
            tenant_id, event_type=event_type, watermark_key=watermark_key
        )

    async def latest_payload_values(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        external_ids: Sequence[str],
        payload_key: str,
    ) -> dict[str, str]:
        """Batch lookup of the captured modified-stamp per external id.

        Capture change-guard support (ENG-381): pullers compare the
        provider stamp of each fetched row against this map and skip
        re-capturing rows that did not change. See
        :meth:`IngestRepository.latest_payload_values`.
        """
        return await self._repo.latest_payload_values(
            tenant_id,
            event_type=event_type,
            external_ids=external_ids,
            payload_key=payload_key,
        )

    async def latest_payload(
        self,
        tenant_id: TenantId,
        *,
        event_type: str,
        external_id: str,
    ) -> dict[str, object] | None:
        """Newest captured payload for one ``(event_type, external_id)``.

        Content-level dedupe support for snapshot feeds without a
        provider modified-stamp (payment summary).
        """
        return await self._repo.latest_payload(
            tenant_id, event_type=event_type, external_id=external_id
        )

    async def get_carestack_invoice_refs(
        self, tenant_id: TenantId, invoice_ids: Sequence[str]
    ) -> dict[str, dict[str, str | None]]:
        """Resolve CareStack invoice ids → ``{invoice_number, invoice_date}``.

        Non-PII billing scalars only, from the latest captured invoice raw
        per id (ENG-303). Used by the PM Payments route to show which invoice
        a payment belongs to. Ids with no captured invoice are absent.
        """
        return await self._repo.get_carestack_invoice_refs(tenant_id, invoice_ids)

    async def get_payment_procedure_doctor_refs(
        self, tenant_id: TenantId, raw_event_ids: Sequence[UUID]
    ) -> dict[UUID, dict[str, str | int | None]]:
        """Resolve payment raw events → operation code + performing doctor.

        For each accounting-transaction raw_event PK (the ``source_event_id``
        carried by every PM Payments row), reads the non-PII ``procedureCodeId``
        and ``providerId`` scalars and resolves them to operator-facing values.

        ENG-551 correction: ``accounting_transaction.procedureCodeId`` is NOT a
        CDT catalog id — its value is a ``treatment_procedure.id`` (the procedure
        INSTANCE id; id spaces ~1.7M–24.7M vs the catalog's 5k–438k). The
        ENG-547 direct ``procedureCodeId → catalog`` join therefore matched 0
        legs. The real resolution hops through the treatment procedure:

        * ``accounting.procedureCodeId`` (= ``treatment_procedure.id``) →
          ``carestack.treatment_procedure.upsert`` raw payload via
          :meth:`IngestRepository.get_treatment_procedure_refs`, which returns
          the procedure's real CDT ``procedureCodeId`` + its ``providerId``.
        * the tp's CDT id → ``catalog.procedure_code`` (CDT ``code`` +
          ``description``) via ``CatalogService`` (allowed ``ingest -> catalog``
          edge).
        * the doctor's provider id → ``ingest.carestack_provider`` display name
          via :meth:`IngestRepository.lookup_provider_names`.

        Doctor preference: the treatment procedure's ``providerId`` (filled
        ~100%) is used whenever the procedure is linked; the accounting
        ``providerId`` (filled ~77% — payment-application legs often omit it) is
        the fallback only when no treatment procedure is linked.
        ``doctor_provider_id`` echoes whichever provider id was used.

        All lookups are batched across the page (no per-row N+1). Returns
        ``{raw_event_id: {"operation_code", "operation_description",
        "doctor_name", "doctor_provider_id"}}`` with ``None`` for any scalar
        that is absent (advances, unallocated legs, adjustments) or unresolved
        (no linked treatment procedure, CDT id not in the catalog, provider id
        not in the directory). Raw ids with no captured accounting row are
        absent from the map. Operation comes ONLY from the tp→catalog chain.
        """
        ids = [rid for rid in raw_event_ids if rid is not None]
        if not ids:
            return {}

        codes_by_raw = await self._repo.get_carestack_accounting_codes(
            tenant_id, ids
        )
        if not codes_by_raw:
            return {}

        # The accounting ``procedureCodeId`` is a treatment_procedure INSTANCE
        # id (ENG-551); hop through the procedure for the real CDT id + provider.
        tp_ids = {
            tp_id
            for tp_id, _accounting_provider_id in codes_by_raw.values()
            if tp_id is not None
        }
        tp_refs = (
            await self._repo.get_treatment_procedure_refs(
                tenant_id, sorted(tp_ids)
            )
            if tp_ids
            else {}
        )

        # Decide the resolved (CDT id, provider id) per raw row: prefer the
        # linked procedure's CDT + provider; fall back to the accounting
        # provider (operation stays None) only when no procedure is linked.
        chosen: dict[UUID, tuple[int | None, int | None]] = {}
        for raw_id, (tp_id, accounting_provider_id) in codes_by_raw.items():
            tp_ref = tp_refs.get(tp_id) if tp_id is not None else None
            if tp_ref is not None:
                cdt_code_id, tp_provider_id = tp_ref
                chosen[raw_id] = (cdt_code_id, tp_provider_id)
            else:
                chosen[raw_id] = (None, accounting_provider_id)

        cdt_code_ids = {
            cdt_id for cdt_id, _provider_id in chosen.values() if cdt_id is not None
        }
        provider_ids = {
            provider_id
            for _cdt_id, provider_id in chosen.values()
            if provider_id is not None
        }

        procedure_map = (
            await CatalogService(self._session).resolve_procedure_codes(
                cdt_code_ids
            )
            if cdt_code_ids
            else {}
        )
        provider_map = (
            await self._repo.lookup_provider_names(tenant_id, provider_ids)
            if provider_ids
            else {}
        )

        result: dict[UUID, dict[str, str | int | None]] = {}
        for raw_id, (cdt_code_id, provider_id) in chosen.items():
            code_pair = (
                procedure_map.get(cdt_code_id) if cdt_code_id is not None else None
            )
            result[raw_id] = {
                "operation_code": code_pair[0] if code_pair else None,
                "operation_description": code_pair[1] if code_pair else None,
                "doctor_name": (
                    provider_map.get(provider_id)
                    if provider_id is not None
                    else None
                ),
                "doctor_provider_id": provider_id,
            }
        return result

    async def latest_payment_summary_balances(
        self, tenant_id: TenantId
    ) -> LatestPaymentSummaryBalancesOut:
        """Return the dashboard-safe outstanding balance aggregate (ENG-257 / ENG-266).

        Sums the LATEST ``carestack.payment_summary.snapshot`` raw_event
        per patient. ``outstanding_total`` = patient + insurance, the
        single number the PM dashboard widget needs. The patient/insurance
        breakdown is returned alongside in case the widget grows.

        Also returns ``ar_risk_count`` (ENG-266) = number of patients
        whose LATEST ``balanceDuePatient`` is strictly greater than
        ``AR_RISK_BALANCE_THRESHOLD``. Tenant-scoped. Returns zeros and
        ``patient_count=0`` when no snapshot rows exist yet.
        """
        row = await self._repo.sum_latest_payment_summary_balances(
            tenant_id,
            ar_risk_threshold=AR_RISK_BALANCE_THRESHOLD,
        )
        balance_due_patient = _float_from_db(row.get("balance_due_patient"))
        balance_due_insurance = _float_from_db(row.get("balance_due_insurance"))
        return LatestPaymentSummaryBalancesOut(
            balance_due_patient=balance_due_patient,
            balance_due_insurance=balance_due_insurance,
            outstanding_total=balance_due_patient + balance_due_insurance,
            patient_count=_int_from_db(row.get("patient_count")),
            ar_risk_count=_int_from_db(row.get("ar_risk_count")),
            ar_risk_threshold=AR_RISK_BALANCE_THRESHOLD,
        )

    async def person_payment_financial_summary(
        self,
        tenant_id: TenantId,
        carestack_patient_ids: Sequence[str],
    ) -> PersonPaymentFinancialSummaryOut:
        """Per-person financial summary for the staff person card (ENG-306).

        Combines the authoritative balance/paid figures from the latest
        ``carestack.payment_summary.snapshot`` raw_event with the gross
        Billed/Adjustments context from the accounting journal raw_events.
        Aggregates across every CareStack patient id linked to the person
        (rare: usually 0 or 1, occasionally >1 when one human has multiple
        CS source links).

        Empty state: when the person has no CareStack patient id OR none
        of the patient ids have a captured payment-summary snapshot yet,
        returns ``snapshot_received_at=None`` with zeroed numbers. The UI
        renders ``"—"`` for each value when ``snapshot_received_at`` is
        ``None`` — never ``"$0"`` (which would imply we know the balance
        is zero).

        Billed and Adjustments are still summed from accounting raw_events
        independently of the payment-summary snapshot, so a patient with
        captured accounting rows but no snapshot will surface zeros in
        the UI (gated by ``snapshot_received_at``) even though the
        underlying billed total is non-zero. That is intentional — the
        ENG-307 backfill is the operator-controlled gate that lights up
        the card.
        """
        patient_ids = sorted({pid for pid in carestack_patient_ids if pid})
        if not patient_ids:
            return PersonPaymentFinancialSummaryOut(
                billed=0.0,
                adjustments=0.0,
                paid=0.0,
                balance=0.0,
                snapshot_received_at=None,
                carestack_patient_ids=[],
                patient_count=0,
            )

        latest_by_patient = await self._repo.latest_payment_summary_by_patient(
            tenant_id, patient_ids
        )
        billed_by_patient = await self._repo.sum_accounting_totals_by_patient(
            tenant_id,
            patient_ids,
            transaction_codes=_BILLED_TRANSACTION_CODES,
        )
        adjustment_by_patient = await self._repo.sum_accounting_totals_by_patient(
            tenant_id,
            patient_ids,
            transaction_codes=_ADJUSTMENT_TRANSACTION_CODES,
        )

        paid_total = 0.0
        balance_total = 0.0
        latest_received: datetime | None = None
        for snapshot in latest_by_patient.values():
            balance_value = snapshot.get("balance")
            if isinstance(balance_value, int | float):
                balance_total += float(balance_value)
            paid_value = snapshot.get("paid")
            if isinstance(paid_value, int | float):
                paid_total += float(paid_value)
            received = snapshot.get("received_at")
            if isinstance(received, datetime):
                if latest_received is None or received > latest_received:
                    latest_received = received

        billed_total = sum(billed_by_patient.values())
        adjustment_total = sum(adjustment_by_patient.values())

        return PersonPaymentFinancialSummaryOut(
            billed=float(billed_total),
            adjustments=float(adjustment_total),
            paid=float(paid_total),
            balance=float(balance_total),
            snapshot_received_at=latest_received,
            carestack_patient_ids=patient_ids,
            patient_count=len(patient_ids),
        )

    async def list_carestack_provider_directory(
        self, tenant_id: TenantId
    ) -> dict[int, str]:
        """``{provider_carestack_id: display_name}`` for every CareStack provider.

        The analytics doctor-actor backfill (ENG-510) links each directory
        provider to an ``actor.actor`` (kind ``carestack_provider_id``) with a
        proper display name. Provider data is operational metadata (PII, not
        PHI). The actor write happens at the worker boundary — ``ingest`` may
        not import ``actor``.
        """
        return await self._repo.list_provider_directory(tenant_id)

    async def person_carestack_origin_context(
        self,
        tenant_id: TenantId,
        carestack_patient_ids: Sequence[str],
    ) -> list[CarestackOriginRowOut]:
        """Per-pid origin context for the person card (ENG-308).

        Returns one :class:`CarestackOriginRowOut` per CareStack patient
        id the person is linked to. Each row has the true earliest /
        latest CareStack activity timestamps (MIN/MAX of appointment
        ``createdOn`` and accounting ``TransactionDate``), the city +
        state from the latest patient.upsert payload, and the resolved
        provider + location names so the UI never renders raw integers.

        Empty input → ``[]`` (no DB round-trip).

        Provider names are resolved via
        :meth:`IngestRepository.lookup_provider_names`. Location names
        are resolved via
        :meth:`packages.tenant.service.LocationService.find_by_carestack_id`
        when the local locations directory is populated; ``None`` is
        returned otherwise.
        """
        cleaned = sorted({pid for pid in carestack_patient_ids if pid})
        if not cleaned:
            return []

        raw_by_pid = await self._repo.person_carestack_origin_context(
            tenant_id, cleaned
        )

        # Collect distinct provider ids first so the name lookup is one
        # round-trip across all pids on the page.
        provider_ids = [
            row["default_provider_id"]
            for row in raw_by_pid.values()
            if row.get("default_provider_id") is not None
        ]
        provider_names = await self._repo.lookup_provider_names(
            tenant_id, provider_ids
        )

        # Location names are resolved per-cs-id via LocationService. The
        # set of distinct cs-location-ids on one person card is tiny
        # (~1-3), so per-id calls are acceptable. Importing here keeps
        # the layering surface minimal.
        location_ids = sorted(
            {
                row["default_location_id"]
                for row in raw_by_pid.values()
                if row.get("default_location_id") is not None
            }
        )
        location_names: dict[int, str] = {}
        if location_ids:
            # Local import — the matrix permits ingest → tenant but
            # importing at module top would pull tenant into every
            # IngestService consumer, including those that never touch
            # the locations directory.
            from packages.tenant.service import LocationService

            location_service = LocationService(self._session)
            for cs_loc_id in location_ids:
                try:
                    location = await location_service.find_by_carestack_id(
                        tenant_id, cs_loc_id
                    )
                except Exception as exc:
                    # Per packages/CLAUDE.md: ``except Exception``.
                    # Location-name resolution is best-effort; the UI
                    # falls back to the raw id when the lookup fails.
                    _origin_log.info(
                        "carestack.location_name.lookup_failed",
                        tenant_id=str(tenant_id),
                        carestack_location_id=cs_loc_id,
                        error=str(exc)[:200],
                    )
                    continue
                if location is not None:
                    location_names[cs_loc_id] = location.name

        rows: list[CarestackOriginRowOut] = []
        for patient_id in cleaned:
            data = raw_by_pid.get(patient_id, {})
            provider_id = data.get("default_provider_id")
            location_id = data.get("default_location_id")
            rows.append(
                CarestackOriginRowOut(
                    patient_id=patient_id,
                    earliest_activity_at=data.get("earliest_activity_at"),
                    latest_activity_at=data.get("latest_activity_at"),
                    default_location_id=location_id,
                    default_location_name=(
                        location_names.get(location_id)
                        if location_id is not None
                        else None
                    ),
                    default_provider_id=provider_id,
                    default_provider_name=(
                        provider_names.get(provider_id)
                        if provider_id is not None
                        else None
                    ),
                    city=data.get("city"),
                    state=data.get("state"),
                    # ENG-310 per-pid identity / patient details. These
                    # come straight from the latest patient.upsert
                    # payload via the repository aggregator; the
                    # frontend uses them for the multi-link row label
                    # ("First Last · pid") and the click-to-reveal
                    # Patient details panel.
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    dob=data.get("dob"),
                    gender=data.get("gender"),
                    marital_status=data.get("marital_status"),
                    mobile=data.get("mobile"),
                    phone_with_ext=data.get("phone_with_ext"),
                    work_phone_with_ext=data.get("work_phone_with_ext"),
                    email=data.get("email"),
                    address_line1=data.get("address_line1"),
                    address_line2=data.get("address_line2"),
                    address_zip=data.get("address_zip"),
                    patient_identifier=data.get("patient_identifier"),
                    account_id=data.get("account_id"),
                )
            )
        return rows

    async def person_household_members(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[HouseholdMemberOut]:
        """Return OTHER persons sharing a phone or email (ENG-310).

        Thin wrapper over
        :meth:`IngestRepository.person_household_members`. The
        repository reads ``carestack.patient.upsert`` payloads (not
        ``identity.person_identifier``) so siblings that share a phone
        / email but are correctly separate Person rows (post-ENG-311
        split) are still surfaced. Empty when the person has no
        CareStack patient link or no matching sibling.

        Returns a list of :class:`HouseholdMemberOut` — one row per
        sibling person, with a masked shared-value hint the UI renders
        next to the navigational link. Never returns the input person.
        """
        # Three complementary resolvers, unioned + deduped by sibling
        # person_uid:
        #   1. CareStack-payload (patients),
        #   2. identity.person_identifier (ENG-463 — cross-form phone numbers),
        #   3. normalized_person_hint (ENG-542 — Salesforce-lead siblings whose
        #      shared phone was never persisted as an identifier because the
        #      global UNIQUE(kind, value) constraint blocks a second row).
        # Precedence on conflict: CareStack > identifier > hint (richer
        # payload-name fallback first), enforced by first-write-wins below.
        carestack_rows = await self._repo.person_household_members(
            tenant_id, person_uid
        )
        identifier_rows = await self._repo.person_household_members_by_identifier(
            tenant_id, person_uid
        )
        hint_rows = await self._repo.person_household_members_by_hint(
            tenant_id, person_uid
        )
        by_uid: dict[str, dict[str, str | None]] = {}
        for row in (*carestack_rows, *identifier_rows, *hint_rows):
            uid = row["person_uid"] or ""
            if uid and uid not in by_uid:
                by_uid[uid] = row
        return [
            HouseholdMemberOut(
                person_uid=row["person_uid"] or "",
                display_name=row.get("display_name"),
                shared_via=row["shared_via"] or "",
                shared_value_masked=row["shared_value_masked"] or "",
            )
            for row in by_uid.values()
        ]

    async def backfill_lead_person_identifiers(
        self,
        tenant_id: TenantId,
        *,
        principal: Principal | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Persist phone/email identifiers for Salesforce-lead persons from
        their captured hints (ENG-542 DO #3).

        For every lead-person hint value, attaches the identifier through
        :meth:`IdentityService.attach_identifier`, which is idempotent and
        collision-safe: a value already owned by ANOTHER person (the
        shared-contact case blocked by the global ``UNIQUE(kind, value)``
        constraint, reworked under ENG-341) is counted as ``collision`` and
        skipped rather than persisted. The card still surfaces those siblings
        via the hint-based household resolver, so no signal is lost.

        Idempotent + reversible-friendly: re-running only ever ADDS rows that
        are still free; already-present values return ``exists``. When a
        ``principal`` is supplied (and not ``dry_run``), each genuinely-added
        identifier writes an append-only ``identity.identifier.backfill``
        audit row. ``dry_run`` predicts the work without writing anything.

        Returns a tally: ``persons`` scanned plus per-outcome counters
        (``added`` / ``exists`` / ``collision`` / ``invalid``); ``dry_run``
        returns ``persons`` + ``candidates`` only.
        """
        candidates = await self._repo.lead_person_identifier_hints(
            tenant_id, limit=limit
        )
        persons = {person_uid for person_uid, _, _ in candidates}
        if dry_run:
            candidate_values = sum(
                1
                for _, phone, email in candidates
                for value in (phone, email)
                if value
            )
            return {"persons": len(persons), "candidates": candidate_values}

        audit = AuditService(self._session) if principal is not None else None
        tally: dict[str, int] = {
            "persons": len(persons),
            "added": 0,
            "exists": 0,
            "collision": 0,
            "invalid": 0,
        }
        for person_uid, phone, email in candidates:
            for kind, value in (("phone", phone), ("email", email)):
                if not value:
                    continue
                status = await self._identity.attach_identifier(
                    tenant_id, PersonUID(person_uid), kind, value
                )
                tally[status] = tally.get(status, 0) + 1
                if status == "added" and audit is not None and principal is not None:
                    await audit.record(
                        principal=principal,
                        action="identity.identifier.backfill",
                        resource="identity.person",
                        person_uid=PersonUID(person_uid),
                        extra={"kind": kind, "source": "salesforce_lead_hint"},
                    )
        return tally

    async def latest_balance_by_patient(
        self,
        tenant_id: TenantId,
        carestack_patient_ids: Sequence[str],
    ) -> dict[str, float]:
        """Return latest ``balance`` per CareStack patient id (ENG-306).

        Used by the PM Payments row balance pill. One repository round-trip
        for the whole page of rows; patient ids with no captured snapshot
        are absent from the result so the UI renders ``"—"`` instead of
        ``"$0"``.
        """
        rows = await self._repo.latest_payment_summary_by_patient(
            tenant_id, carestack_patient_ids
        )
        out: dict[str, float] = {}
        for patient_id, snapshot in rows.items():
            balance = snapshot.get("balance")
            if isinstance(balance, int | float):
                out[patient_id] = float(balance)
        return out

    # --- Normalized person hints (ENG-185) ---

    async def capture_normalized_person_hint(
        self, tenant_id: TenantId, payload: NormalizedPersonHintIn
    ) -> NormalizedPersonHint:
        """Persist a normalised hint extracted from a raw event.

        The service:

        * validates ``source_system`` / ``source_kind`` against the
          identity-domain source lists (keeps the two domains' allowed
          values aligned without copying the tuples);
        * normalises ``email`` and ``phone`` — invalid inputs do NOT
          raise; the offending column is left ``NULL`` and a quality
          flag (``invalid_email`` / ``invalid_phone``) is added so the
          match policy can decide how to handle low-quality evidence;
        * records ``missing_*`` quality flags for absent identifiers;
        * rejects PHI/raw-payload keys in ``meta`` and ``quality_flags``;
        * computes a deterministic ``hint_hash`` over the normalised
          matching features (used downstream for idempotency).

        Returns the persisted hint row.
        """
        if payload.source_system not in SOURCE_SYSTEMS:
            raise ValidationError(
                "unknown source_system",
                details={
                    "source_system": payload.source_system,
                    "allowed": list(SOURCE_SYSTEMS),
                },
            )
        if payload.source_kind not in SOURCE_KINDS:
            raise ValidationError(
                "unknown source_kind",
                details={
                    "source_kind": payload.source_kind,
                    "allowed": list(SOURCE_KINDS),
                },
            )

        _reject_phi_keys("meta", payload.meta)
        _reject_phi_keys("quality_flags", payload.quality_flags)

        quality_flags: dict[str, object] = dict(payload.quality_flags)

        email_normalized: str | None = None
        if payload.email is None or payload.email.strip() == "":
            quality_flags.setdefault("missing_email", True)
        else:
            try:
                email_normalized = normalise_email(payload.email)
            except ValidationError:
                quality_flags["invalid_email"] = True

        phone_normalized: str | None = None
        if payload.phone is None or payload.phone.strip() == "":
            quality_flags.setdefault("missing_phone", True)
        else:
            try:
                phone_normalized = normalise_phone(payload.phone)
            except ValidationError:
                quality_flags["invalid_phone"] = True

        if (
            not (payload.given_name or "").strip()
            and not (payload.family_name or "").strip()
            and not (payload.display_name or "").strip()
        ):
            quality_flags.setdefault("missing_name", True)

        source_instance = (
            payload.source_instance.strip()
            if payload.source_instance is not None and payload.source_instance.strip()
            else default_source_instance(payload.source_system)
        )

        hint_hash = _compute_hint_hash(
            source_system=payload.source_system,
            source_instance=source_instance,
            source_kind=payload.source_kind,
            source_id=payload.source_id,
            email_normalized=email_normalized,
            phone_normalized=phone_normalized,
            given_name=payload.given_name,
            family_name=payload.family_name,
        )

        hint = NormalizedPersonHint(
            tenant_id=tenant_id,
            raw_event_id=payload.raw_event_id,
            source_system=payload.source_system,
            source_instance=source_instance,
            source_kind=payload.source_kind,
            source_id=payload.source_id,
            observed_at=payload.observed_at,
            given_name=payload.given_name,
            family_name=payload.family_name,
            display_name=payload.display_name,
            email_normalized=email_normalized,
            phone_normalized=phone_normalized,
            person_uid=None,
            source_link_id=None,
            payload_sha256=payload.payload_sha256,
            hint_hash=hint_hash,
            quality_flags=quality_flags,
            meta=dict(payload.meta),
        )
        return await self._repo.add_normalized_person_hint(hint)

    async def find_hint_by_raw_event(
        self, tenant_id: TenantId, raw_event_id: UUID
    ) -> NormalizedPersonHint | None:
        return await self._repo.find_hint_by_raw_event(tenant_id, raw_event_id)

    async def list_unresolved_hints(
        self, tenant_id: TenantId, limit: int = 100
    ) -> list[NormalizedPersonHint]:
        return await self._repo.list_unresolved_hints(tenant_id, limit=limit)

    async def list_dev_source_data(self, tenant_id: TenantId, limit: int = 50) -> SourceDataListOut:
        """Return PHI-minimised source records for the local dev UI.

        The backing source of truth is ``ingest.raw_event``. The returned
        ``payload`` is a safe projection, not the stored verbatim payload.
        """
        if limit < 1 or limit > 200:
            raise ValidationError(
                "limit must be between 1 and 200",
                details={"limit": limit},
            )

        rows = await self._repo.list_source_records(
            tenant_id,
            sources=_SOURCE_DATA_SOURCES,
            limit=limit,
        )
        external_keys = [key for raw_event, hint in rows if (key := _external_key(raw_event, hint))]
        source_links_by_key = await self._identity.source_links_for_external_records(
            tenant_id, external_keys
        )

        resolved_person_uids = sorted(
            {link.person_uid for link in source_links_by_key.values()},
            key=str,
        )
        links_by_person = await self._identity.source_links_for_persons(
            tenant_id, resolved_person_uids
        )

        items: list[SourceDataRecordOut] = []
        totals_by_provider = {"salesforce": 0, "carestack": 0}

        for raw_event, hint in rows:
            provider = raw_event.source
            if provider not in totals_by_provider:
                continue
            totals_by_provider[provider] += 1

            source_kind = (
                hint.source_kind
                if hint is not None
                else _infer_source_kind(provider, raw_event.event_type, raw_event.payload)
            )
            source_instance = (
                hint.source_instance
                if hint is not None
                else default_source_instance(provider)
            )
            source_id = (
                hint.source_id
                if hint is not None and hint.source_id is not None
                else raw_event.external_id
            )
            external_id = source_id or str(raw_event.id)
            entity_kind = _source_kind_to_entity_kind(source_kind, raw_event.event_type)
            key = _external_key(raw_event, hint)
            source_link = source_links_by_key.get(key) if key is not None else None
            person_uid = source_link.person_uid if source_link is not None else None

            signals = [
                provider,
                source_kind,
                "processed" if raw_event.processed_at else "unprocessed",
            ]
            if raw_event.error:
                signals.append("error")
            if person_uid is not None:
                signals.append("resolved_person")
            if hint is not None:
                signals.extend(str(key) for key in sorted(hint.quality_flags))

            related_records: list[SourceDataRelationOut] = []
            if person_uid is not None:
                for link in links_by_person.get(person_uid, []):
                    if (
                        link.source_system == provider
                        and link.source_instance == source_instance
                        and link.source_kind == source_kind
                        and link.source_id == source_id
                    ):
                        continue
                    if link.source_id is None:
                        continue
                    related_records.append(
                        SourceDataRelationOut(
                            id=str(link.id),
                            provider=link.source_system,
                            source_instance=link.source_instance,
                            entity_kind=_source_kind_to_entity_kind(
                                link.source_kind, link.source_kind
                            ),
                            external_id=link.source_id,
                            relation="same_resolved_person",
                            label="Same resolved person via source link",
                            person_uid=link.person_uid,
                        )
                    )

            items.append(
                SourceDataRecordOut(
                    id=raw_event.id,
                    provider=provider,
                    source_instance=source_instance,
                    external_id=external_id,
                    entity_kind=entity_kind,
                    display_name=_display_name_from_hint(hint),
                    email=hint.email_normalized if hint is not None else None,
                    phone=hint.phone_normalized if hint is not None else None,
                    status=_payload_status(raw_event.payload),
                    location_name=None,
                    occurred_at=_payload_occurred_at(raw_event.payload),
                    fetched_at=raw_event.received_at,
                    resolved_person_uid=person_uid,
                    raw_event_id=raw_event.id,
                    derived_signals=_dedupe_signals(signals),
                    related_records=related_records,
                    payload=_safe_payload_projection(provider, raw_event.payload),
                )
            )

        return SourceDataListOut(
            items=items,
            total=len(items),
            totals_by_provider=totals_by_provider,
        )
