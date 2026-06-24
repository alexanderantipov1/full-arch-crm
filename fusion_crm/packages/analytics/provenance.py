"""Field-level provenance for ``analytics.fact_patient_journey``.

Every projected field records *where its value came from* and *how* — so a
later auto-resolver or manual enrichment can fill an ``unresolved`` field and
the projection still survives a full rebuild. The precedence is

    manual > auto > unresolved

i.e. a rebuild must never overwrite a ``manual`` value with an ``auto`` (or
``unresolved``) one. The builder (ENG-506) carries the prior provenance map
forward and only lets a same-or-higher-precedence method replace a field.

The map is stored as JSONB on ``FactPatientJourney.field_provenance``: a dict
keyed by column name → :class:`FieldProvenance` (serialised). Storing it as a
single JSONB column (rather than per-field ``*_source`` / ``*_confidence``
columns) keeps the fact table's column list aligned with market.md while still
giving every field independent provenance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Resolution method, ordered by precedence (higher index wins on rebuild).
ProvenanceMethod = Literal["unresolved", "auto", "manual"]

_METHOD_RANK: dict[str, int] = {"unresolved": 0, "auto": 1, "manual": 2}


class FieldProvenance(BaseModel):
    """Provenance for one projected field.

    ``source`` is a short canonical-origin tag (e.g. ``"ops.lead.created_at"``,
    ``"interaction.event:payment_recorded"``, ``"attribution.lead_attribution"``,
    or ``"unresolved"`` for a field with no signal yet). ``confidence`` is
    ``None`` when not meaningful (deterministic projections are simply
    ``method='auto'`` with ``confidence=1.0`` or ``None``).
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=128)
    method: ProvenanceMethod = "unresolved"
    confidence: float | None = Field(default=None, ge=0, le=1)
    resolved_at: datetime | None = None

    def to_jsonb(self) -> dict[str, object]:
        """Serialise to a JSON-safe dict for the JSONB column."""
        return {
            "source": self.source,
            "method": self.method,
            "confidence": self.confidence,
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at is not None else None
            ),
        }


def unresolved(source: str = "unresolved") -> FieldProvenance:
    """Provenance for a field with no canonical signal yet (ships NULL)."""
    return FieldProvenance(source=source, method="unresolved", confidence=None)


def auto(
    source: str,
    *,
    confidence: float | None = None,
    resolved_at: datetime | None = None,
) -> FieldProvenance:
    """Provenance for a deterministically projected field."""
    return FieldProvenance(
        source=source, method="auto", confidence=confidence, resolved_at=resolved_at
    )


def manual(
    source: str,
    *,
    confidence: float | None = 1.0,
    resolved_at: datetime | None = None,
) -> FieldProvenance:
    """Provenance for an operator-set / corrected field (ENG-513).

    ``method='manual'`` outranks both ``auto`` and ``unresolved``, so a builder
    rebuild never clobbers a manually enriched field (value or provenance).
    ``source`` records who/what wrote it (e.g. ``"enrichment:ui"``).
    """
    return FieldProvenance(
        source=source, method="manual", confidence=confidence, resolved_at=resolved_at
    )


def outranks(candidate: ProvenanceMethod, existing: ProvenanceMethod) -> bool:
    """True when ``candidate`` may replace a field resolved by ``existing``.

    Equal precedence is allowed to replace (a rebuild refreshes an ``auto``
    field with the latest ``auto`` value); only a *lower*-precedence method is
    blocked (an ``auto`` rebuild must not clobber a ``manual`` value).
    """
    return _METHOD_RANK[candidate] >= _METHOD_RANK[existing]


def merge_provenance(
    prior: dict[str, object] | None,
    incoming: dict[str, FieldProvenance],
) -> dict[str, object]:
    """Merge freshly computed provenance over the prior map, honouring precedence.

    ``prior`` is the JSONB map already stored on the row (``None`` / empty on
    first build). ``incoming`` is the provenance the builder computed this run.
    A field in ``incoming`` replaces the prior entry only when its method
    out-ranks (or equals) the prior method, so manual enrichment is never lost
    on rebuild. Prior fields absent from ``incoming`` are carried forward
    untouched.
    """
    merged: dict[str, object] = dict(prior or {})
    for field, prov in incoming.items():
        existing = merged.get(field)
        existing_method = (
            existing.get("method", "unresolved")
            if isinstance(existing, dict)
            else "unresolved"
        )
        if existing is None or outranks(prov.method, existing_method):  # type: ignore[arg-type]
            merged[field] = prov.to_jsonb()
    return merged
