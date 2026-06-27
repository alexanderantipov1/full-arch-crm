"""Pure helpers: Salesforce describe + Tooling fields -> projection & registry.

Block B of the Full-Fidelity Ingestion Framework (ENG-427). These functions
are deliberately pure (no I/O) so they can be unit-tested without a live
Salesforce org: the SF ingest services fetch ``describe`` + Tooling field rows
through the injected client, then call here to build the dynamic SOQL
projection and the schema-registry observations.

Two Salesforce field views feed in:

* ``describe`` (``GET /sobjects/<obj>/describe``) — the fields the integration
  user can actually read (Field-Level-Security-aware). We SELECT from this set
  and mark these fields ``readable=True`` in the registry.
* Tooling ``FieldDefinition`` — the FULL field list regardless of FLS. Fields
  present here but absent from ``describe`` are FLS-blocked; we record them
  ``readable=False`` so the gap is knowable and the admin gets an exact list.

See ``.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`` (principle 4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .schemas import ObservedFieldIn

# Field types we do NOT put in a SOQL SELECT:
# - ``base64``: blob fields (e.g. Attachment.Body) are not selectable in a
#   normal SOQL query; they are fetched via a separate blob endpoint.
# - ``address`` / ``location``: compound PARENT fields. Their components
#   (Street, City, State, PostalCode, Country / Latitude, Longitude) are
#   separate selectable fields in the same describe, so we capture the data
#   through the components and skip the compound wrapper.
_SKIP_SELECT_TYPES = frozenset({"base64", "address", "location"})

# Registry ``field_type`` column is String(64); Tooling ``DataType`` labels
# such as "Roll-Up Summary (COUNT Opportunity)" can exceed that.
_FIELD_TYPE_MAX = 64


def _field_name(field: Mapping[str, Any]) -> str | None:
    name = field.get("name")
    return name if isinstance(name, str) and name else None


def _field_type(field: Mapping[str, Any]) -> str | None:
    ftype = field.get("type")
    return ftype if isinstance(ftype, str) and ftype else None


def selectable_fields(describe_result: Mapping[str, Any]) -> list[str]:
    """Ordered list of API names safe to put in a SOQL SELECT.

    Preserves Salesforce's describe field order (stable) and drops blob /
    compound-parent types per ``_SKIP_SELECT_TYPES``.
    """
    fields = describe_result.get("fields")
    if not isinstance(fields, Sequence):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, Mapping):
            continue
        name = _field_name(field)
        if name is None or name in seen:
            continue
        ftype = (_field_type(field) or "").lower()
        if ftype in _SKIP_SELECT_TYPES:
            continue
        seen.add(name)
        out.append(name)
    return out


def build_projection(describe_result: Mapping[str, Any]) -> str:
    """Build the full-fidelity SOQL projection (comma-separated field list).

    Raises ``ValueError`` when the describe yields no selectable fields — a
    caller should then fall back to its static projection rather than emit an
    invalid ``SELECT  FROM``.
    """
    names = selectable_fields(describe_result)
    if not names:
        raise ValueError("describe produced no selectable fields")
    return ", ".join(names)


def _truncate_type(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:_FIELD_TYPE_MAX]


def build_observed_fields(
    describe_result: Mapping[str, Any],
    tooling_fields: Sequence[Mapping[str, Any]],
) -> list[ObservedFieldIn]:
    """Registry observations: readable fields from describe + FLS-blocked
    fields from Tooling.

    Every describe field is ``readable=True``. Every Tooling ``FieldDefinition``
    not present in describe is ``readable=False`` with ``meta.fls_blocked``.
    """
    observed: list[ObservedFieldIn] = []
    described_names: set[str] = set()
    # Case-insensitive index of describe field names. Salesforce's Tooling
    # ``FieldDefinition.QualifiedApiName`` and the sObject describe ``name``
    # can differ only in casing for the SAME field (e.g. Tooling
    # ``CreatedByID`` vs describe ``CreatedById``). Matching case-sensitively
    # would falsely flag such a field as FLS-blocked and write a duplicate
    # registry row. Verified against the real Lead object (ENG-427).
    described_lower: set[str] = set()

    fields = describe_result.get("fields")
    if isinstance(fields, Sequence):
        for field in fields:
            if not isinstance(field, Mapping):
                continue
            name = _field_name(field)
            if name is None or name in described_names:
                continue
            described_names.add(name)
            described_lower.add(name.lower())
            ftype = (_field_type(field) or "").lower()
            observed.append(
                ObservedFieldIn(
                    name=name,
                    field_type=_truncate_type(_field_type(field)),
                    readable=True,
                    meta={
                        "custom": bool(field.get("custom")),
                        "selectable": ftype not in _SKIP_SELECT_TYPES,
                    },
                )
            )

    seen_tooling: set[str] = set()
    for tf in tooling_fields:
        if not isinstance(tf, Mapping):
            continue
        api = tf.get("QualifiedApiName")
        if not isinstance(api, str) or not api:
            continue
        api_lower = api.lower()
        if api_lower in described_lower or api_lower in seen_tooling:
            continue
        seen_tooling.add(api_lower)
        data_type = tf.get("DataType")
        observed.append(
            ObservedFieldIn(
                name=api,
                field_type=_truncate_type(
                    data_type if isinstance(data_type, str) else None
                ),
                readable=False,
                meta={"fls_blocked": True, "source": "tooling"},
            )
        )

    return observed


def fls_gap(
    describe_result: Mapping[str, Any],
    tooling_fields: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Sorted API names present in Tooling but hidden from describe by FLS.

    This is the exact remediation list for the Salesforce admin: grant the
    integration user Field-Level-Security read on these fields to reach 100%.
    """
    # Case-insensitive describe index — see build_observed_fields for why
    # (Tooling ``CreatedByID`` vs describe ``CreatedById`` is one field).
    described_lower: set[str] = set()
    fields = describe_result.get("fields")
    if isinstance(fields, Sequence):
        for field in fields:
            if isinstance(field, Mapping):
                name = _field_name(field)
                if name is not None:
                    described_lower.add(name.lower())
    gap: set[str] = set()
    for tf in tooling_fields:
        if not isinstance(tf, Mapping):
            continue
        api = tf.get("QualifiedApiName")
        if isinstance(api, str) and api and api.lower() not in described_lower:
            gap.add(api)
    return sorted(gap)
