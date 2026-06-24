"""HTTP tests for the PM Payments dashboard read model (ENG-271).

The PM Payments page surfaces ``interaction.event`` rows of the three
payment kinds (``payment_recorded``, ``payment_refunded``,
``payment_reversed``) joined to person identity, lead/consult stage, and
the canonical location label. These tests cover the safe-fields contract,
each filter, and the no-PHI assertion (the list response must not echo
clinical free text or any patient identifier beyond the resolved display
name + person_uid).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_db,
    get_identity_service,
    get_ingest_service,
    get_interaction_service,
    get_ops_service,
    get_principal_with_tenant,
)
from apps.api.routers import dashboard as dashboard_router
from packages.core.security import Principal, Role
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="pm-payments@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _fake_db() -> MagicMock:
    return MagicMock()


def _build_app(
    ops: MagicMock,
    interaction: MagicMock,
    identity: MagicMock,
    ingest: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(dashboard_router.router)
    if ingest is None:
        ingest = MagicMock()
        ingest.get_carestack_invoice_refs = AsyncMock(return_value={})
    # ENG-306: every PM-payments test ends up exercising the per-row
    # balance pipeline. Default both surfaces to "no data" so callers only
    # need to override when they want to assert the pill behaviour.
    if not hasattr(ingest, "latest_balance_by_patient") or not isinstance(
        ingest.latest_balance_by_patient, AsyncMock
    ):
        ingest.latest_balance_by_patient = AsyncMock(return_value={})
    # ENG-547: every PM-payments test now also exercises the operation-code +
    # doctor enrichment. Default to "no enrichment" so callers only override
    # when they want to assert the Operation/Doctor columns.
    if not hasattr(ingest, "get_payment_procedure_doctor_refs") or not isinstance(
        ingest.get_payment_procedure_doctor_refs, AsyncMock
    ):
        ingest.get_payment_procedure_doctor_refs = AsyncMock(return_value={})
    if not hasattr(identity, "source_links_for_persons") or not isinstance(
        identity.source_links_for_persons, AsyncMock
    ):
        identity.source_links_for_persons = AsyncMock(return_value={})
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_interaction_service] = lambda: interaction
    app.dependency_overrides[get_identity_service] = lambda: identity
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def _make_event(
    *,
    kind: str = "payment_recorded",
    source_provider: str = "carestack",
    source_external_id: str | None = "CS-TX-1",
    person_uid: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
    payload: dict[str, object] | None = None,
    source_event_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id or uuid.uuid4(),
        person_uid=person_uid or uuid.uuid4(),
        kind=kind,
        source_provider=source_provider,
        source_external_id=source_external_id,
        source_event_id=source_event_id or uuid.uuid4(),
        occurred_at=occurred_at or datetime(2026, 5, 22, 15, 30, tzinfo=UTC),
        # ``payload if payload is not None`` (not ``payload or ...``) so a
        # caller can pass ``{}`` to exercise the empty-payload branch.
        payload=payload
        if payload is not None
        else {
            "amount": 1850.0,
            "transaction_type": "PATIENTCREDIT",
        },
    )


def test_pm_payments_returns_safe_row_shape() -> None:
    person_uid = uuid.uuid4()
    location_uid = uuid.uuid4()
    event = _make_event(
        person_uid=person_uid,
        payload={
            "amount": 1850.0,
            "transaction_type": "PATIENTCREDIT",
            "location_id": str(location_uid),
        },
    )

    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[event])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=1)

    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="Jane Payer",
                given_name="Jane",
                family_name="Payer",
                identifiers=[
                    SimpleNamespace(kind="email", value="jane@example.test"),
                ],
            )
        ]
    )

    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(
        return_value={
            person_uid: SimpleNamespace(
                status="qualified",
                source="Facebook",
                extra={
                    "utm_source": "facebook",
                    "owner_id": "005XYZ",
                    "owner_name": "Jane Owner",
                },
            )
        }
    )
    ops.latest_consultations_for_persons = AsyncMock(
        return_value={person_uid: SimpleNamespace(status="completed")}
    )

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock(
            return_value=SimpleNamespace(
                id=location_uid, name="Fusion Roseville", city="Roseville"
            )
        )
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert body["has_next"] is False
    assert body["has_previous"] is False
    assert len(body["items"]) == 1
    row = body["items"][0]
    # SAFE field set, in spec order.
    assert set(row.keys()) == {
        "id",
        "person_uid",
        "display_name",
        "lead_status",
        "consultation_status",
        "lead_source_label",
        "lead_owner",
        "amount",
        "kind",
        "transaction_type",
        "occurred_at",
        "source_provider",
        "source_external_id",
        "location_id",
        "location_name",
        "raw_event_id",
        "invoice_id",
        "invoice_number",
        "invoice_date",
        "balance",
        "operation_code",
        "operation_description",
        "doctor_name",
        "doctor_provider_id",
    }
    assert row["person_uid"] == str(person_uid)
    assert row["display_name"] == "Jane Payer"
    assert row["lead_status"] == "qualified"
    assert row["consultation_status"] == "completed"
    # ENG-408: explorer source label (lowercased, last-touch chain) and the
    # SF owner (Owner.Name mirror preferred over the raw OwnerId).
    assert row["lead_source_label"] == "facebook"
    assert row["lead_owner"] == "Jane Owner"
    assert row["amount"] == 1850.0
    assert row["kind"] == "payment_recorded"
    assert row["transaction_type"] == "PATIENTCREDIT"
    assert row["source_provider"] == "carestack"
    assert row["location_id"] == str(location_uid)
    assert row["location_name"] == "Fusion Roseville · Roseville"
    assert row["raw_event_id"] == str(event.source_event_id)

    # No-PHI assertion: the rendered JSON must not include identifiers,
    # contact fields, or provider-payload keys.
    rendered = res.text
    assert "jane@example.test" not in rendered
    assert "patientId" not in rendered
    assert "PatientId" not in rendered
    assert "notes" not in rendered
    assert "given_name" not in row
    assert "family_name" not in row
    assert "email" not in row
    assert "phone" not in row


def test_pm_payments_forwards_window_location_provider_q_to_service() -> None:
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=0)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(return_value=[])
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    location_id = uuid.uuid4()
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get(
            "/dashboard/pm/payments"
            "?from=2026-05-01T00:00:00Z"
            "&to=2026-06-01T00:00:00Z"
            f"&location_id={location_id}"
            "&source_provider=carestack"
            "&q=tx-9001"
            "&limit=25"
        )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["source_provider"] == "carestack"
    assert body["filters"]["location_id"] == str(location_id)
    assert body["filters"]["q"] == "tx-9001"
    interaction.list_payment_events_for_dashboard.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        source_provider="carestack",
        location_id=location_id,
        query="tx-9001",
        include_applied=False,
        person_uids=None,
        limit=25,
        offset=0,
    )
    # The count companion gets the same filters (no limit/offset) to drive
    # the honest total / pagination flags.
    interaction.count_payment_events_for_dashboard.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        source_provider="carestack",
        location_id=location_id,
        query="tx-9001",
        include_applied=False,
        person_uids=None,
    )


def test_pm_payments_forwards_include_applied_and_offset() -> None:
    """`include_applied` + `offset` reach the list call; total drives has_next."""
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(
        return_value=[_make_event()]
    )
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=250)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(return_value=[])
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get(
            "/dashboard/pm/payments?include_applied=true&limit=100&offset=100"
        )

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 250
    assert body["offset"] == 100
    # offset(100) + 1 fetched row < 250 → more pages ahead; offset>0 → behind.
    assert body["has_next"] is True
    assert body["has_previous"] is True
    list_kwargs = interaction.list_payment_events_for_dashboard.await_args.kwargs
    assert list_kwargs["include_applied"] is True
    assert list_kwargs["offset"] == 100
    count_kwargs = interaction.count_payment_events_for_dashboard.await_args.kwargs
    assert count_kwargs["include_applied"] is True
    assert "offset" not in count_kwargs


def test_pm_payments_tenant_scope_passed_through() -> None:
    """The route must hand the principal's tenant id to every service call."""
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=0)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(return_value=[])
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    # Every service call's first positional arg must be the tenant id.
    args, kwargs = interaction.list_payment_events_for_dashboard.await_args
    assert args[0] == _TENANT_ID
    assert kwargs["occurred_from"] is None
    assert kwargs["occurred_to"] is None


def test_pm_payments_resolves_invoice_number_and_date() -> None:
    person_uid = uuid.uuid4()
    event = _make_event(
        person_uid=person_uid,
        payload={
            "amount": 300.0,
            "transaction_type": "PATIENTCREDIT",
            "invoice_id": "2424603",
        },
    )
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[event])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=1)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="Inv Payer",
                given_name="Inv",
                family_name="Payer",
                identifiers=[],
            )
        ]
    )
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    ingest = MagicMock()
    ingest.get_carestack_invoice_refs = AsyncMock(
        return_value={
            "2424603": {"invoice_number": "10498", "invoice_date": "2026-05-28"}
        }
    )

    app = _build_app(ops, interaction, identity, ingest)
    client = TestClient(app)
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    row = res.json()["items"][0]
    assert row["invoice_id"] == "2424603"
    assert row["invoice_number"] == "10498"
    assert row["invoice_date"] == "2026-05-28"
    # Only the invoice ids actually present on the page are resolved.
    ingest.get_carestack_invoice_refs.assert_awaited_once_with(
        _TENANT_ID, ["2424603"]
    )


def test_pm_payments_resolves_operation_code_and_doctor() -> None:
    """ENG-547: the row surfaces the resolved operation code + doctor.

    Enrichment is keyed by the payment's ``source_event_id`` (the raw_event PK),
    and the route hands exactly the page's raw ids to the ingest resolver.
    """
    person_uid = uuid.uuid4()
    raw_id = uuid.uuid4()
    event = _make_event(person_uid=person_uid, source_event_id=raw_id)
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[event])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=1)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="Op Payer",
                given_name="Op",
                family_name="Payer",
                identifiers=[],
            )
        ]
    )
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    ingest = MagicMock()
    ingest.get_payment_procedure_doctor_refs = AsyncMock(
        return_value={
            raw_id: {
                "operation_code": "D6010",
                "operation_description": "Surgical placement of implant body",
                "doctor_name": "Dr Jane Smith",
                "doctor_provider_id": 3,
            }
        }
    )

    app = _build_app(ops, interaction, identity, ingest)
    client = TestClient(app)
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    row = res.json()["items"][0]
    assert row["operation_code"] == "D6010"
    assert row["operation_description"] == "Surgical placement of implant body"
    assert row["doctor_name"] == "Dr Jane Smith"
    assert row["doctor_provider_id"] == 3
    # The route resolves exactly the page's raw_event ids.
    ingest.get_payment_procedure_doctor_refs.assert_awaited_once_with(
        _TENANT_ID, [raw_id]
    )


def test_pm_payments_summary_forwards_window_and_returns_totals() -> None:
    interaction = MagicMock()
    interaction.summarize_payment_events_for_dashboard = AsyncMock(
        return_value=SimpleNamespace(
            collected_total=205639.05, payment_count=565, patient_count=312
        )
    )
    identity = MagicMock()
    ops = MagicMock()

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    location_id = uuid.uuid4()
    res = client.get(
        "/dashboard/pm/payments/summary"
        "?from=2026-05-01T00:00:00Z"
        "&to=2026-06-01T00:00:00Z"
        f"&location_id={location_id}"
        "&source_provider=carestack"
        "&q=tx"
    )

    assert res.status_code == 200
    body = res.json()
    assert body["collected_total"] == 205639.05
    assert body["payment_count"] == 565
    assert body["patient_count"] == 312
    assert body["filters"]["location_id"] == str(location_id)
    # Window-aggregate: no limit/offset/include_applied forwarded.
    interaction.summarize_payment_events_for_dashboard.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        source_provider="carestack",
        location_id=location_id,
        query="tx",
        person_uids=None,
    )


def test_pm_payments_lead_source_node_scopes_rows_and_summary() -> None:
    """ENG-408: the lead-source node params resolve to person_uids on the ops
    side and scope both the row list and the window aggregate."""
    node_persons = [uuid.uuid4(), uuid.uuid4()]

    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=0)
    interaction.summarize_payment_events_for_dashboard = AsyncMock(
        return_value=SimpleNamespace(
            collected_total=0.0, payment_count=0, patient_count=0
        )
    )
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(return_value=[])
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    ops.person_uids_for_lead_source_node = AsyncMock(return_value=node_persons)

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get(
            "/dashboard/pm/payments"
            "?lead_channel=facebook&lead_source=facebook&lead_medium=cpc"
        )
    assert res.status_code == 200
    assert res.json()["filters"]["lead_channel"] == "facebook"
    assert res.json()["filters"]["lead_source"] == "facebook"
    assert res.json()["filters"]["lead_medium"] == "cpc"
    ops.person_uids_for_lead_source_node.assert_awaited_once_with(
        _TENANT_ID,
        channel="facebook",
        source="facebook",
        medium="cpc",
        campaign=None,
    )
    list_kwargs = interaction.list_payment_events_for_dashboard.await_args.kwargs
    assert list_kwargs["person_uids"] == node_persons
    count_kwargs = interaction.count_payment_events_for_dashboard.await_args.kwargs
    assert count_kwargs["person_uids"] == node_persons

    # Summary honours the same node scope ("cash from this resource").
    res = client.get(
        "/dashboard/pm/payments/summary?lead_channel=facebook&lead_source=facebook"
    )
    assert res.status_code == 200
    summary_kwargs = (
        interaction.summarize_payment_events_for_dashboard.await_args.kwargs
    )
    assert summary_kwargs["person_uids"] == node_persons

    # An empty node (no persons) is a real filter, not "no filter": the
    # interaction layer must receive [] and match nothing.
    ops.person_uids_for_lead_source_node = AsyncMock(return_value=[])
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments?lead_channel=ghost")
    assert res.status_code == 200
    assert res.json()["total"] == 0
    list_kwargs = interaction.list_payment_events_for_dashboard.await_args.kwargs
    assert list_kwargs["person_uids"] == []


def test_pm_payments_resolves_per_row_balance_pill() -> None:
    """ENG-306: each row gains a ``balance`` from the latest CS payment-summary
    snapshot for the row's CareStack patient ids — null when no snapshot."""
    person_with_balance = uuid.uuid4()
    person_unsnapshotted = uuid.uuid4()
    event_a = _make_event(
        person_uid=person_with_balance,
        payload={"amount": 100.0, "transaction_type": "PATIENTCREDIT"},
    )
    event_b = _make_event(
        person_uid=person_unsnapshotted,
        payload={"amount": 200.0, "transaction_type": "PATIENTCREDIT"},
    )
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(
        return_value=[event_a, event_b]
    )
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=2)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_with_balance,
                display_name="Alice",
                given_name="A",
                family_name="",
                identifiers=[],
            ),
            SimpleNamespace(
                id=person_unsnapshotted,
                display_name="Bob",
                given_name="B",
                family_name="",
                identifiers=[],
            ),
        ]
    )
    identity.source_links_for_persons = AsyncMock(
        return_value={
            person_with_balance: [
                SimpleNamespace(
                    source_system="carestack",
                    source_kind="patient",
                    source_id="PT-9981",
                ),
                # Non-CareStack noise — must be ignored before the lookup.
                SimpleNamespace(
                    source_system="salesforce",
                    source_kind="lead",
                    source_id="00Q5j000001abcd",
                ),
            ],
            person_unsnapshotted: [
                SimpleNamespace(
                    source_system="carestack",
                    source_kind="patient",
                    source_id="PT-NONE",
                ),
            ],
        }
    )

    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    ingest = MagicMock()
    ingest.get_carestack_invoice_refs = AsyncMock(return_value={})
    ingest.latest_balance_by_patient = AsyncMock(return_value={"PT-9981": 1250.0})

    app = _build_app(ops, interaction, identity, ingest)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    rows = {row["person_uid"]: row for row in res.json()["items"]}
    assert rows[str(person_with_balance)]["balance"] == 1250.0
    # No snapshot → ``null``, not zero — the UI renders ``"—"``.
    assert rows[str(person_unsnapshotted)]["balance"] is None
    # Single ingest round-trip for the whole page; ONLY CareStack patient
    # ids reach it (the Salesforce lead id is filtered out at the route).
    ingest.latest_balance_by_patient.assert_awaited_once_with(
        _TENANT_ID, ["PT-9981", "PT-NONE"]
    )


def test_pm_payments_handles_empty_payload_gracefully() -> None:
    """Payloads missing amount/location should produce nullable row fields."""
    person_uid = uuid.uuid4()
    event = _make_event(person_uid=person_uid, payload={})
    interaction = MagicMock()
    interaction.list_payment_events_for_dashboard = AsyncMock(return_value=[event])
    interaction.count_payment_events_for_dashboard = AsyncMock(return_value=1)
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="No Stage Person",
                given_name=None,
                family_name=None,
                identifiers=[],
            )
        ]
    )
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments")

    assert res.status_code == 200
    row = res.json()["items"][0]
    assert row["amount"] is None
    assert row["transaction_type"] is None
    assert row["location_id"] is None
    assert row["location_name"] is None
    assert row["lead_status"] is None
    assert row["consultation_status"] is None


def test_pm_payment_groups_returns_grouped_rows_with_legs() -> None:
    """ENG-410: /pm/payments/groups collapses same-day legs with person-level
    enrichment on the group head and full row DTOs embedded as legs."""
    from datetime import date

    person_uid = uuid.uuid4()
    leg_new = _make_event(
        person_uid=person_uid,
        source_external_id="CS-TX-2",
        occurred_at=datetime(2026, 6, 11, 17, 28, tzinfo=UTC),
        payload={"amount": 344.0, "transaction_type": "PATIENTCREDIT"},
    )
    leg_old = _make_event(
        person_uid=person_uid,
        source_external_id="CS-TX-1",
        occurred_at=datetime(2026, 6, 11, 17, 27, tzinfo=UTC),
        payload={"amount": 450.0, "transaction_type": "PATIENTCREDIT"},
    )

    interaction = MagicMock()
    interaction.list_payment_event_groups_for_dashboard = AsyncMock(
        return_value=[
            {
                "person_uid": person_uid,
                "kind": "payment_recorded",
                "local_day": date(2026, 6, 11),
                "total_amount": 794.0,
                "leg_count": 2,
                "last_occurred_at": leg_new.occurred_at,
                "legs": [leg_new, leg_old],
            }
        ]
    )
    interaction.count_payment_event_groups_for_dashboard = AsyncMock(return_value=1)

    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[SimpleNamespace(id=person_uid, display_name="Chris Bustos")]
    )
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(
        return_value={
            person_uid: SimpleNamespace(
                status="qualified",
                source=None,
                extra={"utm_source": "google", "owner_name": "Yelena Myalik"},
            )
        }
    )
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    app = _build_app(ops, interaction, identity)
    client = TestClient(app)
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments/groups?limit=50")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    group = body["items"][0]
    assert group["person_uid"] == str(person_uid)
    assert group["display_name"] == "Chris Bustos"
    assert group["lead_source_label"] == "google"
    assert group["lead_owner"] == "Yelena Myalik"
    assert group["kind"] == "payment_recorded"
    assert group["day"] == "2026-06-11"
    assert group["amount"] == 794.0
    assert group["leg_count"] == 2
    # Legs are full flat-row DTOs, newest-first.
    assert [leg["source_external_id"] for leg in group["legs"]] == [
        "CS-TX-2",
        "CS-TX-1",
    ]
    assert group["legs"][0]["amount"] == 344.0
    assert group["legs"][0]["lead_owner"] == "Yelena Myalik"

    # The grouped service got the same filter surface (incl. paging).
    kwargs = interaction.list_payment_event_groups_for_dashboard.await_args.kwargs
    assert kwargs["limit"] == 50
    assert kwargs["person_uids"] is None


def test_pm_payment_groups_legs_carry_operation_and_doctor() -> None:
    """ENG-547: each leg in a group carries its OWN operation code + doctor.

    A group collapses same-day legs that may span different procedures and
    different doctors, so the enrichment is per-leg (keyed by each leg's
    ``source_event_id``). The frontend rolls these up into the group head's
    Operation/Doctor columns ("—" / single value / "N codes" / "N doctors");
    that rollup is only possible because the backend resolves and surfaces the
    fields on every embedded leg DTO — which is what this asserts.
    """
    from datetime import date

    person_uid = uuid.uuid4()
    raw_new = uuid.uuid4()
    raw_old = uuid.uuid4()
    leg_new = _make_event(
        person_uid=person_uid,
        source_external_id="CS-TX-2",
        source_event_id=raw_new,
        occurred_at=datetime(2026, 6, 11, 17, 28, tzinfo=UTC),
        payload={"amount": 344.0, "transaction_type": "PATIENTCREDIT"},
    )
    leg_old = _make_event(
        person_uid=person_uid,
        source_external_id="CS-TX-1",
        source_event_id=raw_old,
        occurred_at=datetime(2026, 6, 11, 17, 27, tzinfo=UTC),
        payload={"amount": 450.0, "transaction_type": "PATIENTCREDIT"},
    )

    interaction = MagicMock()
    interaction.list_payment_event_groups_for_dashboard = AsyncMock(
        return_value=[
            {
                "person_uid": person_uid,
                "kind": "payment_recorded",
                "local_day": date(2026, 6, 11),
                "total_amount": 794.0,
                "leg_count": 2,
                "last_occurred_at": leg_new.occurred_at,
                "legs": [leg_new, leg_old],
            }
        ]
    )
    interaction.count_payment_event_groups_for_dashboard = AsyncMock(return_value=1)

    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[SimpleNamespace(id=person_uid, display_name="Chris Bustos")]
    )
    ops = MagicMock()
    ops.latest_leads_for_persons = AsyncMock(return_value={})
    ops.latest_consultations_for_persons = AsyncMock(return_value={})

    # Distinct enrichment per leg — different procedures AND different doctors,
    # the case the group head must roll up.
    ingest = MagicMock()
    ingest.get_payment_procedure_doctor_refs = AsyncMock(
        return_value={
            raw_new: {
                "operation_code": "D6010",
                "operation_description": "Surgical placement of implant body",
                "doctor_name": "Dr Jane Smith",
                "doctor_provider_id": 3,
            },
            raw_old: {
                "operation_code": "D0120",
                "operation_description": "Periodic oral evaluation",
                "doctor_name": "Dr John Doe",
                "doctor_provider_id": 7,
            },
        }
    )

    app = _build_app(ops, interaction, identity, ingest)
    client = TestClient(app)
    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.get_location = AsyncMock()
        res = client.get("/dashboard/pm/payments/groups?limit=50")

    assert res.status_code == 200
    legs = res.json()["items"][0]["legs"]
    by_external = {leg["source_external_id"]: leg for leg in legs}
    assert by_external["CS-TX-2"]["operation_code"] == "D6010"
    assert by_external["CS-TX-2"]["doctor_name"] == "Dr Jane Smith"
    assert by_external["CS-TX-2"]["doctor_provider_id"] == 3
    assert by_external["CS-TX-1"]["operation_code"] == "D0120"
    assert by_external["CS-TX-1"]["doctor_name"] == "Dr John Doe"
    assert by_external["CS-TX-1"]["doctor_provider_id"] == 7

    # The route resolved exactly the group's leg raw ids (one batched call).
    awaited_ids = ingest.get_payment_procedure_doctor_refs.await_args.args[1]
    assert set(awaited_ids) == {raw_new, raw_old}
