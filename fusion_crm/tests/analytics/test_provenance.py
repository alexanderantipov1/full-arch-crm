"""Provenance shape + precedence tests for fact_patient_journey (ENG-505)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.analytics.provenance import (
    FieldProvenance,
    auto,
    merge_provenance,
    outranks,
    unresolved,
)

_RESOLVED_AT = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def test_unresolved_shape() -> None:
    prov = unresolved()
    assert prov.method == "unresolved"
    assert prov.confidence is None
    assert prov.to_jsonb() == {
        "source": "unresolved",
        "method": "unresolved",
        "confidence": None,
        "resolved_at": None,
    }


def test_auto_shape_serialises_resolved_at_iso() -> None:
    prov = auto("ops.lead.created_at", confidence=1.0, resolved_at=_RESOLVED_AT)
    blob = prov.to_jsonb()
    assert blob["source"] == "ops.lead.created_at"
    assert blob["method"] == "auto"
    assert blob["confidence"] == 1.0
    assert blob["resolved_at"] == _RESOLVED_AT.isoformat()


def test_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        FieldProvenance(source="x", method="auto", confidence=1.5)
    with pytest.raises(ValidationError):
        FieldProvenance(source="x", method="auto", confidence=-0.1)


def test_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        FieldProvenance(source="x", method="auto", bogus=1)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("candidate", "existing", "expected"),
    [
        ("manual", "auto", True),
        ("manual", "manual", True),
        ("auto", "auto", True),  # rebuild refreshes same-precedence
        ("auto", "unresolved", True),
        ("auto", "manual", False),  # rebuild must NOT clobber manual
        ("unresolved", "auto", False),
        ("unresolved", "manual", False),
    ],
)
def test_outranks(candidate: str, existing: str, expected: bool) -> None:
    assert outranks(candidate, existing) is expected  # type: ignore[arg-type]


def test_merge_first_build_seeds_all_fields() -> None:
    incoming = {
        "lead_date": auto("ops.lead.created_at"),
        "caller_id": unresolved(),
    }
    merged = merge_provenance(None, incoming)
    assert merged["lead_date"]["method"] == "auto"  # type: ignore[index]
    assert merged["caller_id"]["method"] == "unresolved"  # type: ignore[index]


def test_merge_preserves_manual_over_auto_rebuild() -> None:
    prior = {
        "caller_id": FieldProvenance(
            source="staff:enrichment", method="manual", confidence=1.0
        ).to_jsonb(),
    }
    # A rebuild recomputes caller_id as still-unresolved (no canonical signal).
    incoming = {"caller_id": unresolved()}
    merged = merge_provenance(prior, incoming)
    # Manual value's provenance survives the rebuild.
    assert merged["caller_id"]["method"] == "manual"  # type: ignore[index]
    assert merged["caller_id"]["source"] == "staff:enrichment"  # type: ignore[index]


def test_merge_carries_forward_untouched_fields() -> None:
    prior = {"source": auto("ops.lead.source").to_jsonb()}
    incoming = {"lead_date": auto("ops.lead.created_at")}
    merged = merge_provenance(prior, incoming)
    # Prior field absent from incoming is carried forward.
    assert merged["source"]["method"] == "auto"  # type: ignore[index]
    assert merged["lead_date"]["method"] == "auto"  # type: ignore[index]


def test_merge_auto_refreshes_auto() -> None:
    prior = {"lead_date": auto("old.source", confidence=0.5).to_jsonb()}
    incoming = {"lead_date": auto("ops.lead.created_at", confidence=1.0)}
    merged = merge_provenance(prior, incoming)
    assert merged["lead_date"]["source"] == "ops.lead.created_at"  # type: ignore[index]
    assert merged["lead_date"]["confidence"] == 1.0  # type: ignore[index]
