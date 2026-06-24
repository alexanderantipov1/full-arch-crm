"""Tests for the ENG-382 funnel segment services (Contact / Account /
OpportunityHistory).

Mock-based service tests following the established per-service style:
stubbed SF client + MagicMock collaborators. Real-PG round-trips for the
funnel glue live in ``test_ingest_idempotency_sql.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.sf_account_service import SfAccountIngestService
from packages.ingest.sf_contact_service import SfContactIngestService
from packages.ingest.sf_opportunity_history_service import (
    SfOpportunityHistoryIngestService,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_RAW_EVENT_ID = uuid.uuid4()


def _ingest_mock() -> MagicMock:
    ingest = MagicMock(
        spec=[
            "capture",
            "capture_normalized_person_hint",
            "max_payload_watermark",
            "latest_payload_values",
            "latest_payload",
            "get_object_schema",
        ]
    )
    ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=_RAW_EVENT_ID, received_at=datetime.now(UTC))
    )
    ingest.max_payload_watermark = AsyncMock(return_value=None)
    ingest.latest_payload_values = AsyncMock(return_value={})
    # ENG-427: empty registry → dynamic projection falls back to static.
    ingest.get_object_schema = AsyncMock(return_value=[])
    ingest.latest_payload = AsyncMock(return_value=None)
    return ingest


# --------------------------------------------------------------- Contact


def _contact(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "003CONTACT01",
        "FirstName": "Vlad",
        "LastName": "Romanchuk",
        "Email": "vlad@example.test",
        "Phone": "+19255550000",
        "MobilePhone": None,
        "AccountId": "001ACC01",
        "OwnerId": "005X",
        "CreatedDate": "2026-06-09T10:00:00.000+0000",
        "LastModifiedDate": "2026-06-09T10:00:00.000+0000",
    }
    base.update(overrides)
    return base


def _make_contact_service(
    records: list[dict[str, Any]] | None = None,
) -> tuple[SfContactIngestService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(return_value={"records": records or [_contact()]})
    service = SfContactIngestService(session, sf_client)

    ingest = _ingest_mock()
    ingest.capture_normalized_person_hint = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            source_system="salesforce",
            source_kind="contact",
            source_id="003CONTACT01",
            given_name="Vlad",
            family_name="Romanchuk",
            display_name="Vlad Romanchuk",
            email_normalized="vlad@example.test",
            phone_normalized="+19255550000",
            quality_flags={},
            meta={},
        )
    )
    service._ingest = ingest  # type: ignore[attr-defined]

    identity = MagicMock(spec=["resolve_or_create_from_hint", "get_person"])
    identity.resolve_or_create_from_hint = AsyncMock(
        return_value=SimpleNamespace(
            person_uid=_PERSON_UID, was_existing_person_match=True
        )
    )
    identity.get_person = AsyncMock(return_value=SimpleNamespace(id=_PERSON_UID))
    service._identity = identity  # type: ignore[attr-defined]

    interaction = MagicMock(spec=["create_event_idempotent"])
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(was_created=True)
    )
    service._interaction = interaction  # type: ignore[attr-defined]
    return service, ingest, identity, interaction


@pytest.mark.asyncio
async def test_contact_import_captures_resolves_and_emits_event() -> None:
    service, ingest, identity, interaction = _make_contact_service()

    result = await service.import_recent_contacts(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.unchanged_count == 0
    ingest.capture.assert_awaited_once()
    identity.resolve_or_create_from_hint.assert_awaited_once()
    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "contact_created"
    assert event_in.source_kind == "salesforce_contact"
    assert event_in.person_uid == _PERSON_UID
    # No-PII payload contract.
    assert event_in.payload == {"sf_contact_id": "003CONTACT01"}


@pytest.mark.asyncio
async def test_contact_capture_guard_skips_unchanged_stamp() -> None:
    contact = _contact()
    service, ingest, identity, interaction = _make_contact_service([contact])
    ingest.latest_payload_values = AsyncMock(
        return_value={contact["Id"]: contact["LastModifiedDate"]}
    )

    result = await service.import_recent_contacts(_TENANT_ID, days=7)

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()
    identity.resolve_or_create_from_hint.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


# --------------------------------------------------------------- Account


def _account(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "001ACC01",
        "Name": "Vlad Romanchuk",
        "Phone": "+19255550000",
        "Type": None,
        "OwnerId": "005X",
        "CreatedDate": "2026-06-09T10:00:00.000+0000",
        "LastModifiedDate": "2026-06-09T10:00:00.000+0000",
    }
    base.update(overrides)
    return base


def _make_account_service(
    records: list[dict[str, Any]] | None = None,
    *,
    person_uid: uuid.UUID | None = _PERSON_UID,
) -> tuple[SfAccountIngestService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(return_value={"records": records or [_account()]})
    service = SfAccountIngestService(session, sf_client)

    ingest = _ingest_mock()
    service._ingest = ingest  # type: ignore[attr-defined]

    ops = MagicMock(
        spec=["record_account", "find_lead_person_by_converted_account"]
    )
    ops.record_account = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    ops.find_lead_person_by_converted_account = AsyncMock(return_value=person_uid)
    service._ops = ops  # type: ignore[attr-defined]

    identity = MagicMock(spec=["add_source_link"])
    identity.add_source_link = AsyncMock(return_value=SimpleNamespace())
    service._identity = identity  # type: ignore[attr-defined]
    return service, ingest, ops, identity


@pytest.mark.asyncio
async def test_account_import_projects_ops_account_and_links_person() -> None:
    service, ingest, ops, identity = _make_account_service()

    result = await service.import_recent_accounts(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.linked_count == 1
    ingest.capture.assert_awaited_once()
    ops.record_account.assert_awaited_once()
    record_kwargs = ops.record_account.await_args.kwargs
    assert record_kwargs["provider"] == "salesforce"
    assert record_kwargs["source_id"] == "001ACC01"
    identity.add_source_link.assert_awaited_once()
    link_kwargs = identity.add_source_link.await_args.kwargs
    assert link_kwargs["source_kind"] == "account"
    assert link_kwargs["person_uid"] == _PERSON_UID


@pytest.mark.asyncio
async def test_account_without_converted_lead_still_imports() -> None:
    service, ingest, _, identity = _make_account_service(person_uid=None)

    result = await service.import_recent_accounts(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.linked_count == 0
    ingest.capture.assert_awaited_once()
    identity.add_source_link.assert_not_awaited()


# ----------------------------------------------------- OpportunityHistory


def _history_row(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "008HIST01",
        "OpportunityId": "006OPP01",
        "StageName": "Surgery Completed",
        "Amount": 15000.0,
        "CloseDate": "2026-03-25",
        "Probability": 90.0,
        "CreatedDate": "2026-06-09T10:00:00.000+0000",
        "CreatedById": "005X",
    }
    base.update(overrides)
    return base


def _make_history_service(
    records: list[dict[str, Any]] | None = None,
    *,
    person_uid: uuid.UUID | None = _PERSON_UID,
) -> tuple[SfOpportunityHistoryIngestService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(return_value={"records": records or [_history_row()]})
    service = SfOpportunityHistoryIngestService(session, sf_client)

    ingest = _ingest_mock()
    service._ingest = ingest  # type: ignore[attr-defined]

    ops = MagicMock(spec=["find_lead_person_by_converted_opportunity"])
    ops.find_lead_person_by_converted_opportunity = AsyncMock(
        return_value=person_uid
    )
    service._ops = ops  # type: ignore[attr-defined]

    identity_repo = MagicMock(spec=["find_source_link"])
    identity_repo.find_source_link = AsyncMock(return_value=None)
    service._identity_repo = identity_repo  # type: ignore[attr-defined]

    interaction = MagicMock(spec=["create_event_idempotent"])
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(was_created=True)
    )
    service._interaction = interaction  # type: ignore[attr-defined]
    return service, ingest, ops, interaction


@pytest.mark.asyncio
async def test_history_emits_stage_changed_event_without_amount() -> None:
    service, ingest, _, interaction = _make_history_service()

    result = await service.import_recent_history(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "opportunity_stage_changed"
    assert event_in.source_kind == "salesforce_opportunity_history"
    assert event_in.payload == {
        "sf_opportunity_id": "006OPP01",
        "stage": "Surgery Completed",
    }
    # Amounts must never leak into summaries or payloads.
    assert "15000" not in str(event_in.payload)
    assert "15000" not in event_in.summary


@pytest.mark.asyncio
async def test_history_without_person_link_captures_raw_only() -> None:
    service, ingest, _, interaction = _make_history_service(person_uid=None)

    result = await service.import_recent_history(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_capture_guard_skips_recaptured_rows() -> None:
    row = _history_row()
    service, ingest, _, interaction = _make_history_service([row])
    ingest.latest_payload_values = AsyncMock(
        return_value={row["Id"]: row["CreatedDate"]}
    )

    result = await service.import_recent_history(_TENANT_ID, days=7)

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()
