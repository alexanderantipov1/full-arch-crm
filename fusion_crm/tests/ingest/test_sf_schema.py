"""Pure-function tests for the SF full-fidelity schema helpers (ENG-427).

No live Salesforce: ``describe`` and Tooling ``FieldDefinition`` shapes are
hand-built so the projection / observation / FLS-gap logic is locked in
deterministically.
"""

from __future__ import annotations

from packages.ingest.sf_schema import (
    build_observed_fields,
    build_projection,
    fls_gap,
    selectable_fields,
)


def _describe(*fields: dict[str, object]) -> dict[str, object]:
    return {"fields": list(fields)}


def _f(name: str, ftype: str = "string", *, custom: bool = False) -> dict[str, object]:
    return {"name": name, "type": ftype, "custom": custom}


# --- selectable_fields / build_projection ---


def test_selectable_keeps_order_and_drops_blob_and_compound() -> None:
    describe = _describe(
        _f("Id"),
        _f("Name"),
        _f("Body", "base64"),  # blob — skip
        _f("Address", "address"),  # compound parent — skip
        _f("Street"),  # component — keep
        _f("City"),
        _f("utm_source__c", "string", custom=True),
    )
    assert selectable_fields(describe) == [
        "Id",
        "Name",
        "Street",
        "City",
        "utm_source__c",
    ]


def test_build_projection_is_comma_joined() -> None:
    describe = _describe(_f("Id"), _f("CreatedById"), _f("Email", "email"))
    assert build_projection(describe) == "Id, CreatedById, Email"


def test_build_projection_raises_when_no_selectable_fields() -> None:
    # Only a blob field — nothing selectable.
    describe = _describe(_f("Body", "base64"))
    try:
        build_projection(describe)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_empty_describe_yields_no_fields() -> None:
    assert selectable_fields({}) == []
    assert selectable_fields({"fields": None}) == []


def test_duplicate_field_names_are_deduped() -> None:
    describe = _describe(_f("Id"), _f("Id"))
    assert selectable_fields(describe) == ["Id"]


# --- build_observed_fields ---


def test_observed_fields_mark_describe_readable_and_tooling_blocked() -> None:
    describe = _describe(_f("Id"), _f("utm_source__c", "string", custom=True))
    tooling = [
        {"QualifiedApiName": "Id", "DataType": "Lookup(...)"},  # already readable
        {"QualifiedApiName": "SSN__c", "DataType": "Text(9)"},  # FLS-blocked
    ]
    observed = build_observed_fields(describe, tooling)
    by_name = {o.name: o for o in observed}

    assert by_name["Id"].readable is True
    assert by_name["utm_source__c"].readable is True
    assert by_name["utm_source__c"].meta["custom"] is True
    # FLS-blocked field came only from Tooling.
    assert by_name["SSN__c"].readable is False
    assert by_name["SSN__c"].meta["fls_blocked"] is True
    assert by_name["SSN__c"].field_type == "Text(9)"


def test_observed_field_type_is_truncated_to_column_width() -> None:
    describe = _describe()
    long_type = "Roll-Up Summary (COUNT Opportunity where amount > 0 and ...)"
    tooling = [{"QualifiedApiName": "Big__c", "DataType": long_type}]
    observed = build_observed_fields(describe, tooling)
    assert observed[0].field_type is not None
    assert len(observed[0].field_type) <= 64


def test_compound_parent_is_observed_but_not_selectable() -> None:
    describe = _describe(_f("Address", "address"), _f("City"))
    observed = {o.name: o for o in build_observed_fields(describe, [])}
    assert observed["Address"].readable is True
    assert observed["Address"].meta["selectable"] is False
    assert observed["City"].meta["selectable"] is True


# --- fls_gap ---


def test_fls_gap_is_tooling_minus_describe_sorted() -> None:
    describe = _describe(_f("Id"), _f("Email", "email"))
    tooling = [
        {"QualifiedApiName": "Email", "DataType": "Email"},
        {"QualifiedApiName": "SSN__c", "DataType": "Text"},
        {"QualifiedApiName": "CreatedById", "DataType": "Lookup"},
    ]
    assert fls_gap(describe, tooling) == ["CreatedById", "SSN__c"]


def test_fls_gap_ignores_casing_difference() -> None:
    # Tooling reports "CreatedByID"; describe reports "CreatedById" — same
    # field, must NOT be flagged as FLS-blocked (real-data regression).
    describe = _describe(_f("Id"), _f("CreatedById", "reference"))
    tooling = [
        {"QualifiedApiName": "CreatedByID", "DataType": "Lookup"},
        {"QualifiedApiName": "CampaignId", "DataType": "Lookup"},
    ]
    assert fls_gap(describe, tooling) == ["CampaignId"]


def test_observed_fields_dedupe_casing_against_describe() -> None:
    describe = _describe(_f("CreatedById", "reference"))
    tooling = [{"QualifiedApiName": "CreatedByID", "DataType": "Lookup"}]
    observed = build_observed_fields(describe, tooling)
    # Only the describe (readable) row — no duplicate FLS-blocked row.
    assert len(observed) == 1
    assert observed[0].name == "CreatedById"
    assert observed[0].readable is True


def test_fls_gap_empty_when_describe_covers_everything() -> None:
    describe = _describe(_f("Id"), _f("Name"))
    tooling = [
        {"QualifiedApiName": "Id", "DataType": "Id"},
        {"QualifiedApiName": "Name", "DataType": "Text"},
    ]
    assert fls_gap(describe, tooling) == []
