"""Manual enrichment of ``analytics.fact_patient_journey`` fields (ENG-513).

The single write path for an operator to set/correct a fact field (caller,
coordinator, doctor, campaign/vendor, treatment_accepted, surgery dates,
marketing cost) on a person. One edit does two things in the SAME unit of work:

1. records a ``enrichment.record_annotation`` row (+ its ``audit.access_log``
   row) via :class:`packages.enrichment.service.EnrichmentService` — the
   durable who/when/what of the edit, and
2. applies the value into the fact row with provenance ``method='manual'``.

Provenance precedence is **manual > auto > unresolved**: a builder rebuild
(:class:`packages.analytics.fact_builder.FactPatientJourneyBuilder`) preserves
both the manual value and its provenance, so the operator's correction survives.

This service is the composition layer — it owns no SQL. It never commits; the
caller boundary (the API ``get_db`` dependency / a worker job / a test) owns the
unit of work, so the annotation, the audit row, and the fact mutation commit or
roll back together.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.enrichment.schemas import AnnotationIn
from packages.enrichment.service import EnrichmentService

from .case_type import ALL_CASE_TYPES
from .fact_repository import FactPatientJourneyRepository
from .provenance import manual
from .schemas import FactFieldProvenanceOut, FactOverrideOut

# Field value kinds → how the string/number input is coerced to the column type.
_FieldKind = Literal["uuid", "str", "datetime", "numeric", "case_type"]

# The fact columns an operator may override and their value kind. Keep in sync
# with ``schemas.FactOverridableField``.
_OVERRIDABLE: dict[str, _FieldKind] = {
    "caller_id": "uuid",
    "coordinator_id": "uuid",
    "doctor_id": "uuid",
    "campaign_id": "uuid",
    "campaign_name": "str",
    "vendor_id": "uuid",
    # ENG-539: case_type override (manual > auto). Accepts the auto values AND
    # the manual-only / future labels (all_on_4, all_on_6, zygomatic, arch
    # side) the CDT resolver can never derive — that is the whole point of the
    # manual path. Validated against ``ALL_CASE_TYPES``.
    "case_type": "case_type",
    "treatment_accepted_date": "datetime",
    "surgery_scheduled_date": "datetime",
    "surgery_completed_date": "datetime",
    "marketing_cost_allocated": "numeric",
}

# Annotation namespace: a fact-field override is stored under key ``fact.<col>``
# so it is distinguishable from other person annotations.
_ANNOTATION_KEY_PREFIX = "fact."
_PERSON_SUBJECT = "person"
_MANUAL_SOURCE = "enrichment:ui"


class FactEnrichmentService:
    """Apply operator overrides to ``fact_patient_journey`` (ENG-513)."""

    def __init__(
        self,
        *,
        enrichment: EnrichmentService,
        repo: FactPatientJourneyRepository,
    ) -> None:
        self._enrichment = enrichment
        self._repo = repo

    async def set_override(
        self,
        tenant_id: TenantId,
        *,
        person_uid: UUID,
        field: str,
        value: str | float | int | None,
        principal: Principal,
        note: str | None = None,
        author_actor_id: UUID | None = None,
        now: datetime | None = None,
    ) -> FactOverrideOut:
        """Set ONE fact field to an operator value with manual provenance.

        Records the annotation (+ audit) and applies the override into the fact
        row. ``value`` is a string / number (coerced to the column type) or
        ``None`` to clear the field. Raises :class:`ValidationError` for an
        unknown field or an uncoercible value.
        """
        kind = _OVERRIDABLE.get(field)
        if kind is None:
            raise ValidationError(
                "field is not operator-overridable",
                details={"field": field, "allowed": sorted(_OVERRIDABLE)},
            )

        column_value = _coerce(field, kind, value)
        resolved_now = now or datetime.now(tz=UTC)

        # 1) Annotation + audit (one row per edit) — the durable record of the
        #    edit. The annotation ``value`` carries the canonical JSON form.
        await self._enrichment.add_annotation(
            tenant_id,
            AnnotationIn(
                subject_type=_PERSON_SUBJECT,
                subject_id=person_uid,
                key=f"{_ANNOTATION_KEY_PREFIX}{field}",
                value={"value": _json_value(column_value)},
                source="ui",
                note=note,
                author_actor_id=author_actor_id,
            ),
            principal=principal,
        )

        # 2) Apply into the fact row with manual provenance (highest precedence).
        provenance = manual(_MANUAL_SOURCE, resolved_at=resolved_now)
        await self._repo.apply_manual_override(
            person_uid,
            field,
            column_value,
            provenance_entry=provenance.to_jsonb(),
        )

        return FactOverrideOut(
            person_uid=person_uid,
            applied=FactFieldProvenanceOut(
                field=field,
                value=_json_value(column_value),
                method="manual",
                source=_MANUAL_SOURCE,
                confidence=provenance.confidence,
                resolved_at=resolved_now,
            ),
        )


def _coerce(field: str, kind: _FieldKind, value: str | float | int | None) -> object:
    """Coerce a raw override value to the fact column's python type."""
    if value is None:
        return None
    try:
        if kind == "uuid":
            return UUID(str(value))
        if kind == "str":
            text = str(value).strip()
            if not text:
                return None
            return text
        if kind == "case_type":
            text = str(value).strip()
            if not text:
                return None
            if text not in ALL_CASE_TYPES:
                raise ValidationError(
                    "case_type is not an allowed value",
                    details={"value": text, "allowed": sorted(ALL_CASE_TYPES)},
                )
            return text
        if kind == "datetime":
            return _parse_datetime(str(value))
        if kind == "numeric":
            return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValidationError(
            "could not coerce override value to the field type",
            details={"field": field, "kind": kind, "value": str(value)},
        ) from exc
    raise ValidationError("unknown field kind", details={"field": field})


def _parse_datetime(raw: str) -> datetime:
    """Parse an ISO-8601 string to a tz-aware UTC datetime."""
    text = raw.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _json_value(value: object) -> str | None:
    """Render a coerced column value as a JSON-safe string for the annotation."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
