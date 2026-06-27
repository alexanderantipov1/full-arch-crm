"""Unit tests for the manual fact-field enrichment service (ENG-513).

DB-free: the ``EnrichmentService`` (annotation + audit) and the fact repository
are fakes, so these lock the coercion + dual-write logic (one annotation, one
manual-provenance fact override) and the validation rules without a Postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.analytics.enrichment_service import FactEnrichmentService
from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())
_PERSON = uuid.uuid4()
_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
_PRINCIPAL = Principal(id=None, email=None, tenant_id=_TENANT)


class _FakeEnrichment:
    def __init__(self) -> None:
        self.annotations: list = []

    async def add_annotation(self, tenant_id, data, *, principal):  # type: ignore[no-untyped-def]
        self.annotations.append(data)
        return data


class _FakeRepo:
    def __init__(self) -> None:
        self.overrides: list[tuple] = []

    async def apply_manual_override(  # type: ignore[no-untyped-def]
        self, person_uid, field, value, *, provenance_entry
    ):
        self.overrides.append((person_uid, field, value, provenance_entry))


def _service() -> tuple[FactEnrichmentService, _FakeEnrichment, _FakeRepo]:
    enrichment = _FakeEnrichment()
    repo = _FakeRepo()
    svc = FactEnrichmentService(enrichment=enrichment, repo=repo)  # type: ignore[arg-type]
    return svc, enrichment, repo


async def test_uuid_field_override_writes_annotation_and_fact() -> None:
    svc, enrichment, repo = _service()
    actor_id = uuid.uuid4()
    out = await svc.set_override(
        _TENANT,
        person_uid=_PERSON,
        field="caller_id",
        value=str(actor_id),
        principal=_PRINCIPAL,
        now=_NOW,
    )
    # One annotation under the fact.<field> key, source ui.
    assert len(enrichment.annotations) == 1
    ann = enrichment.annotations[0]
    assert ann.key == "fact.caller_id"
    assert ann.source == "ui"
    assert ann.subject_type == "person"
    assert ann.subject_id == _PERSON
    # One fact override, coerced to UUID, manual provenance.
    assert len(repo.overrides) == 1
    person_uid, field, value, prov = repo.overrides[0]
    assert person_uid == _PERSON
    assert field == "caller_id"
    assert value == actor_id
    assert prov["method"] == "manual"
    # Response echoes the applied state.
    assert out.applied.method == "manual"
    assert out.applied.field == "caller_id"


async def test_datetime_field_coerced_to_aware_datetime() -> None:
    svc, _enrichment, repo = _service()
    await svc.set_override(
        _TENANT,
        person_uid=_PERSON,
        field="surgery_completed_date",
        value="2026-05-01T09:30:00Z",
        principal=_PRINCIPAL,
        now=_NOW,
    )
    _p, _f, value, _prov = repo.overrides[0]
    assert value == datetime(2026, 5, 1, 9, 30, tzinfo=UTC)


async def test_numeric_field_coerced_to_decimal() -> None:
    svc, _enrichment, repo = _service()
    await svc.set_override(
        _TENANT,
        person_uid=_PERSON,
        field="marketing_cost_allocated",
        value="123.45",
        principal=_PRINCIPAL,
        now=_NOW,
    )
    _p, _f, value, _prov = repo.overrides[0]
    assert value == Decimal("123.45")


async def test_null_value_clears_field() -> None:
    svc, _enrichment, repo = _service()
    await svc.set_override(
        _TENANT,
        person_uid=_PERSON,
        field="doctor_id",
        value=None,
        principal=_PRINCIPAL,
        now=_NOW,
    )
    _p, _f, value, prov = repo.overrides[0]
    assert value is None
    assert prov["method"] == "manual"


async def test_case_type_override_accepts_manual_only_value() -> None:  # ENG-539
    # all_on_4 is a manual-only label the CDT resolver can never produce.
    svc, enrichment, repo = _service()
    out = await svc.set_override(
        _TENANT,
        person_uid=_PERSON,
        field="case_type",
        value="all_on_4",
        principal=_PRINCIPAL,
        now=_NOW,
    )
    assert enrichment.annotations[0].key == "fact.case_type"
    _p, field, value, prov = repo.overrides[0]
    assert field == "case_type"
    assert value == "all_on_4"
    assert prov["method"] == "manual"
    assert out.applied.method == "manual"


async def test_case_type_override_rejects_unknown_value() -> None:  # ENG-539
    svc, _enrichment, _repo = _service()
    with pytest.raises(ValidationError):
        await svc.set_override(
            _TENANT,
            person_uid=_PERSON,
            field="case_type",
            value="not_a_case_type",
            principal=_PRINCIPAL,
        )


async def test_unknown_field_rejected() -> None:
    svc, _enrichment, _repo = _service()
    with pytest.raises(ValidationError):
        await svc.set_override(
            _TENANT,
            person_uid=_PERSON,
            field="person_uid",  # not overridable
            value=str(uuid.uuid4()),
            principal=_PRINCIPAL,
        )


async def test_uncoercible_uuid_rejected() -> None:
    svc, _enrichment, _repo = _service()
    with pytest.raises(ValidationError):
        await svc.set_override(
            _TENANT,
            person_uid=_PERSON,
            field="caller_id",
            value="not-a-uuid",
            principal=_PRINCIPAL,
        )
