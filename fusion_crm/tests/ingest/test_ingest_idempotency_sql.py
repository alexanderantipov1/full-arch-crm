"""Real-PostgreSQL double-import idempotency tests (ENG-381 / ENG-384).

The core acceptance criterion: re-running a pull against UNCHANGED
provider data writes ZERO new ``ingest.raw_event`` rows. Unit tests
cover the guard logic with mocks; these tests exercise the real
``latest_payload_values`` SQL against PostgreSQL through a full
service round-trip with a stubbed provider client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from tests.conftest import TENANT_SCHEMA_AVAILABLE, TwoTenantContext

_OPP_RECORD = {
    "Id": "006IDEMPOTENT01",
    "Name": "Idempotency Probe",
    "StageName": "New",
    "Amount": None,
    "CloseDate": None,
    "AccountId": None,
    "OwnerId": "005X",
    "CreatedDate": "2026-06-01T10:00:00.000+0000",
    "LastModifiedDate": "2026-06-08T10:00:00.000+0000",
    "Type": None,
    "LeadSource": None,
    "Probability": None,
    "IsClosed": False,
    "IsWon": False,
}


# ENG-384: rows for the CareStack accounting_transaction + invoice guard
# tests. Both omit ``patientId`` so the capture-then-route path falls
# through to ``skipped`` for emit but the raw_event is still captured —
# enough surface to assert the change-guard's count against the DB.
_ACCT_RECORD: dict[str, Any] = {
    "id": 88001,
    "accountId": 17,
    "transactionDate": "2026-05-22T14:00:00Z",
    "providerId": 3,
    "transactionType": "credit",
    "amount": 125.50,
    "transactionCode": "PATIENTPAYMENTS",
    "invoiceId": 5501,
    "locationId": 10029,
    "isReversed": False,
    "lastUpdatedOn": "2026-05-22T14:01:00Z",
    "patientId": None,
}

_INVOICE_RECORD: dict[str, Any] = {
    "invoiceId": 5501,
    "patientId": None,
    "locationId": 10029,
    "providerId": 3,
    "amount": 250.0,
    "invoiceType": 1,
    "paymentDate": "2026-05-22T14:00:00Z",
    "lastUpdatedOn": "2026-05-22T14:01:00Z",
    "isDeleted": False,
}


class _StubSfClient:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.queries: list[str] = []

    async def describe(self, _resource: str) -> dict[str, Any]:
        # Empty describe → dynamic projection falls back to static (ENG-427).
        return {"fields": []}

    async def describe_tooling_fields(self, _resource: str) -> list[dict[str, Any]]:
        return []

    async def soql(self, query: str) -> dict[str, Any]:
        self.queries.append(query)
        return {"records": self.records}


class _StubCsAccountingClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[datetime] = []

    async def list_accounting_transactions_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(modified_since)
        return {"accountingTransactions": list(self.rows), "continueToken": None}


class _StubCsInvoiceClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[datetime] = []

    async def list_invoices_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(modified_since)
        return {"invoices": list(self.rows), "continueToken": None}


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_opportunity_double_import_writes_raw_once(
    two_tenant_db: TwoTenantContext,
) -> None:
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.models import RawEvent
    from packages.ingest.sf_opportunity_service import SfOpportunityIngestService

    service = SfOpportunityIngestService(session, _StubSfClient([dict(_OPP_RECORD)]))

    first = await service.import_recent_opportunities(tenant_id, days=7)
    await session.flush()
    second = await service.import_recent_opportunities(tenant_id, days=7)
    await session.flush()

    assert first.imported_count == 1
    assert first.unchanged_count == 0
    assert second.imported_count == 0
    assert second.unchanged_count == 1

    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "salesforce.opportunity.upsert",
                RawEvent.external_id == _OPP_RECORD["Id"],
            )
        )
    ).scalar_one()
    assert raw_count == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_opportunity_change_writes_second_raw_row(
    two_tenant_db: TwoTenantContext,
) -> None:
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.models import RawEvent
    from packages.ingest.sf_opportunity_service import SfOpportunityIngestService

    stub = _StubSfClient([dict(_OPP_RECORD)])
    service = SfOpportunityIngestService(session, stub)

    await service.import_recent_opportunities(tenant_id, days=7)
    await session.flush()

    moved = dict(_OPP_RECORD)
    moved["StageName"] = "Surgery Completed"
    moved["LastModifiedDate"] = "2026-06-09T09:00:00.000+0000"
    stub.records = [moved]

    result = await service.import_recent_opportunities(tenant_id, days=7)
    await session.flush()

    assert result.imported_count == 1
    assert result.unchanged_count == 0

    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "salesforce.opportunity.upsert",
                RawEvent.external_id == _OPP_RECORD["Id"],
            )
        )
    ).scalar_one()
    assert raw_count == 2

    # The second run resumed from the first capture's watermark, not the
    # 7-day fallback window (overlap-adjusted stamp appears in the SOQL).
    assert "2026-06-08T09:50:00Z" in stub.queries[1]


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_opportunity_resolves_person_via_converted_lead(
    two_tenant_db: TwoTenantContext,
) -> None:
    """ENG-382 funnel glue: an Opportunity with no account link resolves
    to a person through the lead that stored its ConvertedOpportunityId,
    and an opportunity timeline event lands for that person."""
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id
    person_uid = two_tenant_db.seeded_ids["identity_person"]["tenant_a"]

    from packages.ingest.sf_opportunity_service import SfOpportunityIngestService
    from packages.interaction.models import Event
    from packages.ops.models import Lead

    opp_id = "006CONVERTED01"
    session.add(
        Lead(
            tenant_id=tenant_id,
            person_uid=person_uid,
            source=None,
            extra={
                "sf_lead_id": "00QCONVERTED01",
                "lead_status": "Qualified",
                "lead_source": None,
                "is_converted": True,
                "converted_opportunity_id": opp_id,
            },
        )
    )
    await session.flush()

    record = dict(_OPP_RECORD)
    record["Id"] = opp_id
    service = SfOpportunityIngestService(session, _StubSfClient([record]))

    result = await service.import_recent_opportunities(tenant_id, days=7)
    await session.flush()

    assert result.imported_count == 1

    events = (
        (
            await session.execute(
                select(Event).where(
                    Event.tenant_id == tenant_id,
                    Event.person_uid == person_uid,
                    Event.kind.like("opportunity%"),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].source_external_id == opp_id


# ---------------------------------------------------------- ENG-384 CareStack accounting_transaction


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_accounting_transaction_double_import_writes_raw_once(
    two_tenant_db: TwoTenantContext,
) -> None:
    """ENG-384: an unchanged accounting_transaction row writes exactly
    one raw_event across two consecutive pulls."""
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.carestack_accounting_transaction_service import (
        CareStackAccountingTransactionIngestService,
    )
    from packages.ingest.models import RawEvent

    service = CareStackAccountingTransactionIngestService(
        session, _StubCsAccountingClient([dict(_ACCT_RECORD)])
    )

    first = await service.import_recent_accounting_transactions(
        tenant_id, days=7
    )
    await session.flush()
    second = await service.import_recent_accounting_transactions(
        tenant_id, days=7
    )
    await session.flush()

    # Row has no patientId → skipped for emit but raw_event captured.
    assert first.skipped_count == 1
    assert first.unchanged_count == 0
    # Second run: guard catches the (id, lastUpdatedOn) match — no
    # raw_event write, no patient-link lookup.
    assert second.skipped_count == 0
    assert second.unchanged_count == 1

    composed_external_id = (
        f"{_ACCT_RECORD['id']}:{_ACCT_RECORD['lastUpdatedOn']}"
    )
    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "carestack.accounting_transaction.upsert",
                RawEvent.external_id == composed_external_id,
            )
        )
    ).scalar_one()
    assert raw_count == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_accounting_transaction_change_writes_second_raw_row(
    two_tenant_db: TwoTenantContext,
) -> None:
    """A moved ``lastUpdatedOn`` writes a second raw_event row (the
    composed external_id changes with the stamp)."""
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.carestack_accounting_transaction_service import (
        CareStackAccountingTransactionIngestService,
    )
    from packages.ingest.models import RawEvent

    stub = _StubCsAccountingClient([dict(_ACCT_RECORD)])
    service = CareStackAccountingTransactionIngestService(session, stub)

    await service.import_recent_accounting_transactions(tenant_id, days=7)
    await session.flush()

    moved = dict(_ACCT_RECORD)
    moved["lastUpdatedOn"] = "2026-06-09T09:00:00Z"
    stub.rows = [moved]

    result = await service.import_recent_accounting_transactions(
        tenant_id, days=7
    )
    await session.flush()

    # The new stamp produced a fresh composed external_id, so the guard
    # missed the previous row and the new one was captured.
    assert result.unchanged_count == 0
    assert result.skipped_count == 1

    # Scope the count to MY composed external_ids (id + ":" + stamp);
    # the conftest seeds an unrelated accounting_transaction raw_event
    # for tenant A that we must not include.
    transaction_id = str(_ACCT_RECORD["id"])
    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "carestack.accounting_transaction.upsert",
                RawEvent.external_id.like(f"{transaction_id}:%"),
            )
        )
    ).scalar_one()
    assert raw_count == 2


# ---------------------------------------------------------- ENG-384 CareStack invoice


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_invoice_double_import_writes_raw_once(
    two_tenant_db: TwoTenantContext,
) -> None:
    """ENG-384: an unchanged invoice row writes exactly one raw_event
    across two consecutive pulls."""
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.carestack_invoice_service import (
        CareStackInvoiceIngestService,
    )
    from packages.ingest.models import RawEvent

    service = CareStackInvoiceIngestService(
        session, _StubCsInvoiceClient([dict(_INVOICE_RECORD)])
    )

    first = await service.import_recent_invoices(tenant_id, days=7)
    await session.flush()
    second = await service.import_recent_invoices(tenant_id, days=7)
    await session.flush()

    assert first.skipped_count == 1
    assert first.unchanged_count == 0
    assert second.skipped_count == 0
    assert second.unchanged_count == 1

    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "carestack.invoice.upsert",
                RawEvent.external_id == str(_INVOICE_RECORD["invoiceId"]),
            )
        )
    ).scalar_one()
    assert raw_count == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_invoice_change_writes_second_raw_row(
    two_tenant_db: TwoTenantContext,
) -> None:
    """A moved ``lastUpdatedOn`` writes a second raw_event row for the
    same invoice id."""
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id

    from packages.ingest.carestack_invoice_service import (
        CareStackInvoiceIngestService,
    )
    from packages.ingest.models import RawEvent

    stub = _StubCsInvoiceClient([dict(_INVOICE_RECORD)])
    service = CareStackInvoiceIngestService(session, stub)

    await service.import_recent_invoices(tenant_id, days=7)
    await session.flush()

    moved = dict(_INVOICE_RECORD)
    moved["lastUpdatedOn"] = "2026-06-09T09:00:00Z"
    stub.rows = [moved]

    result = await service.import_recent_invoices(tenant_id, days=7)
    await session.flush()

    assert result.unchanged_count == 0
    assert result.skipped_count == 1

    raw_count = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == "carestack.invoice.upsert",
                RawEvent.external_id == str(_INVOICE_RECORD["invoiceId"]),
            )
        )
    ).scalar_one()
    assert raw_count == 2
