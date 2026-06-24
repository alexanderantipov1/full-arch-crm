"""HTTP-level tests for the backfill router (ENG-246 / ENG-247).

The four per-entity helpers are mocked at the FastAPI dependency layer so
the tests stay fast and don't touch real Salesforce / CareStack. We focus
on the sync-run lifecycle wiring that ENG-247 added on top of the
Phase-1 router: every leg opens a real `integrations.sync_run` via
`IntegrationService.open_provider_sync_run`, then closes it with the
right `ProviderSyncStatus` (succeeded / partial / failed /
skipped_credential).
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_carestack_accounting_transaction_ingest_service,
    get_carestack_appointment_ingest_service,
    get_carestack_patient_ingest_service,
    get_carestack_payment_summary_ingest_service,
    get_integration_service,
    get_principal_with_tenant,
    get_sf_event_ingest_service,
    get_sf_lead_ingest_service,
    get_sf_task_ingest_service,
)
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import backfill as backfill_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tenant.credential_service import NoCredentialError

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000247")


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="oncall@fusiondentalimplants.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _integration_service() -> MagicMock:
    svc = MagicMock()
    svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    svc.close_provider_sync_run = AsyncMock()
    return svc


def _stub_service(method: str, returns: object) -> MagicMock:
    svc = MagicMock()
    setattr(svc, method, AsyncMock(return_value=returns))
    return svc


def _stub_service_raises(method: str, exc: BaseException) -> MagicMock:
    svc = MagicMock()
    setattr(svc, method, AsyncMock(side_effect=exc))
    return svc


def _build_app(
    *,
    integration: MagicMock,
    sf_leads: MagicMock | None = None,
    sf_events: MagicMock | None = None,
    sf_tasks: MagicMock | None = None,
    cs_patients: MagicMock | None = None,
    cs_appointments: MagicMock | None = None,
    cs_accounting_transactions: MagicMock | None = None,
    cs_payment_summary: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(backfill_router.router)
    app.dependency_overrides[get_principal_with_tenant] = _principal
    app.dependency_overrides[get_integration_service] = lambda: integration
    app.dependency_overrides[get_sf_lead_ingest_service] = lambda: (
        sf_leads or MagicMock()
    )
    app.dependency_overrides[get_sf_event_ingest_service] = lambda: (
        sf_events or MagicMock()
    )
    app.dependency_overrides[get_sf_task_ingest_service] = lambda: (
        sf_tasks or MagicMock()
    )
    app.dependency_overrides[get_carestack_patient_ingest_service] = lambda: (
        cs_patients or MagicMock()
    )
    app.dependency_overrides[get_carestack_appointment_ingest_service] = lambda: (
        cs_appointments or MagicMock()
    )
    app.dependency_overrides[
        get_carestack_accounting_transaction_ingest_service
    ] = lambda: (cs_accounting_transactions or MagicMock())
    app.dependency_overrides[
        get_carestack_payment_summary_ingest_service
    ] = lambda: (cs_payment_summary or MagicMock())
    return app


def test_sf_leads_leg_opens_and_closes_real_sync_run() -> None:
    integration = _integration_service()
    sf_leads = _stub_service("pull_all_since", 42)
    app = _build_app(integration=integration, sf_leads=sf_leads)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"since": "2026-01-01T00:00:00Z", "entities": ["sf_leads"]},
        )
    assert res.status_code == 200
    body = res.json()
    legs = body["legs"]
    assert len(legs) == 1
    leg = legs[0]
    assert leg["entity"] == "sf_leads"
    assert leg["imported"] == 42
    assert leg["sync_run_id"] == str(_SYNC_RUN_ID)
    assert leg["sync_run_status"] == "succeeded"
    assert leg["error"] is None

    integration.open_provider_sync_run.assert_awaited_once()
    open_kwargs = integration.open_provider_sync_run.await_args.kwargs
    assert open_kwargs["provider"] == "salesforce"
    assert open_kwargs["object_scope"] == "lead"
    assert open_kwargs["trigger"] == "backfill"

    integration.close_provider_sync_run.assert_awaited_once()
    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["status"] == "succeeded"
    assert close_kwargs["records_total"] == 42
    assert close_kwargs["records_succeeded"] == 42
    assert close_kwargs["records_failed"] == 0


def test_sf_tasks_entity_is_supported_and_propagates_counts() -> None:
    integration = _integration_service()
    sf_tasks = _stub_service(
        "import_all_since",
        SimpleNamespace(imported_count=12, skipped_count=3),
    )
    app = _build_app(integration=integration, sf_tasks=sf_tasks)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"since": "2026-01-01T00:00:00Z", "entities": ["sf_tasks"]},
        )
    assert res.status_code == 200
    leg = res.json()["legs"][0]
    assert leg["entity"] == "sf_tasks"
    assert leg["imported"] == 12
    assert leg["skipped"] == 3
    # 12 succeeded + 3 unresolved-WhoId = partial.
    assert leg["sync_run_status"] == "partial"
    assert leg["sync_run_id"] == str(_SYNC_RUN_ID)

    open_kwargs = integration.open_provider_sync_run.await_args.kwargs
    assert open_kwargs["provider"] == "salesforce"
    assert open_kwargs["object_scope"] == "task"

    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["records_total"] == 15
    assert close_kwargs["records_succeeded"] == 12
    assert close_kwargs["records_failed"] == 3


def test_partial_status_when_all_records_skipped() -> None:
    integration = _integration_service()
    sf_events = _stub_service(
        "import_all_since",
        SimpleNamespace(imported_count=0, skipped_count=5),
    )
    app = _build_app(integration=integration, sf_events=sf_events)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"since": "2026-01-01T00:00:00Z", "entities": ["sf_events"]},
        )
    leg = res.json()["legs"][0]
    # 0 succeeded + 5 failed → "failed" (no successes at all).
    assert leg["sync_run_status"] == "failed"


def test_provider_exception_closes_run_as_failed() -> None:
    integration = _integration_service()
    sf_leads = _stub_service_raises(
        "pull_all_since", RuntimeError("provider 503 service unavailable")
    )
    app = _build_app(integration=integration, sf_leads=sf_leads)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"since": "2026-01-01T00:00:00Z", "entities": ["sf_leads"]},
        )
    assert res.status_code == 200  # legs absorb their own errors
    leg = res.json()["legs"][0]
    assert leg["sync_run_status"] == "failed"
    assert "provider 503" in (leg["error"] or "")
    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["status"] == "failed"
    assert close_kwargs["error"] is not None
    assert "provider 503" in close_kwargs["error"]


@pytest.mark.asyncio
async def test_cancellation_is_not_absorbed_as_leg_failure() -> None:
    integration = _integration_service()
    sf_leads = _stub_service_raises("pull_all_since", asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await backfill_router._run_sf_leads(
            integration,
            _principal(),
            sf_leads,
            _TENANT_ID,
            backfill_router._DEFAULT_SINCE,
        )

    integration.open_provider_sync_run.assert_awaited_once()
    integration.close_provider_sync_run.assert_not_awaited()


@pytest.mark.parametrize(
    "exc",
    [
        NoCredentialError("no carestack credential"),
        type("SfNotConnectedError", (Exception,), {})(),
    ],
)
def test_credential_error_closes_run_as_skipped_credential(
    exc: BaseException,
) -> None:
    integration = _integration_service()
    cs_patients = _stub_service_raises("pull_all_since", exc)
    app = _build_app(integration=integration, cs_patients=cs_patients)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"since": "2026-01-01T00:00:00Z", "entities": ["cs_patients"]},
        )
    leg = res.json()["legs"][0]
    assert leg["sync_run_status"] == "skipped_credential"
    assert leg["error"] == "no active credential for this tenant/provider"
    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["status"] == "skipped_credential"


def test_all_default_entities_run_when_none_supplied() -> None:
    integration = _integration_service()
    # 5 dedicated mocks so each leg has its own open/close call.
    sf_leads = _stub_service("pull_all_since", 0)
    sf_events = _stub_service(
        "import_all_since", SimpleNamespace(imported_count=0, skipped_count=0)
    )
    sf_tasks = _stub_service(
        "import_all_since", SimpleNamespace(imported_count=0, skipped_count=0)
    )
    cs_patients = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=0,
            skipped_count=0,
            page_count=0,
            next_continue_token=None,
        ),
    )
    cs_appointments = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=0,
            skipped_count=0,
            page_count=0,
            next_continue_token=None,
        ),
    )
    app = _build_app(
        integration=integration,
        sf_leads=sf_leads,
        sf_events=sf_events,
        sf_tasks=sf_tasks,
        cs_patients=cs_patients,
        cs_appointments=cs_appointments,
    )

    with TestClient(app) as client:
        res = client.post("/backfill/run", json={})
    assert res.status_code == 200
    legs = res.json()["legs"]
    entities = [leg["entity"] for leg in legs]
    assert entities == [
        "sf_leads",
        "sf_events",
        "sf_tasks",
        "cs_patients",
        "cs_appointments",
    ]
    assert integration.open_provider_sync_run.await_count == 5
    assert integration.close_provider_sync_run.await_count == 5


# ---------------------------------------------------------- ENG-285 throttled CareStack payments backfill


def test_cs_accounting_transactions_leg_opens_and_closes_sync_run() -> None:
    """ENG-285: ``carestack_accounting_transactions`` scope drives the
    throttled backfill and journals a ``sync_run`` row exactly like the
    other CareStack legs.
    """
    integration = _integration_service()
    cs_at = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=128,
            skipped_count=4,
            page_count=12,
            next_continue_token=None,
        ),
    )
    app = _build_app(integration=integration, cs_accounting_transactions=cs_at)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"entities": ["carestack_accounting_transactions"]},
        )
    assert res.status_code == 200
    leg = res.json()["legs"][0]
    assert leg["entity"] == "carestack_accounting_transactions"
    assert leg["imported"] == 128
    assert leg["skipped"] == 4
    assert leg["pages"] == 12
    assert leg["next_continue_token"] is None
    assert leg["sync_run_id"] == str(_SYNC_RUN_ID)
    # 128 succeeded + 4 unlinked patients = partial.
    assert leg["sync_run_status"] == "partial"

    open_kwargs = integration.open_provider_sync_run.await_args.kwargs
    assert open_kwargs["provider"] == "carestack"
    assert open_kwargs["object_scope"] == "accounting_transaction"
    assert open_kwargs["trigger"] == "backfill"

    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["records_total"] == 132
    assert close_kwargs["records_succeeded"] == 128
    assert close_kwargs["records_failed"] == 4


def test_cs_accounting_transactions_default_since_is_2026_01_01() -> None:
    """When the operator omits ``since`` the AT backfill anchors at
    2026-01-01 — the fiscal year the operator is reconstructing — even
    though the route-level default (epoch) is wider."""
    integration = _integration_service()
    cs_at = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=0,
            skipped_count=0,
            page_count=0,
            next_continue_token=None,
        ),
    )
    app = _build_app(integration=integration, cs_accounting_transactions=cs_at)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"entities": ["carestack_accounting_transactions"]},
        )
    assert res.status_code == 200
    cs_at.pull_all_since.assert_awaited_once()
    call_args = cs_at.pull_all_since.await_args
    since_arg = call_args.args[1] if len(call_args.args) >= 2 else call_args.kwargs.get("since")
    import datetime as _dt

    assert since_arg == _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)


def test_cs_accounting_transactions_operator_since_overrides_default() -> None:
    """An operator-supplied ``since`` reaches the backfill service unchanged."""
    integration = _integration_service()
    cs_at = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=0,
            skipped_count=0,
            page_count=0,
            next_continue_token=None,
        ),
    )
    app = _build_app(integration=integration, cs_accounting_transactions=cs_at)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={
                "since": "2026-03-15T00:00:00Z",
                "entities": ["carestack_accounting_transactions"],
            },
        )
    assert res.status_code == 200
    call_args = cs_at.pull_all_since.await_args
    since_arg = call_args.args[1] if len(call_args.args) >= 2 else call_args.kwargs.get("since")
    import datetime as _dt

    assert since_arg == _dt.datetime(2026, 3, 15, tzinfo=_dt.UTC)


def test_cs_accounting_transactions_resume_token_propagates_to_response() -> None:
    """Backoff exhausted → ``next_continue_token`` surfaces so the
    operator can re-invoke the backfill at the same pagination point.
    """
    integration = _integration_service()
    cs_at = _stub_service(
        "pull_all_since",
        SimpleNamespace(
            imported_count=300,
            skipped_count=10,
            page_count=6,
            next_continue_token="continue-here",
        ),
    )
    app = _build_app(integration=integration, cs_accounting_transactions=cs_at)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"entities": ["carestack_accounting_transactions"]},
        )
    leg = res.json()["legs"][0]
    assert leg["next_continue_token"] == "continue-here"
    assert leg["pages"] == 6


def test_cs_payment_summary_leg_opens_and_closes_sync_run() -> None:
    integration = _integration_service()
    cs_ps = _stub_service(
        "pull_all_payment_summaries",
        SimpleNamespace(
            snapshot_count=900,
            skipped_count=3,
            error_count=5,
            patient_count=908,
        ),
    )
    app = _build_app(integration=integration, cs_payment_summary=cs_ps)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run", json={"entities": ["carestack_payment_summary"]}
        )
    assert res.status_code == 200
    leg = res.json()["legs"][0]
    assert leg["entity"] == "carestack_payment_summary"
    assert leg["imported"] == 900
    # skipped_count + error_count both contribute to the failure side
    # of the partial total (per-patient errors are still failure-
    # isolated by the service, but the operator should see them).
    assert leg["skipped"] == 8
    assert leg["sync_run_id"] == str(_SYNC_RUN_ID)
    assert leg["sync_run_status"] == "partial"

    open_kwargs = integration.open_provider_sync_run.await_args.kwargs
    assert open_kwargs["provider"] == "carestack"
    assert open_kwargs["object_scope"] == "payment_summary"
    assert open_kwargs["trigger"] == "backfill"

    close_kwargs = integration.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["records_total"] == 908
    assert close_kwargs["records_succeeded"] == 900
    assert close_kwargs["records_failed"] == 8


def test_cs_payment_summary_credential_error_closes_skipped_credential() -> None:
    """A missing CareStack credential surfaces as ``skipped_credential``
    on the new payment-summary leg, matching the existing CareStack
    leg behaviour."""
    integration = _integration_service()
    cs_ps = _stub_service_raises(
        "pull_all_payment_summaries",
        NoCredentialError("no carestack credential"),
    )
    app = _build_app(integration=integration, cs_payment_summary=cs_ps)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run", json={"entities": ["carestack_payment_summary"]}
        )
    leg = res.json()["legs"][0]
    assert leg["sync_run_status"] == "skipped_credential"
    assert leg["error"] == "no active credential for this tenant/provider"


def test_cs_accounting_transactions_provider_failure_closes_failed() -> None:
    integration = _integration_service()
    cs_at = _stub_service_raises(
        "pull_all_since", RuntimeError("provider 502 bad gateway")
    )
    app = _build_app(integration=integration, cs_accounting_transactions=cs_at)

    with TestClient(app) as client:
        res = client.post(
            "/backfill/run",
            json={"entities": ["carestack_accounting_transactions"]},
        )
    leg = res.json()["legs"][0]
    assert leg["sync_run_status"] == "failed"
    assert "provider 502" in (leg["error"] or "")
