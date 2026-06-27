"""Service-level tests for EnrichmentService — validation + audit emission.

The repository and audit service are mocked here; live persistence + tenant
isolation coverage against a real PostgreSQL lands in
``tests/enrichment/test_record_annotation_integration.py`` (per
``packages/CLAUDE.md`` / root ``CLAUDE.md``: integration tests use real
Postgres, not mocks). This unit layer asserts:

* the value text is NEVER placed in the audit ``extra`` (PII safety);
* ``person_uid`` is set in the audit row only when the subject is a person;
* the service-side ``source`` guard fires for callers that bypass the DTO;
* ``latest_per_key`` collapses the newest row per key.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.enrichment.models import RecordAnnotation
from packages.enrichment.schemas import AnnotationIn
from packages.enrichment.service import EnrichmentService


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="staff@example.com",
        roles=frozenset({Role.ADMIN}),
    )


def _make_service() -> tuple[EnrichmentService, MagicMock, MagicMock]:
    session = MagicMock()
    service = EnrichmentService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.add = AsyncMock(side_effect=lambda row: row)
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return service, service._repo, service._audit  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_add_annotation_person_subject_sets_person_uid_and_audit() -> None:
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    subject_id = uuid.uuid4()

    result = await service.add_annotation(
        tenant_id,
        AnnotationIn(
            subject_type="person",
            subject_id=subject_id,
            key="consult_notes",
            value={"text": "Patient prefers morning slots; sensitive note."},
            source="ui",
            note="set during intake call",
        ),
        principal=_principal(),
    )

    assert isinstance(result, RecordAnnotation)
    assert result.tenant_id == tenant_id
    assert result.subject_id == subject_id
    repo.add.assert_awaited_once()

    audit.record.assert_awaited_once()
    kwargs = audit.record.await_args.kwargs
    assert kwargs["action"] == "enrichment.annotation.add"
    assert kwargs["resource"] == "enrichment.record_annotation"
    # person subject → person_uid is the subject id.
    assert kwargs["person_uid"] == subject_id
    extra = kwargs["extra"]
    assert extra == {
        "subject_type": "person",
        "subject_id": str(subject_id),
        "key": "consult_notes",
        "source": "ui",
    }


@pytest.mark.asyncio
async def test_add_annotation_value_text_never_in_audit_extra() -> None:
    """The annotation value (free text / PII) must not leak into audit extra."""
    service, _repo, audit = _make_service()
    secret_text = "DOB 1990-01-01, allergic to penicillin"

    await service.add_annotation(
        TenantId(uuid.uuid4()),
        AnnotationIn(
            subject_type="person",
            subject_id=uuid.uuid4(),
            key="clinical_note",
            value={"text": secret_text},
            source="ui",
        ),
        principal=_principal(),
    )

    extra = audit.record.await_args.kwargs["extra"]
    assert secret_text not in str(extra)
    assert "value" not in extra


@pytest.mark.asyncio
async def test_add_annotation_non_person_subject_has_no_person_uid() -> None:
    service, _repo, audit = _make_service()

    await service.add_annotation(
        TenantId(uuid.uuid4()),
        AnnotationIn(
            subject_type="lead",
            subject_id=uuid.uuid4(),
            key="lost_reason",
            value={"text": "Went with competitor"},
            source="chat",
        ),
        principal=_principal(),
    )

    assert audit.record.await_args.kwargs["person_uid"] is None


@pytest.mark.asyncio
async def test_add_annotation_rejects_invalid_source_via_model_construct() -> None:
    """Service-side guard fires when a caller bypasses the Pydantic literal."""
    service, repo, audit = _make_service()

    bad = AnnotationIn.model_construct(
        subject_type="person",
        subject_id=uuid.uuid4(),
        key="x",
        value={},
        source="webhook",  # type: ignore[arg-type]  — not in the allowed set
        note=None,
        author_actor_id=None,
    )

    with pytest.raises(ValueError, match="invalid annotation source"):
        await service.add_annotation(
            TenantId(uuid.uuid4()), bad, principal=_principal()
        )

    repo.add.assert_not_called()
    audit.record.assert_not_called()


@pytest.mark.asyncio
async def test_latest_per_key_collapses_newest_row_per_key() -> None:
    service, repo, _audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    subject_id = uuid.uuid4()

    def _row(key: str, marker: str) -> RecordAnnotation:
        return RecordAnnotation(
            tenant_id=tenant_id,
            subject_type="person",
            subject_id=subject_id,
            key=key,
            value={"text": marker},
            source="ui",
        )

    # list_for_subject returns newest-first; two rows share key "pref".
    newest_pref = _row("pref", "new")
    older_pref = _row("pref", "old")
    other = _row("note", "only")
    repo.list_for_subject = AsyncMock(return_value=[newest_pref, other, older_pref])

    latest = await service.latest_per_key(tenant_id, "person", subject_id)

    assert latest == [newest_pref, other]
