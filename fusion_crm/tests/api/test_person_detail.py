"""HTTP tests for the person detail operational card contract."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_identity_service,
    get_ingest_service,
    get_ops_service,
    get_phi_service,
    get_principal_with_tenant,
)
from apps.api.routers import persons as persons_router
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.schemas import (
    CarestackOriginRowOut,
    PersonPaymentFinancialSummaryOut,
)
from packages.ops.models import LeadStatus

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LEAD_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="person-detail@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def test_person_detail_returns_safe_operational_lead_metadata() -> None:
    identity = MagicMock()
    identity.get_person = AsyncMock(
        return_value=SimpleNamespace(
            id=_PERSON_UID,
            display_name="Jane Lead",
            given_name="Jane",
            family_name="Lead",
            updated_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            identifiers=[
                SimpleNamespace(kind="email", value="jane@example.test"),
                SimpleNamespace(kind="phone", value="+15551234567"),
            ],
        )
    )
    identity.source_providers_for = AsyncMock(
        return_value={_PERSON_UID: ["salesforce", "carestack"]}
    )
    identity.source_links_for_persons = AsyncMock(return_value={_PERSON_UID: []})

    ops = MagicMock()
    ops.has_lead_for = AsyncMock(return_value={_PERSON_UID})
    ops.get_lead_for_person = AsyncMock(
        return_value=SimpleNamespace(
            id=_LEAD_ID,
            person_uid=_PERSON_UID,
            status=LeadStatus.QUALIFIED,
            source="Website",
            created_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 25, 12, 5, tzinfo=UTC),
            extra={
                "lead_status": "Working - Contacted",
                "sf_created_at": "2026-05-25T12:00:00+00:00",
                "company": "Fusion demo",
                "campaign_name": "Implant May",
                "owner_name": "Taylor Owner",
                "tc_name": "Jamie TC",
                "raw_sensitive_field": "must not render",
            },
        )
    )

    phi = MagicMock()
    phi.person_uids_with_consultation = AsyncMock(return_value=set())

    ingest = MagicMock()
    ingest.person_payment_financial_summary = AsyncMock(
        return_value=PersonPaymentFinancialSummaryOut()
    )
    ingest.person_carestack_origin_context = AsyncMock(return_value=[])
    ingest.person_household_members = AsyncMock(return_value=[])

    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_identity_service] = lambda: identity
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_phi_service] = lambda: phi
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    app.dependency_overrides[get_principal_with_tenant] = _principal

    res = TestClient(app).get(f"/persons/{_PERSON_UID}")

    assert res.status_code == 200
    body = res.json()
    assert body["lead"]["salesforce_status"] == "Working - Contacted"
    assert body["lead"]["salesforce_created_at"].startswith("2026-05-25T12:00:00")
    assert body["lead"]["company"] == "Fusion demo"
    assert body["lead"]["campaign"] == "Implant May"
    assert body["lead"]["owner"] == "Taylor Owner"
    assert body["lead"]["treatment_coordinator"] == "Jamie TC"
    assert "raw_sensitive_field" not in res.text
    assert "must not render" not in res.text
    # ENG-306: detail must always carry a financial_summary block (zeroed +
    # snapshot_received_at=None for persons with no captured snapshot).
    assert body["financial_summary"] is not None
    assert body["financial_summary"]["snapshot_received_at"] is None
    assert body["financial_summary"]["carestack_patient_ids"] == []
    assert body["financial_summary"]["patient_count"] == 0


def test_person_detail_passes_carestack_patient_ids_to_financial_summary() -> None:
    """When the person has CareStack patient source links, the detail
    route must hand them to the ingest service so the four-number block
    is computed against the right ids (ENG-306).
    """
    cs_link = SimpleNamespace(
        id=uuid.uuid4(),
        person_uid=_PERSON_UID,
        source_system="carestack",
        source_instance="carestack-main",
        source_kind="patient",
        source_id="PT-9981",
        first_seen_at=datetime(2026, 4, 21, 14, 2, tzinfo=UTC),
        last_seen_at=datetime(2026, 5, 4, 18, 32, tzinfo=UTC),
    )
    # Non-CareStack link MUST be filtered out before the call.
    sf_link = SimpleNamespace(
        id=uuid.uuid4(),
        person_uid=_PERSON_UID,
        source_system="salesforce",
        source_instance="salesforce-main",
        source_kind="lead",
        source_id="00Q5j000001abcd",
        first_seen_at=datetime(2026, 4, 21, 14, 2, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 23, 9, 18, tzinfo=UTC),
    )

    identity = MagicMock()
    identity.get_person = AsyncMock(
        return_value=SimpleNamespace(
            id=_PERSON_UID,
            display_name="Jane Lead",
            given_name="Jane",
            family_name="Lead",
            updated_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            identifiers=[],
        )
    )
    identity.source_providers_for = AsyncMock(
        return_value={_PERSON_UID: ["carestack", "salesforce"]}
    )
    identity.source_links_for_persons = AsyncMock(
        return_value={_PERSON_UID: [cs_link, sf_link]}
    )

    ops = MagicMock()
    ops.has_lead_for = AsyncMock(return_value=set())
    ops.get_lead_for_person = AsyncMock(return_value=None)

    phi = MagicMock()
    phi.person_uids_with_consultation = AsyncMock(return_value=set())

    snapshot_at = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    ingest = MagicMock()
    ingest.person_payment_financial_summary = AsyncMock(
        return_value=PersonPaymentFinancialSummaryOut(
            billed=2500.0,
            adjustments=-150.0,
            paid=800.0,
            balance=1200.0,
            snapshot_received_at=snapshot_at,
            carestack_patient_ids=["PT-9981"],
            patient_count=1,
        )
    )
    ingest.person_carestack_origin_context = AsyncMock(return_value=[])
    ingest.person_household_members = AsyncMock(return_value=[])

    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_identity_service] = lambda: identity
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_phi_service] = lambda: phi
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    app.dependency_overrides[get_principal_with_tenant] = _principal

    res = TestClient(app).get(f"/persons/{_PERSON_UID}")

    assert res.status_code == 200
    body = res.json()
    fs = body["financial_summary"]
    assert fs is not None
    assert fs["billed"] == 2500.0
    assert fs["adjustments"] == -150.0
    assert fs["paid"] == 800.0
    assert fs["balance"] == 1200.0
    assert fs["snapshot_received_at"].startswith("2026-05-25T12:00:00")
    assert fs["carestack_patient_ids"] == ["PT-9981"]
    assert fs["patient_count"] == 1

    # The route must hand the ingest service ONLY the CareStack patient ids
    # — not the Salesforce lead id — so the SQL is scoped correctly.
    ingest.person_payment_financial_summary.assert_awaited_once_with(
        _TENANT_ID, ["PT-9981"]
    )


def test_person_detail_returns_carestack_origin_for_multi_link_person() -> None:
    """ENG-308: when a person has multiple CareStack patient links, the
    detail route must return one ``carestack_origin`` row per pid, with
    earliest activity, location/provider names, and city/state surfaced.
    """
    pids = [("1460847", "El Dorado Hills"), ("1461274", "Roseville"), ("2171827", None)]
    cs_links = [
        SimpleNamespace(
            id=uuid.uuid4(),
            person_uid=_PERSON_UID,
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id=pid,
            first_seen_at=datetime(2026, 4, 21, 14, 2, tzinfo=UTC),
            last_seen_at=datetime(2026, 5, 4, 18, 32, tzinfo=UTC),
        )
        for pid, _ in pids
    ]

    identity = MagicMock()
    identity.get_person = AsyncMock(
        return_value=SimpleNamespace(
            id=_PERSON_UID,
            display_name="Multi Link",
            given_name="Multi",
            family_name="Link",
            updated_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            identifiers=[],
        )
    )
    identity.source_providers_for = AsyncMock(
        return_value={_PERSON_UID: ["carestack"]}
    )
    identity.source_links_for_persons = AsyncMock(
        return_value={_PERSON_UID: cs_links}
    )

    ops = MagicMock()
    ops.has_lead_for = AsyncMock(return_value=set())
    ops.get_lead_for_person = AsyncMock(return_value=None)

    phi = MagicMock()
    phi.person_uids_with_consultation = AsyncMock(return_value=set())

    ingest = MagicMock()
    ingest.person_payment_financial_summary = AsyncMock(
        return_value=PersonPaymentFinancialSummaryOut()
    )
    origin_rows = [
        CarestackOriginRowOut(
            patient_id="1460847",
            earliest_activity_at=datetime(2025, 8, 1, 9, 0, tzinfo=UTC),
            latest_activity_at=datetime(2026, 4, 1, 15, 30, tzinfo=UTC),
            default_location_id=10001,
            default_location_name="El Dorado Hills",
            default_provider_id=17,
            default_provider_name="Dr Aram Torosyan",
            city="El Dorado Hills",
            state="CA",
        ),
        CarestackOriginRowOut(
            patient_id="1461274",
            earliest_activity_at=datetime(2026, 3, 12, 23, 47, tzinfo=UTC),
            latest_activity_at=datetime(2026, 5, 4, 18, 32, tzinfo=UTC),
            default_location_id=10002,
            default_location_name="Roseville",
            default_provider_id=None,
            default_provider_name=None,
            city="Roseville",
            state="CA",
        ),
        CarestackOriginRowOut(
            patient_id="2171827",
            earliest_activity_at=None,
            latest_activity_at=None,
            default_location_id=None,
            default_location_name=None,
            default_provider_id=None,
            default_provider_name=None,
            city=None,
            state=None,
        ),
    ]
    ingest.person_carestack_origin_context = AsyncMock(return_value=origin_rows)
    ingest.person_household_members = AsyncMock(return_value=[])

    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_identity_service] = lambda: identity
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_phi_service] = lambda: phi
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    app.dependency_overrides[get_principal_with_tenant] = _principal

    res = TestClient(app).get(f"/persons/{_PERSON_UID}")

    assert res.status_code == 200
    body = res.json()
    assert "carestack_origin" in body
    assert len(body["carestack_origin"]) == 3
    assert body["carestack_origin"][0]["patient_id"] == "1460847"
    assert body["carestack_origin"][0]["default_provider_name"] == "Dr Aram Torosyan"
    assert body["carestack_origin"][0]["city"] == "El Dorado Hills"
    assert body["carestack_origin"][1]["default_provider_name"] is None
    assert body["carestack_origin"][2]["earliest_activity_at"] is None

    # The origin call must receive ONLY the CareStack patient ids, in the
    # same form (deduped, sorted) we already pass to financial_summary.
    ingest.person_carestack_origin_context.assert_awaited_once_with(
        _TENANT_ID, ["1460847", "1461274", "2171827"]
    )


def test_person_detail_returns_empty_carestack_origin_when_no_cs_links() -> None:
    """A person with zero CareStack links must surface an empty
    ``carestack_origin`` array (not null) so the frontend can iterate
    over it unconditionally."""
    identity = MagicMock()
    identity.get_person = AsyncMock(
        return_value=SimpleNamespace(
            id=_PERSON_UID,
            display_name="SF Only",
            given_name="SF",
            family_name="Only",
            updated_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            identifiers=[],
        )
    )
    identity.source_providers_for = AsyncMock(
        return_value={_PERSON_UID: ["salesforce"]}
    )
    identity.source_links_for_persons = AsyncMock(return_value={_PERSON_UID: []})

    ops = MagicMock()
    ops.has_lead_for = AsyncMock(return_value=set())
    ops.get_lead_for_person = AsyncMock(return_value=None)

    phi = MagicMock()
    phi.person_uids_with_consultation = AsyncMock(return_value=set())

    ingest = MagicMock()
    ingest.person_payment_financial_summary = AsyncMock(
        return_value=PersonPaymentFinancialSummaryOut()
    )
    ingest.person_carestack_origin_context = AsyncMock(return_value=[])
    ingest.person_household_members = AsyncMock(return_value=[])

    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_identity_service] = lambda: identity
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_phi_service] = lambda: phi
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    app.dependency_overrides[get_principal_with_tenant] = _principal

    res = TestClient(app).get(f"/persons/{_PERSON_UID}")

    assert res.status_code == 200
    body = res.json()
    assert body["carestack_origin"] == []
