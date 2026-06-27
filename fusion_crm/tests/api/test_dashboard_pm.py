"""HTTP tests for the PM dashboard read model."""

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
    get_integration_service,
    get_interaction_service,
    get_ops_service,
    get_principal_with_tenant,
)
from apps.api.routers import dashboard as dashboard_router
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.interaction.schemas import OperationalTimelineEntry

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="pm-dashboard@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _fake_db() -> MagicMock:
    return MagicMock()


def _build_app(
    ops: MagicMock,
    interaction: MagicMock,
    integrations: MagicMock,
    ingest: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(dashboard_router.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_ops_service] = lambda: ops
    app.dependency_overrides[get_interaction_service] = lambda: interaction
    app.dependency_overrides[get_integration_service] = lambda: integrations
    ingest_dep = ingest if ingest is not None else _default_ingest()
    app.dependency_overrides[get_ingest_service] = lambda: ingest_dep
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def _default_ingest() -> MagicMock:
    ingest = MagicMock()
    ingest.latest_payment_summary_balances = AsyncMock(
        return_value=SimpleNamespace(
            balance_due_patient=0.0,
            balance_due_insurance=0.0,
            outstanding_total=0.0,
            patient_count=0,
            ar_risk_count=0,
            ar_risk_threshold=500.0,
        )
    )
    return ingest


def _bucket(key: str, count: int, label: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(key=key, label=label or key.replace("_", " ").title(), count=count)


def _wire_semantic_ops_defaults(ops: MagicMock) -> None:
    ops.get_lead_source_profile = AsyncMock(
        return_value=SimpleNamespace(total_leads=0, sources=[])
    )
    ops.get_conversion_funnel_analytics = AsyncMock(
        return_value=SimpleNamespace(
            lead_status=[],
            consultation_status=[],
            pipeline_total=0,
            consultations_total=0,
            completed_consultations=0,
        )
    )
    ops.get_paid_leads_analytics = AsyncMock(
        return_value=SimpleNamespace(
            total_paid_leads=0,
            sources=[],
            classification_terms=[],
        )
    )
    ops.get_consultation_followup_analytics = AsyncMock(
        return_value=SimpleNamespace(
            consultation_status=[],
            open_followups=0,
            overdue_followups=0,
        )
    )


def test_pm_dashboard_returns_contract_with_filters_and_safe_activity() -> None:
    ops = MagicMock()
    lead_counts = {
        "new": 3,
        "qualified": 2,
        "contacted": 1,
        "booked": 1,
        "lost": 1,
    }
    consultation_counts = {
        "scheduled": 4,
        "completed": 2,
        "cancelled": 1,
        "rescheduled": 0,
        "no_show": 1,
    }
    ops.get_lead_source_profile = AsyncMock(
        return_value=SimpleNamespace(
            total_leads=6,
            sources=[_bucket("Website", 4), _bucket("Phone", 2)],
        )
    )
    ops.get_conversion_funnel_analytics = AsyncMock(
        return_value=SimpleNamespace(
            lead_status=[_bucket(key, count) for key, count in lead_counts.items()],
            consultation_status=[
                _bucket(key, count) for key, count in consultation_counts.items()
            ],
            pipeline_total=7,
            consultations_total=8,
            completed_consultations=2,
        )
    )
    ops.get_paid_leads_analytics = AsyncMock(
        return_value=SimpleNamespace(
            total_paid_leads=4,
            sources=[_bucket("Google", 3), _bucket("Meta", 1)],
            classification_terms=["google", "meta"],
        )
    )
    ops.get_consultation_followup_analytics = AsyncMock(
        return_value=SimpleNamespace(
            consultation_status=[
                _bucket(key, count) for key, count in consultation_counts.items()
            ],
            open_followups=5,
            overdue_followups=2,
        )
    )
    ops.get_consultation_source_counts = AsyncMock(return_value={"carestack": 6, "salesforce": 2})
    ops.get_consultation_location_counts = AsyncMock(return_value={})

    interaction = MagicMock()
    interaction.list_recent_operational_events = AsyncMock(
        return_value=[
            OperationalTimelineEntry(
                kind="lead_created",
                occurred_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                source_provider="salesforce",
                source_kind="salesforce_lead",
                source_external_id="00Q-safe",
                data_class="operational",
                review_status="auto",
                summary="Lead created from Salesforce (id=00Q-safe)",
                projection=None,
            )
        ]
    )
    interaction.get_treatment_payment_aggregate = AsyncMock(
        return_value=SimpleNamespace(
            treatment_presented_count=4,
            treatment_completed_count=2,
            invoice_count=3,
            payment_total_amount=1250.5,
            collected_total=900.0,
            payment_event_count=3,
            first_payment_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            last_payment_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        )
    )

    sync_run = SimpleNamespace(
        meta={"object_scope": "Lead"},
        sf_object=None,
        status="succeeded",
        started_at=datetime(2026, 5, 25, 13, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 25, 13, 1, tzinfo=UTC),
        records_total=10,
        records_succeeded=9,
        records_failed=1,
        error=None,
    )
    integrations = MagicMock()
    integrations.list_latest_runs_for_tenant = AsyncMock(return_value=[(sync_run, "salesforce")])
    client = TestClient(_build_app(ops, interaction, integrations))

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.list_locations = AsyncMock(return_value=[])
        res = client.get(
            "/dashboard/pm"
            "?from=2026-05-01T00:00:00Z"
            "&to=2026-06-01T00:00:00Z"
            "&source_provider=salesforce"
            "&lead_source=Website"
            "&q=00Q"
        )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["from"].startswith("2026-05-01T00:00:00")
    assert body["filters"]["source_provider"] == "salesforce"
    assert body["filters"]["lead_source"] == "Website"
    assert body["filters"]["q"] == "00Q"
    assert body["kpis"][0] == {
        "key": "pipeline_total",
        "label": "Pipeline",
        "value": 7,
        "hint": "Active leads excluding lost",
    }
    assert [stage["key"] for stage in body["funnel"]] == [
        "lead_new",
        "lead_qualified",
        "lead_contacted",
        "lead_booked",
        "consultation_scheduled",
        "consultation_completed",
    ]
    assert body["recent_activity"][0]["summary"] == ("Lead created from Salesforce (id=00Q-safe)")
    assert "payload" not in body["recent_activity"][0]
    assert body["sync_health"][0]["provider"] == "salesforce"
    assert [item["query_id"] for item in body["semantic_analytics"]] == [
        "lead_source_profile.v1",
        "lead_conversion_funnel.v1",
        "paid_leads_by_source.v1",
        "consultation_followup_worklist.v1",
        "treatment_revenue_evidence.v1",
    ]
    assert body["semantic_analytics"][0]["read_model_id"] == "lead_source_profile"
    assert body["semantic_analytics"][0]["export_available"] is True
    assert body["semantic_analytics"][4]["data_classes"] == [
        "billing",
        "integration_metadata",
    ]
    # Salesforce-only filter: outstanding totals stay zero (no CareStack
    # snapshot read), but collected_total / payment_event_count still
    # reflect what the aggregate returned.
    assert body["treatment_payments"] == {
        "status": "available",
        "message": (
            "CareStack treatment/payment aggregates are available, but the "
            "current provider filter is Salesforce-only."
        ),
        "treatment_presented_count": 4,
        "treatment_completed_count": 2,
        "invoice_count": 3,
        "payment_total_amount": 1250.5,
        "collected_total": 900.0,
        "payment_event_count": 3,
        "outstanding_total": 0.0,
        "outstanding_patient_count": 0,
        "has_partial_payments": False,
        "first_payment_at": "2026-05-10T12:00:00Z",
        "last_payment_at": "2026-05-25T12:00:00Z",
        "ar_risk_count": None,
    }

    ops.get_conversion_funnel_analytics.assert_awaited_once()
    interaction.list_recent_operational_events.assert_awaited_once()
    interaction.get_treatment_payment_aggregate.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        source_provider="salesforce",
        location_id=None,
    )
    integrations.list_latest_runs_for_tenant.assert_awaited_once_with(
        _TENANT_ID,
        provider="salesforce",
        limit=10,
    )


def test_pm_dashboard_surfaces_ar_risk_count_for_carestack_view() -> None:
    """ENG-266: when the provider filter is None or carestack, the
    dashboard reads the latest payment-summary aggregate and surfaces
    ``ar_risk_count`` from it. Salesforce-only callers stay on the
    ``None`` path (covered by the contract test above).
    """
    ops = MagicMock()
    _wire_semantic_ops_defaults(ops)
    ops.get_consultation_source_counts = AsyncMock(return_value={})
    ops.get_consultation_location_counts = AsyncMock(return_value={})

    interaction = MagicMock()
    interaction.list_recent_operational_events = AsyncMock(return_value=[])
    interaction.get_treatment_payment_aggregate = AsyncMock(
        return_value=SimpleNamespace(
            treatment_presented_count=0,
            treatment_completed_count=0,
            invoice_count=0,
            payment_total_amount=0.0,
            collected_total=0.0,
            payment_event_count=0,
            first_payment_at=None,
            last_payment_at=None,
        )
    )

    integrations = MagicMock()
    integrations.list_latest_runs_for_tenant = AsyncMock(return_value=[])

    ingest = MagicMock()
    ingest.latest_payment_summary_balances = AsyncMock(
        return_value=SimpleNamespace(
            balance_due_patient=4200.0,
            balance_due_insurance=800.0,
            outstanding_total=5000.0,
            patient_count=9,
            ar_risk_count=3,
            ar_risk_threshold=500.0,
        )
    )

    app = _build_app(ops, interaction, integrations, ingest)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.list_locations = AsyncMock(return_value=[])
        res = client.get("/dashboard/pm?source_provider=carestack")

    assert res.status_code == 200
    body = res.json()
    assert body["treatment_payments"]["ar_risk_count"] == 3
    assert body["treatment_payments"]["outstanding_total"] == 5000.0
    # The dashboard response must never echo per-patient identifiers or
    # per-patient balances — only aggregate counts/totals plus the
    # threshold (which the schema does not expose on the dashboard
    # widget; only the count surfaces). Spot-check the rendered JSON.
    rendered = res.text
    assert "balanceDuePatient" not in rendered
    assert "patientId" not in rendered
    assert "person_uid" not in body["treatment_payments"]
    ingest.latest_payment_summary_balances.assert_awaited_once_with(_TENANT_ID)


def test_pm_dashboard_omits_ar_risk_count_for_salesforce_only_view() -> None:
    """ENG-266: a salesforce-only filter must not pull the CareStack
    payment-summary aggregate; ``ar_risk_count`` stays ``None`` so the
    widget can render an explicit "n/a" state instead of a misleading 0.
    """
    ops = MagicMock()
    _wire_semantic_ops_defaults(ops)
    ops.get_consultation_source_counts = AsyncMock(return_value={})
    ops.get_consultation_location_counts = AsyncMock(return_value={})

    interaction = MagicMock()
    interaction.list_recent_operational_events = AsyncMock(return_value=[])
    interaction.get_treatment_payment_aggregate = AsyncMock(
        return_value=SimpleNamespace(
            treatment_presented_count=0,
            treatment_completed_count=0,
            invoice_count=0,
            payment_total_amount=0.0,
            collected_total=0.0,
            payment_event_count=0,
            first_payment_at=None,
            last_payment_at=None,
        )
    )

    integrations = MagicMock()
    integrations.list_latest_runs_for_tenant = AsyncMock(return_value=[])

    ingest = MagicMock()
    ingest.latest_payment_summary_balances = AsyncMock()  # should NOT be called

    app = _build_app(ops, interaction, integrations, ingest)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.list_locations = AsyncMock(return_value=[])
        res = client.get("/dashboard/pm?source_provider=salesforce")

    assert res.status_code == 200
    body = res.json()
    assert body["treatment_payments"]["ar_risk_count"] is None
    ingest.latest_payment_summary_balances.assert_not_awaited()


def test_pm_dashboard_forwards_location_id_to_treatment_aggregate() -> None:
    """ENG-267: when the PM dashboard receives a ``location_id`` query
    param, it must pass it through to
    ``InteractionService.get_treatment_payment_aggregate`` so the
    Treatment & payments widget recalculates by location.
    """
    location_id = uuid.uuid4()

    ops = MagicMock()
    _wire_semantic_ops_defaults(ops)
    ops.get_consultation_source_counts = AsyncMock(return_value={})
    ops.get_consultation_location_counts = AsyncMock(return_value={})

    interaction = MagicMock()
    interaction.list_recent_operational_events = AsyncMock(return_value=[])
    interaction.get_treatment_payment_aggregate = AsyncMock(
        return_value=SimpleNamespace(
            treatment_presented_count=0,
            treatment_completed_count=0,
            invoice_count=0,
            payment_total_amount=0.0,
            collected_total=0.0,
            payment_event_count=0,
            first_payment_at=None,
            last_payment_at=None,
        )
    )

    integrations = MagicMock()
    integrations.list_latest_runs_for_tenant = AsyncMock(return_value=[])

    app = _build_app(ops, interaction, integrations)
    client = TestClient(app)

    with patch.object(dashboard_router, "LocationService") as location_cls:
        location_cls.return_value.list_locations = AsyncMock(return_value=[])
        res = client.get(f"/dashboard/pm?location_id={location_id}")

    assert res.status_code == 200
    interaction.get_treatment_payment_aggregate.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=None,
        occurred_to=None,
        source_provider=None,
        location_id=location_id,
    )


def test_pm_leads_returns_individual_lead_rows_without_raw_extra() -> None:
    person_uid = uuid.uuid4()
    lead_id = uuid.uuid4()
    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=lead_id,
                person_uid=person_uid,
                source="Website",
                status="new",
                extra={
                    "sf_lead_id": "00Q-visible",
                    "raw_sensitive_field": "must not render",
                },
                created_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 25, 12, 5, tzinfo=UTC),
            )
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="Jane Lead",
                given_name="Jane",
                family_name="Lead",
                identifiers=[
                    SimpleNamespace(kind="email", value="jane@example.test"),
                    SimpleNamespace(kind="phone", value="+15551234567"),
                ],
            )
        ]
    )
    identity.source_providers_for = AsyncMock(return_value={person_uid: ["salesforce"]})

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get(
        "/dashboard/pm/leads?from=2026-05-01T00:00:00Z&source_provider=salesforce&status=new&q=Jane"
    )

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert body["has_next"] is False
    assert body["has_previous"] is False
    assert body["items"][0]["id"] == str(lead_id)
    assert body["items"][0]["display_name"] == "Jane Lead"
    assert body["items"][0]["email"] == "jane@example.test"
    assert body["items"][0]["lead_source"] == "Website"
    assert body["items"][0]["source_provider"] == "salesforce"
    assert body["items"][0]["source_external_id"] == "00Q-visible"
    rendered = res.text
    assert "raw_sensitive_field" not in rendered
    assert "must not render" not in rendered


def test_pm_leads_includes_carestack_patient_source_rows() -> None:
    person_uid = uuid.uuid4()
    link_id = uuid.uuid4()
    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(return_value=[])
    ops.latest_consultations_for_persons = AsyncMock(
        return_value={person_uid: SimpleNamespace(
            status="scheduled",
            scheduled_at=None,
            provider_created_at=None,
            source_provider=None,
            location_id=None,
        )}
    )
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.count_source_links_for_dashboard = AsyncMock(return_value=1)
    identity.source_links_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=link_id,
                person_uid=person_uid,
                source_system="carestack",
                source_instance="carestack-main",
                source_kind="patient",
                source_id="cs-patient-123",
                first_seen_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                last_seen_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
        ]
    )
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="CareStack Patient",
                given_name="CareStack",
                family_name="Patient",
                identifiers=[
                    SimpleNamespace(kind="email", value="care@example.test"),
                ],
            )
        ]
    )
    identity.source_providers_for = AsyncMock(return_value={person_uid: ["carestack"]})

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get("/dashboard/pm/leads?source_provider=carestack")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["has_next"] is False
    assert body["has_previous"] is False
    assert body["items"][0]["id"] == str(link_id)
    assert body["items"][0]["display_name"] == "CareStack Patient"
    assert body["items"][0]["source_provider"] == "carestack"
    assert body["items"][0]["source_external_id"] == "cs-patient-123"
    assert body["items"][0]["status"] == "scheduled"
    assert body["items"][0]["lead_source"] == "CareStack patient"
    ops.list_leads_for_dashboard.assert_not_awaited()


def test_pm_leads_paginates_combined_rows() -> None:
    first_person_uid = uuid.uuid4()
    second_person_uid = uuid.uuid4()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    ops = MagicMock()
    ops.count_leads_for_dashboard = AsyncMock(return_value=2)
    # The repository contract returns newest-first; rows without any
    # consultation keep that order after the consultation-date sort.
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=second_id,
                person_uid=second_person_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-second"},
                created_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=first_id,
                person_uid=first_person_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-first"},
                created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            ),
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.source_links_for_dashboard = AsyncMock(return_value=[])
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=first_person_uid,
                display_name="First Lead",
                given_name="First",
                family_name="Lead",
                identifiers=[],
            ),
            SimpleNamespace(
                id=second_person_uid,
                display_name="Second Lead",
                given_name="Second",
                family_name="Lead",
                identifiers=[],
            ),
        ]
    )
    identity.source_providers_for = AsyncMock(return_value={})

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get("/dashboard/pm/leads?source_provider=salesforce&limit=1&offset=1")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["has_next"] is False
    assert body["has_previous"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(first_id)


def test_pm_leads_location_tab_sort_lead_vs_appointment() -> None:
    """On a location tab, sort=lead orders by lead created_at; sort=appointment
    orders by consultation_provider_created_at. The two leads are crossed
    (newer lead has the older appointment) so the order must flip."""
    recent_lead_uid = uuid.uuid4()  # newest lead, oldest appointment
    recent_appt_uid = uuid.uuid4()  # oldest lead, newest appointment
    recent_lead_id = uuid.uuid4()
    recent_appt_id = uuid.uuid4()

    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=recent_lead_id,
                person_uid=recent_lead_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-recent-lead"},
                created_at=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=recent_appt_id,
                person_uid=recent_appt_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-recent-appt"},
                created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            ),
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(
        return_value={
            recent_lead_uid: SimpleNamespace(
                status="scheduled", scheduled_at=None,
                provider_created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                source_provider="carestack", location_id=None,
            ),
            recent_appt_uid: SimpleNamespace(
                status="scheduled", scheduled_at=None,
                provider_created_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
                source_provider="carestack", location_id=None,
            ),
        }
    )
    # Both persons resolve to the galleria tab.
    ops.classify_location_tabs = AsyncMock(
        return_value={recent_lead_uid: "galleria", recent_appt_uid: "galleria"}
    )

    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.source_links_for_dashboard = AsyncMock(return_value=[])
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=recent_lead_uid, display_name="Recent Lead",
                given_name="Recent", family_name="Lead", identifiers=[],
            ),
            SimpleNamespace(
                id=recent_appt_uid, display_name="Recent Appt",
                given_name="Recent", family_name="Appt", identifiers=[],
            ),
        ]
    )
    identity.source_providers_for = AsyncMock(return_value={})

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    by_lead = client.get("/dashboard/pm/leads?location_tab=galleria&sort=lead")
    assert by_lead.status_code == 200
    lead_order = [i["person_uid"] for i in by_lead.json()["items"]]
    assert lead_order == [str(recent_lead_uid), str(recent_appt_uid)]

    by_appt = client.get(
        "/dashboard/pm/leads?location_tab=galleria&sort=appointment"
    )
    assert by_appt.status_code == 200
    appt_order = [i["person_uid"] for i in by_appt.json()["items"]]
    assert appt_order == [str(recent_appt_uid), str(recent_lead_uid)]


def test_pm_leads_location_tab_paginates_by_person_not_row() -> None:
    """A location tab renders one card per person, so pagination is per-person:
    a Salesforce+CareStack person counts once toward total and is never split
    across pages — both its rows arrive together on the person's page."""
    solo_uid = uuid.uuid4()  # newest lead, SF only
    unified_uid = uuid.uuid4()  # older, SF + CareStack (two rows, one card)
    solo_sf_id = uuid.uuid4()
    unified_sf_id = uuid.uuid4()
    unified_cs_id = uuid.uuid4()

    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=solo_sf_id, person_uid=solo_uid, source="Website", status="new",
                extra={"sf_lead_id": "00Q-solo"},
                created_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=unified_sf_id, person_uid=unified_uid, source="Website", status="new",
                extra={"sf_lead_id": "00Q-unified"},
                created_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
            ),
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    ops.classify_location_tabs = AsyncMock(
        return_value={solo_uid: "galleria", unified_uid: "galleria"}
    )

    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.source_links_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=unified_cs_id, person_uid=unified_uid,
                source_system="carestack", source_instance="carestack-main",
                source_kind="patient", source_id="cs-unified",
                first_seen_at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
                last_seen_at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
            )
        ]
    )
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(id=solo_uid, display_name="Solo SF",
                            given_name="Solo", family_name="SF", identifiers=[]),
            SimpleNamespace(id=unified_uid, display_name="Unified Person",
                            given_name="Unified", family_name="Person", identifiers=[]),
        ]
    )
    identity.source_providers_for = AsyncMock(
        return_value={unified_uid: ["salesforce", "carestack"]}
    )

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    # total counts PERSONS (2), not rows (3). Page 1 (limit=1) = the newest-lead
    # person (solo), one row.
    page1 = client.get(
        "/dashboard/pm/leads?location_tab=galleria&sort=lead&limit=1&offset=0"
    ).json()
    assert page1["total"] == 2
    assert len(page1["items"]) == 1
    assert page1["items"][0]["person_uid"] == str(solo_uid)

    # Page 2 = the unified person — BOTH rows together, never split.
    page2 = client.get(
        "/dashboard/pm/leads?location_tab=galleria&sort=lead&limit=1&offset=1"
    ).json()
    assert page2["total"] == 2
    assert {i["person_uid"] for i in page2["items"]} == {str(unified_uid)}
    assert len(page2["items"]) == 2  # SF + CareStack rows on the same page


def test_pm_leads_searches_identity_and_returns_both_provider_rows() -> None:
    person_uid = uuid.uuid4()
    sf_lead_id = uuid.uuid4()
    carestack_link_id = uuid.uuid4()
    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=sf_lead_id,
                person_uid=person_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-shared"},
                created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            )
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(
        return_value={person_uid: SimpleNamespace(
            status="scheduled",
            scheduled_at=None,
            provider_created_at=None,
            source_provider=None,
            location_id=None,
        )}
    )
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.source_links_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=carestack_link_id,
                person_uid=person_uid,
                source_system="carestack",
                source_instance="carestack-main",
                source_kind="patient",
                source_id="cs-shared",
                first_seen_at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
                last_seen_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
        ]
    )
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=person_uid,
                display_name="Shared Person",
                given_name="Shared",
                family_name="Person",
                identifiers=[
                    SimpleNamespace(kind="email", value="shared@example.test"),
                    SimpleNamespace(kind="phone", value="+15551230000"),
                ],
            )
        ]
    )
    identity.source_providers_for = AsyncMock(
        return_value={person_uid: ["salesforce", "carestack"]}
    )

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get("/dashboard/pm/leads?q=shared@example.test")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert {item["source_provider"] for item in body["items"]} == {
        "salesforce",
        "carestack",
    }
    assert {item["person_uid"] for item in body["items"]} == {str(person_uid)}


def test_pm_leads_linked_only_returns_rows_for_cross_provider_persons() -> None:
    linked_person_uid = uuid.uuid4()
    salesforce_only_person_uid = uuid.uuid4()
    linked_lead_id = uuid.uuid4()
    salesforce_only_lead_id = uuid.uuid4()
    carestack_link_id = uuid.uuid4()
    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=linked_lead_id,
                person_uid=linked_person_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-linked"},
                created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=salesforce_only_lead_id,
                person_uid=salesforce_only_person_uid,
                source="Website",
                status="new",
                extra={"sf_lead_id": "00Q-salesforce-only"},
                created_at=datetime(2026, 5, 24, 11, 0, tzinfo=UTC),
                updated_at=datetime(2026, 5, 24, 11, 0, tzinfo=UTC),
            ),
        ]
    )
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.source_links_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=carestack_link_id,
                person_uid=linked_person_uid,
                source_system="carestack",
                source_instance="carestack-main",
                source_kind="patient",
                source_id="cs-linked",
                first_seen_at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
                last_seen_at=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
        ]
    )
    identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=linked_person_uid,
                display_name="Linked Person",
                given_name="Linked",
                family_name="Person",
                identifiers=[],
            ),
            SimpleNamespace(
                id=salesforce_only_person_uid,
                display_name="Salesforce Only",
                given_name="Salesforce",
                family_name="Only",
                identifiers=[],
            ),
        ]
    )
    identity.source_providers_for = AsyncMock(
        return_value={
            linked_person_uid: ["salesforce", "carestack"],
            salesforce_only_person_uid: ["salesforce"],
        }
    )

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get("/dashboard/pm/leads?linked_only=true")

    assert res.status_code == 200
    body = res.json()
    # total counts unique linked persons, not individual rows
    assert body["total"] == 1
    assert {item["person_uid"] for item in body["items"]} == {str(linked_person_uid)}
    assert {item["source_provider"] for item in body["items"]} == {
        "salesforce",
        "carestack",
    }


def test_pm_leads_forwards_exact_lead_source_match_to_ops() -> None:
    ops = MagicMock()
    ops.list_leads_for_dashboard = AsyncMock(return_value=[])
    ops.count_leads_for_dashboard = AsyncMock(return_value=0)
    ops.latest_consultations_for_persons = AsyncMock(return_value={})
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.list_by_ids = AsyncMock(return_value=[])
    identity.source_providers_for = AsyncMock(return_value={})

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get(
        "/dashboard/pm/leads?source_provider=salesforce"
        "&lead_source=Facebook&lead_source_match=exact"
    )

    assert res.status_code == 200
    ops.list_leads_for_dashboard.assert_awaited_once()
    list_kwargs = ops.list_leads_for_dashboard.await_args.kwargs
    assert list_kwargs["lead_source"] == "Facebook"
    assert list_kwargs["lead_source_match"] == "exact"
    count_kwargs = ops.count_leads_for_dashboard.await_args.kwargs
    assert count_kwargs["lead_source"] == "Facebook"
    assert count_kwargs["lead_source_match"] == "exact"


def test_pm_leads_rejects_unknown_lead_source_match() -> None:
    ops = MagicMock()
    interaction = MagicMock()
    integrations = MagicMock()

    app = _build_app(ops, interaction, integrations)
    client = TestClient(app)

    res = client.get("/dashboard/pm/leads?lead_source_match=fuzzy")

    assert res.status_code == 422


def test_pm_lead_sources_groups_buckets_by_provider() -> None:
    ops = MagicMock()
    ops.get_lead_source_counts = AsyncMock(
        return_value={"Facebook": 39, "Website Form": 26, "unknown": 62397}
    )
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.count_source_links_for_dashboard = AsyncMock(return_value=55000)

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get("/dashboard/pm/lead-sources")

    assert res.status_code == 200
    body = res.json()
    providers = {p["provider"]: p for p in body["providers"]}
    assert set(providers) == {"salesforce", "carestack"}
    salesforce = providers["salesforce"]
    assert salesforce["total"] == 39 + 26 + 62397
    assert salesforce["sources"] == [
        {"key": "Facebook", "count": 39},
        {"key": "Website Form", "count": 26},
        {"key": "unknown", "count": 62397},
    ]
    carestack = providers["carestack"]
    assert carestack["total"] == 55000
    assert carestack["sources"] == []
    ops.get_lead_source_counts.assert_awaited_once()
    assert (
        ops.get_lead_source_counts.await_args.kwargs["source_provider"]
        == "salesforce"
    )
    identity.count_source_links_for_dashboard.assert_awaited_once()


def test_pm_lead_sources_forwards_date_window() -> None:
    ops = MagicMock()
    ops.get_lead_source_counts = AsyncMock(return_value={})
    interaction = MagicMock()
    integrations = MagicMock()
    identity = MagicMock()
    identity.count_source_links_for_dashboard = AsyncMock(return_value=0)

    app = _build_app(ops, interaction, integrations)
    app.dependency_overrides[get_identity_service] = lambda: identity
    client = TestClient(app)

    res = client.get(
        "/dashboard/pm/lead-sources?from=2026-05-01T00:00:00Z&to=2026-06-01T00:00:00Z"
    )

    assert res.status_code == 200
    counts_kwargs = ops.get_lead_source_counts.await_args.kwargs
    assert counts_kwargs["created_from"] == datetime(2026, 5, 1, tzinfo=UTC)
    assert counts_kwargs["created_to"] == datetime(2026, 6, 1, tzinfo=UTC)
    links_kwargs = identity.count_source_links_for_dashboard.await_args.kwargs
    assert links_kwargs["first_seen_from"] == datetime(2026, 5, 1, tzinfo=UTC)
    assert links_kwargs["first_seen_to"] == datetime(2026, 6, 1, tzinfo=UTC)
