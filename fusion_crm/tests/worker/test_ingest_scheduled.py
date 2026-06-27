"""Unit tests for the ENG-222 ingest scheduler.

Covers the per-tenant pull entry points (CareStack + Salesforce) and
the fanout cron summary.

We mock out:
- ``async_session`` so no DB is required.
- ``IntegrationCredentialService`` to control the no-credential path.
- The CareStack / Salesforce client constructors to avoid real HTTP.
- The ingest service classes so we exercise the orchestration only.

The actual service-level behaviour is exercised by the service-specific
test suites (ENG-217 / ENG-219 / ENG-221).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.jobs import carestack_pull, salesforce_pull
from apps.worker.jobs.ingest_scheduled import (
    _CARESTACK_SCHEMA_OBJECTS,
    _carestack_counters,
    _counter_status,
    _scheduler_principal,
    ingest_scheduled_fanout,
    pull_carestack_for_all_tenants,
    pull_carestack_for_tenant,
    pull_salesforce_for_all_tenants,
    pull_salesforce_for_tenant,
    refresh_carestack_schemas_for_tenant,
    refresh_salesforce_schemas_for_tenant,
)
from apps.worker.jobs.salesforce_token_keepalive import (
    refresh_salesforce_token_for_tenant,
    refresh_salesforce_tokens,
)
from packages.core.security import Role
from packages.core.types import TenantId
from packages.ingest.schemas import SchemaDiffOut
from packages.ingest.sf_schema_sync import SF_FULL_FIDELITY_OBJECTS
from packages.integrations.carestack.exceptions import CareStackApiError
from packages.integrations.salesforce import SfTokens
from packages.integrations.salesforce.exceptions import SfNotConnectedError
from packages.tenant.credential_service import NoCredentialError

_TENANT_UUID = uuid.uuid4()
_TENANT_ID = TenantId(_TENANT_UUID)
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000239")


def _fake_session_cm() -> Any:
    @asynccontextmanager
    async def _cm():
        yield MagicMock()

    return _cm()


def _integration_service() -> MagicMock:
    svc = MagicMock()
    svc.open_provider_sync_run = AsyncMock(return_value=SimpleNamespace(id=_SYNC_RUN_ID))
    svc.close_provider_sync_run = AsyncMock()
    return svc


# ----------------------------------------------------- scheduler_principal


def test_scheduler_principal_carries_system_role_and_tenant() -> None:
    principal = _scheduler_principal(_TENANT_ID)
    assert principal.tenant_id == _TENANT_ID
    assert Role.SYSTEM in principal.roles
    assert principal.context.get("actor") == "system:ingest_scheduler"


# ----------------------------------------------------- Salesforce token keepalive


@pytest.mark.asyncio
async def test_refresh_salesforce_token_returns_skipped_when_no_oauth() -> None:
    with patch(
        "apps.worker.jobs.salesforce_token_keepalive.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.IntegrationCredentialService"
    ) as cred_cls:
        cred_cls.return_value.read_for = AsyncMock(
            side_effect=NoCredentialError(
                "no salesforce credential",
                details={"provider": "salesforce"},
            )
        )
        result = await refresh_salesforce_token_for_tenant({}, str(_TENANT_UUID))

    assert result == {"skipped": "no_credential"}


@pytest.mark.asyncio
async def test_refresh_salesforce_token_refreshes_and_closes_client() -> None:
    captured: dict[str, Any] = {}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    async def _refresh() -> None:
        await captured["on_refresh"](
            SfTokens(
                access_token="new-access",
                instance_url="https://example.my.salesforce.com",
                refresh_token="rt",
                issued_at="1710000000000",
            )
        )

    fake_client.refresh_access_token = AsyncMock(side_effect=_refresh)

    def _client_factory(
        _payload: dict[str, Any],
        *,
        on_refresh: Any,
        api_key_payload: dict[str, Any] | None,
    ) -> Any:
        captured["on_refresh"] = on_refresh
        captured["api_key_payload"] = api_key_payload
        return fake_client

    async def _read(_tenant_id: Any, _provider: str, kind: str) -> dict[str, Any]:
        if kind == "oauth_token":
            return {
                "access_token": "x",
                "instance_url": "https://example.my.salesforce.com",
                "refresh_token": "rt",
            }
        return {"client_id": "id", "client_secret": "secret"}

    with patch(
        "apps.worker.jobs.salesforce_token_keepalive.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.salesforce_token_keepalive.SfClient.from_credential",
        side_effect=_client_factory,
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=_read)
        cred_cls.return_value.upsert = AsyncMock()
        result = await refresh_salesforce_token_for_tenant({}, str(_TENANT_UUID))

    assert result == {"refreshed": True}
    assert captured["api_key_payload"] == {"client_id": "id", "client_secret": "secret"}
    fake_client.refresh_access_token.assert_awaited_once()
    assert cred_cls.return_value.upsert.await_args.kwargs["last_refreshed_at"] is not None
    fake_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_salesforce_token_invalid_grant_expires_active() -> None:
    fake_client = MagicMock()
    fake_client.refresh_access_token = AsyncMock(
        side_effect=SfNotConnectedError(
            "Salesforce connection expired.",
            details={"action": "reconnect", "sf_error": "invalid_grant"},
        )
    )
    fake_client.close = AsyncMock()
    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(
        return_value={
            "access_token": "x",
            "instance_url": "https://example.my.salesforce.com",
            "refresh_token": "rt",
        }
    )
    cred_svc.expire_active_for = AsyncMock(return_value=1)

    with patch(
        "apps.worker.jobs.salesforce_token_keepalive.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.IntegrationCredentialService",
        return_value=cred_svc,
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.SfClient.from_credential",
        return_value=fake_client,
    ):
        result = await refresh_salesforce_token_for_tenant({}, str(_TENANT_UUID))

    assert result == {"skipped": "needs_reconnect", "expired_count": 1}
    cred_svc.expire_active_for.assert_awaited_once()
    fake_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_salesforce_token_transient_failure_does_not_expire() -> None:
    fake_client = MagicMock()
    fake_client.refresh_access_token = AsyncMock(side_effect=TimeoutError("timeout"))
    fake_client.close = AsyncMock()
    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(
        return_value={
            "access_token": "x",
            "instance_url": "https://example.my.salesforce.com",
            "refresh_token": "rt",
        }
    )
    cred_svc.expire_active_for = AsyncMock()

    with patch(
        "apps.worker.jobs.salesforce_token_keepalive.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.IntegrationCredentialService",
        return_value=cred_svc,
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.SfClient.from_credential",
        return_value=fake_client,
    ):
        result = await refresh_salesforce_token_for_tenant({}, str(_TENANT_UUID))

    assert result == {"failed": "transient_failed"}
    cred_svc.expire_active_for.assert_not_awaited()
    fake_client.close.assert_awaited_once()


# ----------------------------------------------------- CareStack pull


@pytest.mark.asyncio
async def test_pull_carestack_returns_skipped_when_no_credential() -> None:
    integration_svc = _integration_service()
    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(
            side_effect=NoCredentialError(
                "no carestack credential", details={"provider": "carestack"}
            )
        )
        result = await pull_carestack_for_tenant({}, str(_TENANT_UUID))

    assert result == {"skipped": "no_credential"}
    integration_svc.close_provider_sync_run.assert_awaited_once()
    assert integration_svc.close_provider_sync_run.await_args.kwargs["status"] == (
        "skipped_credential"
    )


@pytest.mark.asyncio
async def test_pull_carestack_runs_location_patient_and_appointment_services() -> None:
    integration_svc = _integration_service()
    fake_payload = {"client_id": "x", "client_secret": "y"}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()
    fake_location_svc = MagicMock()
    fake_location_svc.import_locations_from_carestack = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"created": 2})
    )
    fake_patient_svc = MagicMock()
    fake_patient_svc.import_recent_patients = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"imported_count": 3})
    )
    fake_appt_svc = MagicMock()
    fake_appt_svc.import_recent_appointments = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"imported_count": 5})
    )
    fake_treatment_svc = MagicMock()
    fake_treatment_svc.import_recent_treatments = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"imported_count": 0})
    )
    fake_invoice_svc = MagicMock()
    fake_invoice_svc.import_recent_invoices = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"imported_count": 0})
    )
    fake_accounting_tx_svc = MagicMock()
    fake_accounting_tx_svc.import_recent_accounting_transactions = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {"imported_count": 4},
            patient_ids=["9001", "9002"],
        )
    )
    fake_treatment_plan_svc = MagicMock()
    fake_treatment_plan_svc.import_treatment_plans = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"accepted_count": 0})
    )
    fake_payment_summary_svc = MagicMock()
    fake_payment_summary_svc.import_payment_summary_snapshots = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"snapshot_count": 7})
    )
    fake_payment_summary_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=2, skipped_count=0, error_count=0, patient_count=2
        )
    )

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.LocationService",
        return_value=fake_location_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPatientIngestService",
        return_value=fake_patient_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAppointmentIngestService",
        return_value=fake_appt_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentIngestService",
        return_value=fake_treatment_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackInvoiceIngestService",
        return_value=fake_invoice_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAccountingTransactionIngestService",
        return_value=fake_accounting_tx_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPaymentSummaryIngestService",
        return_value=fake_payment_summary_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentPlanIngestService",
        return_value=fake_treatment_plan_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=fake_payload)
        result = await pull_carestack_for_tenant({}, str(_TENANT_UUID))

    assert result == {
        "locations": {"created": 2},
        "patients": {"imported_count": 3},
        "appointments": {"imported_count": 5},
        "treatments": {"imported_count": 0},
        "invoices": {"imported_count": 0},
        "accounting_transactions": {"imported_count": 4},
        "payment_summaries": {"snapshot_count": 7},
        "treatment_plans": {"accepted_count": 0},
        "failed_legs": [],
    }
    fake_location_svc.import_locations_from_carestack.assert_awaited_once()
    fake_patient_svc.import_recent_patients.assert_awaited_once()
    fake_appt_svc.import_recent_appointments.assert_awaited_once()
    fake_accounting_tx_svc.import_recent_accounting_transactions.assert_awaited_once()
    fake_payment_summary_svc.import_payment_summary_snapshots.assert_awaited_once()
    # ENG-305: the live signal refreshes payment-summary for every
    # patient whose row was just imported from accounting-transactions.
    fake_payment_summary_svc.import_payment_summary_for_patients.assert_awaited_once()
    targeted_call = (
        fake_payment_summary_svc.import_payment_summary_for_patients.await_args
    )
    assert targeted_call.args[1] == ["9001", "9002"]
    assert "commit" in targeted_call.kwargs
    fake_client.close.assert_awaited_once()
    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "succeeded"


@pytest.mark.asyncio
async def test_pull_carestack_isolates_a_provider_blocked_leg() -> None:
    """A provider 403 on ONE CareStack feed must not roll back the rest.

    Motivating incident: a 403 "Request blocked due to CareStack Security
    Policy" (egress IP not on CareStack's Sync-API allowlist) used to
    propagate, roll back the whole ``async_session`` and report "0 records ·
    failed" even though earlier legs had imported. The accounting leg here
    raises ``CareStackApiError``; the pull must still import the other legs,
    close the run ``partial`` with the blocked feed in ``meta.failed_legs``,
    and never re-raise.
    """
    integration_svc = _integration_service()
    fake_payload = {"client_id": "x", "client_secret": "y"}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()
    # Success legs carry the count attributes ``_carestack_counters`` reads
    # (not just ``model_dump``), so ``succeeded > 0`` and the run is genuinely
    # ``partial`` (some data through, one feed blocked) rather than ``failed``.
    fake_location_svc = MagicMock()
    fake_location_svc.import_locations_from_carestack = AsyncMock(
        return_value=SimpleNamespace(total_seen=2, model_dump=lambda: {"created": 2})
    )
    fake_patient_svc = MagicMock()
    fake_patient_svc.import_recent_patients = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=3,
            unchanged_count=0,
            skipped_count=0,
            model_dump=lambda: {"imported_count": 3},
        )
    )
    fake_appt_svc = MagicMock()
    fake_appt_svc.import_recent_appointments = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=5,
            unchanged_count=0,
            skipped_count=0,
            model_dump=lambda: {"imported_count": 5},
        )
    )
    fake_treatment_svc = MagicMock()
    fake_treatment_svc.import_recent_treatments = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=1,
            unchanged_count=0,
            skipped_count=0,
            model_dump=lambda: {"imported_count": 1},
        )
    )
    fake_invoice_svc = MagicMock()
    fake_invoice_svc.import_recent_invoices = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=0,
            unchanged_count=0,
            skipped_count=0,
            model_dump=lambda: {"imported_count": 0},
        )
    )
    # The blocked leg: CareStack Security Policy 403.
    fake_accounting_tx_svc = MagicMock()
    fake_accounting_tx_svc.import_recent_accounting_transactions = AsyncMock(
        side_effect=CareStackApiError(
            "carestack GET api/v1.0/sync/accounting-transactions failed: 403",
            details={"status": 403, "body": "Request blocked due to CareStack Security Policy!"},
        )
    )
    fake_treatment_plan_svc = MagicMock()
    fake_treatment_plan_svc.import_treatment_plans = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"accepted_count": 0})
    )
    fake_payment_summary_svc = MagicMock()
    fake_payment_summary_svc.import_payment_summary_snapshots = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"snapshot_count": 7})
    )
    fake_payment_summary_svc.import_payment_summary_for_patients = AsyncMock()

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.LocationService",
        return_value=fake_location_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPatientIngestService",
        return_value=fake_patient_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAppointmentIngestService",
        return_value=fake_appt_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentIngestService",
        return_value=fake_treatment_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackInvoiceIngestService",
        return_value=fake_invoice_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAccountingTransactionIngestService",
        return_value=fake_accounting_tx_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPaymentSummaryIngestService",
        return_value=fake_payment_summary_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentPlanIngestService",
        return_value=fake_treatment_plan_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=fake_payload)
        # Must NOT raise — the blocked leg is swallowed, the rest proceed.
        result = await pull_carestack_for_tenant({}, str(_TENANT_UUID))

    # The blocked leg renders as an empty dict; everything else imported.
    assert result["accounting_transactions"] == {}
    assert result["failed_legs"] == ["accounting_transactions"]
    assert result["patients"] == {"imported_count": 3}
    assert result["treatments"] == {"imported_count": 1}
    assert result["payment_summaries"] == {"snapshot_count": 7}
    # Earlier legs still ran; rolling payment-summary sweep still ran.
    fake_patient_svc.import_recent_patients.assert_awaited_once()
    fake_payment_summary_svc.import_payment_summary_snapshots.assert_awaited_once()
    # Targeted refresh is skipped — it depends on the (now None) accounting leg.
    fake_payment_summary_svc.import_payment_summary_for_patients.assert_not_awaited()
    fake_client.close.assert_awaited_once()
    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "partial"
    assert close_call.kwargs["meta"]["failed_legs"] == ["accounting_transactions"]


@pytest.mark.asyncio
async def test_pull_carestack_default_financial_pulls_use_max_pages_20() -> None:
    """ENG-330: ``pull_carestack_for_tenant`` gained a ``max_pages`` kwarg
    threaded into the three watermark-resuming financial feeds. The
    default (20) must keep the scheduled cron tick byte-identical — and
    the bounded patients / appointments feeds stay at their own literal
    ``max_pages=5``, NOT scaled by the new knob.
    """
    integration_svc = _integration_service()
    fake_payload = {"client_id": "x", "client_secret": "y"}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    def _ok(value: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(model_dump=lambda: value)

    fake_location_svc = MagicMock()
    fake_location_svc.import_locations_from_carestack = AsyncMock(
        return_value=_ok({"created": 0})
    )
    fake_patient_svc = MagicMock()
    fake_patient_svc.import_recent_patients = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_appt_svc = MagicMock()
    fake_appt_svc.import_recent_appointments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_treatment_svc = MagicMock()
    fake_treatment_svc.import_recent_treatments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_invoice_svc = MagicMock()
    fake_invoice_svc.import_recent_invoices = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_accounting_tx_svc = MagicMock()
    fake_accounting_tx_svc.import_recent_accounting_transactions = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {"imported_count": 0}, patient_ids=[]
        )
    )
    fake_treatment_plan_svc = MagicMock()
    fake_treatment_plan_svc.import_treatment_plans = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"accepted_count": 0})
    )
    fake_payment_summary_svc = MagicMock()
    fake_payment_summary_svc.import_payment_summary_snapshots = AsyncMock(
        return_value=_ok({"snapshot_count": 0})
    )
    fake_payment_summary_svc.import_payment_summary_for_patients = AsyncMock()

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.LocationService",
        return_value=fake_location_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPatientIngestService",
        return_value=fake_patient_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAppointmentIngestService",
        return_value=fake_appt_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentIngestService",
        return_value=fake_treatment_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackInvoiceIngestService",
        return_value=fake_invoice_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAccountingTransactionIngestService",
        return_value=fake_accounting_tx_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPaymentSummaryIngestService",
        return_value=fake_payment_summary_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentPlanIngestService",
        return_value=fake_treatment_plan_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=fake_payload)
        # No max_pages arg → default. This is the scheduled-cron call site.
        await pull_carestack_for_tenant({}, str(_TENANT_UUID))

    # The three financial feeds default to max_pages=20.
    assert (
        fake_treatment_svc.import_recent_treatments.await_args.kwargs["max_pages"] == 20
    )
    assert (
        fake_invoice_svc.import_recent_invoices.await_args.kwargs["max_pages"] == 20
    )
    assert (
        fake_accounting_tx_svc.import_recent_accounting_transactions.await_args.kwargs[
            "max_pages"
        ]
        == 20
    )
    # The bounded feeds keep their own literal (5), unscaled by the knob.
    assert fake_patient_svc.import_recent_patients.await_args.kwargs["max_pages"] == 5
    assert (
        fake_appt_svc.import_recent_appointments.await_args.kwargs["max_pages"] == 5
    )


@pytest.mark.asyncio
async def test_pull_carestack_passes_custom_max_pages_to_financial_feeds() -> None:
    """ENG-330: a caller (the local-dev drain) may raise the page cap; it
    flows ONLY to the three financial feeds, never to patients/appointments.
    """
    integration_svc = _integration_service()
    fake_payload = {"client_id": "x", "client_secret": "y"}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    def _ok(value: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(model_dump=lambda: value)

    fake_location_svc = MagicMock()
    fake_location_svc.import_locations_from_carestack = AsyncMock(
        return_value=_ok({"created": 0})
    )
    fake_patient_svc = MagicMock()
    fake_patient_svc.import_recent_patients = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_appt_svc = MagicMock()
    fake_appt_svc.import_recent_appointments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_treatment_svc = MagicMock()
    fake_treatment_svc.import_recent_treatments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_invoice_svc = MagicMock()
    fake_invoice_svc.import_recent_invoices = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_accounting_tx_svc = MagicMock()
    fake_accounting_tx_svc.import_recent_accounting_transactions = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {"imported_count": 0}, patient_ids=[]
        )
    )
    fake_treatment_plan_svc = MagicMock()
    fake_treatment_plan_svc.import_treatment_plans = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"accepted_count": 0})
    )
    fake_payment_summary_svc = MagicMock()
    fake_payment_summary_svc.import_payment_summary_snapshots = AsyncMock(
        return_value=_ok({"snapshot_count": 0})
    )
    fake_payment_summary_svc.import_payment_summary_for_patients = AsyncMock()

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.LocationService",
        return_value=fake_location_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPatientIngestService",
        return_value=fake_patient_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAppointmentIngestService",
        return_value=fake_appt_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentIngestService",
        return_value=fake_treatment_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackInvoiceIngestService",
        return_value=fake_invoice_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAccountingTransactionIngestService",
        return_value=fake_accounting_tx_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPaymentSummaryIngestService",
        return_value=fake_payment_summary_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentPlanIngestService",
        return_value=fake_treatment_plan_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=fake_payload)
        await pull_carestack_for_tenant({}, str(_TENANT_UUID), max_pages=40)

    assert (
        fake_treatment_svc.import_recent_treatments.await_args.kwargs["max_pages"] == 40
    )
    assert fake_invoice_svc.import_recent_invoices.await_args.kwargs["max_pages"] == 40
    assert (
        fake_accounting_tx_svc.import_recent_accounting_transactions.await_args.kwargs[
            "max_pages"
        ]
        == 40
    )
    # Bounded feeds untouched.
    assert fake_patient_svc.import_recent_patients.await_args.kwargs["max_pages"] == 5
    assert (
        fake_appt_svc.import_recent_appointments.await_args.kwargs["max_pages"] == 5
    )


@pytest.mark.asyncio
async def test_pull_carestack_skips_live_signal_when_no_imported_patient_ids() -> None:
    """ENG-305: when the accounting pull imports nothing, the live-signal
    targeted refresh must NOT fire. The rolling 50-patient sweep still
    runs — it's the safety net for patients whose balance drifted
    without producing a fresh accounting transaction in this window.
    """
    integration_svc = _integration_service()
    fake_payload = {"client_id": "x", "client_secret": "y"}
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    def _ok(value: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(model_dump=lambda: value)

    fake_location_svc = MagicMock()
    fake_location_svc.import_locations_from_carestack = AsyncMock(
        return_value=_ok({"created": 0})
    )
    fake_patient_svc = MagicMock()
    fake_patient_svc.import_recent_patients = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_appt_svc = MagicMock()
    fake_appt_svc.import_recent_appointments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_treatment_svc = MagicMock()
    fake_treatment_svc.import_recent_treatments = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_invoice_svc = MagicMock()
    fake_invoice_svc.import_recent_invoices = AsyncMock(
        return_value=_ok({"imported_count": 0})
    )
    fake_accounting_tx_svc = MagicMock()
    fake_accounting_tx_svc.import_recent_accounting_transactions = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {"imported_count": 0},
            patient_ids=[],
        )
    )
    fake_treatment_plan_svc = MagicMock()
    fake_treatment_plan_svc.import_treatment_plans = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"accepted_count": 0})
    )
    fake_payment_summary_svc = MagicMock()
    fake_payment_summary_svc.import_payment_summary_snapshots = AsyncMock(
        return_value=_ok({"snapshot_count": 0})
    )
    fake_payment_summary_svc.import_payment_summary_for_patients = AsyncMock()

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.LocationService",
        return_value=fake_location_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPatientIngestService",
        return_value=fake_patient_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAppointmentIngestService",
        return_value=fake_appt_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentIngestService",
        return_value=fake_treatment_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackInvoiceIngestService",
        return_value=fake_invoice_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackAccountingTransactionIngestService",
        return_value=fake_accounting_tx_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackPaymentSummaryIngestService",
        return_value=fake_payment_summary_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.CareStackTreatmentPlanIngestService",
        return_value=fake_treatment_plan_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=fake_payload)
        await pull_carestack_for_tenant({}, str(_TENANT_UUID))

    # Live signal stayed silent — no targeted refresh.
    fake_payment_summary_svc.import_payment_summary_for_patients.assert_not_awaited()
    # Rolling sweep still ran.
    fake_payment_summary_svc.import_payment_summary_snapshots.assert_awaited_once()


# ----------------------------------------------------- Salesforce pull


@pytest.mark.asyncio
async def test_pull_salesforce_returns_skipped_when_no_oauth() -> None:
    integration_svc = _integration_service()
    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(
            side_effect=NoCredentialError(
                "no salesforce credential",
                details={"provider": "salesforce"},
            )
        )
        result = await pull_salesforce_for_tenant({}, str(_TENANT_UUID))

    assert result == {"skipped": "no_credential"}
    integration_svc.close_provider_sync_run.assert_awaited_once()
    assert integration_svc.close_provider_sync_run.await_args.kwargs["status"] == (
        "skipped_credential"
    )


@pytest.mark.asyncio
async def test_pull_salesforce_runs_lead_event_and_task_services() -> None:
    integration_svc = _integration_service()
    fake_client = MagicMock()
    fake_client.close = AsyncMock()
    fake_lead_svc = MagicMock()
    fake_lead_svc.pull_recent_for_sync = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=2,
            skipped_count=1,
            queried_count=3,
            notify_signals=(),
            model_dump=lambda: {
                "imported_count": 2,
                "skipped_count": 1,
                "queried_count": 3,
            },
        )
    )
    fake_event_svc = MagicMock()
    fake_event_svc.import_recent_events = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=7,
            queried_count=8,
            model_dump=lambda: {"imported_count": 7, "queried_count": 8}
        )
    )
    fake_task_svc = MagicMock()
    fake_task_svc.import_recent_tasks = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=4,
            queried_count=4,
            skipped_count=0,
            model_dump=lambda: {
                "imported_count": 4,
                "queried_count": 4,
                "skipped_count": 0,
            },
        )
    )
    # ENG-462: the scheduled SF tick also re-projects tasks first seen before
    # their lead/contact was linked (await call in ingest_scheduled).
    fake_task_svc.reproject_tasks_from_raw = AsyncMock(return_value=None)

    cred_calls: list[tuple[str, str]] = []

    async def _read(_tenant_id: Any, provider: str, kind: str) -> dict[str, Any]:
        cred_calls.append((provider, kind))
        if kind == "oauth_token":
            return {"access_token": "x", "instance_url": "https://example.com"}
        if kind == "api_key":
            return {"client_id": "id", "client_secret": "secret"}
        raise NoCredentialError("unknown", details={"provider": provider, "kind": kind})

    fake_opportunity_svc = MagicMock()
    fake_opportunity_svc.import_recent_opportunities = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=0,
            queried_count=0,
            skipped_count=0,
            model_dump=lambda: {
                "imported_count": 0,
                "queried_count": 0,
                "skipped_count": 0,
            },
        )
    )
    fake_case_svc = MagicMock()
    fake_case_svc.import_recent_cases = AsyncMock(
        return_value=SimpleNamespace(
            imported_count=0,
            queried_count=0,
            skipped_count=0,
            model_dump=lambda: {
                "imported_count": 0,
                "queried_count": 0,
                "skipped_count": 0,
            },
        )
    )

    def _empty_summary() -> SimpleNamespace:
        return SimpleNamespace(
            imported_count=0,
            queried_count=0,
            skipped_count=0,
            unchanged_count=0,
            model_dump=lambda: {
                "imported_count": 0,
                "queried_count": 0,
                "skipped_count": 0,
            },
        )

    fake_contact_svc = MagicMock()
    fake_contact_svc.import_recent_contacts = AsyncMock(
        return_value=_empty_summary()
    )
    fake_account_svc = MagicMock()
    fake_account_svc.import_recent_accounts = AsyncMock(
        return_value=_empty_summary()
    )
    fake_opportunity_history_svc = MagicMock()
    fake_opportunity_history_svc.import_recent_history = AsyncMock(
        return_value=_empty_summary()
    )

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfLeadIngestService",
        return_value=fake_lead_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfEventIngestService",
        return_value=fake_event_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfTaskIngestService",
        return_value=fake_task_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfOpportunityIngestService",
        return_value=fake_opportunity_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfCaseIngestService",
        return_value=fake_case_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfContactIngestService",
        return_value=fake_contact_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfAccountIngestService",
        return_value=fake_account_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfOpportunityHistoryIngestService",
        return_value=fake_opportunity_history_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=_read)
        cred_cls.return_value.upsert = AsyncMock()
        result = await pull_salesforce_for_tenant({}, str(_TENANT_UUID))

    assert result == {
        "leads": {
            "imported_count": 2,
            "skipped_count": 1,
            "queried_count": 3,
        },
        "leads_imported": 2,
        "leads_skipped": 1,
        "events": {"imported_count": 7, "queried_count": 8},
        "tasks": {
            "imported_count": 4,
            "queried_count": 4,
            "skipped_count": 0,
        },
        "opportunities": {
            "imported_count": 0,
            "queried_count": 0,
            "skipped_count": 0,
        },
        "cases": {
            "imported_count": 0,
            "queried_count": 0,
            "skipped_count": 0,
        },
        "contacts": {
            "imported_count": 0,
            "queried_count": 0,
            "skipped_count": 0,
        },
        "accounts": {
            "imported_count": 0,
            "queried_count": 0,
            "skipped_count": 0,
        },
        "opportunity_history": {
            "imported_count": 0,
            "queried_count": 0,
            "skipped_count": 0,
        },
    }
    # Both creds were read (oauth + api_key for refresh path).
    assert ("salesforce", "oauth_token") in cred_calls
    assert ("salesforce", "api_key") in cred_calls
    fake_client.close.assert_awaited_once()
    fake_lead_svc.pull_recent_for_sync.assert_awaited_once_with(_TENANT_ID, limit=50)
    fake_task_svc.import_recent_tasks.assert_awaited_once_with(
        _TENANT_ID, days=7, limit=200
    )
    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "partial"
    assert close_call.kwargs["records_total"] == 15
    assert close_call.kwargs["records_succeeded"] == 13
    assert close_call.kwargs["records_failed"] == 2


@pytest.mark.asyncio
async def test_pull_salesforce_closes_failed_when_provider_errors() -> None:
    integration_svc = _integration_service()
    fake_client = MagicMock()
    fake_client.close = AsyncMock()
    fake_lead_svc = MagicMock()
    fake_lead_svc.pull_recent_for_sync = AsyncMock(side_effect=TimeoutError("timeout"))

    async def _read(_tenant_id: Any, _provider: str, kind: str) -> dict[str, Any]:
        if kind == "oauth_token":
            return {"access_token": "x", "instance_url": "https://example.com"}
        raise NoCredentialError("missing api key", details={"kind": kind})

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfClient.from_credential",
        return_value=fake_client,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfLeadIngestService",
        return_value=fake_lead_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=_read)
        with pytest.raises(TimeoutError):
            await pull_salesforce_for_tenant({}, str(_TENANT_UUID))

    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "failed"
    assert close_call.kwargs["records_failed"] == 1
    fake_client.close.assert_awaited_once()


# ----------------------------------------------------- Fanout cron


@pytest.mark.asyncio
async def test_fanout_returns_no_tenants_summary_when_empty() -> None:
    fake_tenant_svc = MagicMock()
    fake_tenant_svc.list_tenants = AsyncMock(return_value=[])

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "packages.tenant.service.TenantService", return_value=fake_tenant_svc
    ):
        summary = await ingest_scheduled_fanout({})

    assert summary == {
        "tenants": 0,
        "carestack_ok": 0,
        "carestack_skipped": 0,
        "carestack_failed": 0,
        "salesforce_ok": 0,
        "salesforce_skipped": 0,
        "salesforce_failed": 0,
    }


@pytest.mark.asyncio
async def test_fanout_aggregates_per_tenant_outcomes() -> None:
    tenant_a = SimpleNamespace(id=uuid.uuid4())
    tenant_b = SimpleNamespace(id=uuid.uuid4())
    fake_tenant_svc = MagicMock()
    fake_tenant_svc.list_tenants = AsyncMock(return_value=[tenant_a, tenant_b])

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "packages.tenant.service.TenantService", return_value=fake_tenant_svc
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_carestack_for_tenant",
        new=AsyncMock(side_effect=[{"patients": {}}, {"skipped": "no_credential"}]),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_salesforce_for_tenant",
        new=AsyncMock(
            side_effect=[
                {"leads_imported": 1, "events": {}},
                Exception("boom"),
            ]
        ),
    ):
        summary = await ingest_scheduled_fanout({})

    assert summary["tenants"] == 2
    assert summary["carestack_ok"] == 1
    assert summary["carestack_skipped"] == 1
    assert summary["salesforce_ok"] == 1
    assert summary["salesforce_failed"] == 1


@pytest.mark.asyncio
async def test_salesforce_provider_fanout_runs_only_salesforce_pull() -> None:
    tenant_a = SimpleNamespace(id=uuid.uuid4())
    tenant_b = SimpleNamespace(id=uuid.uuid4())
    fake_tenant_svc = MagicMock()
    fake_tenant_svc.list_tenants = AsyncMock(return_value=[tenant_a, tenant_b])

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "packages.tenant.service.TenantService", return_value=fake_tenant_svc
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_salesforce_for_tenant",
        new=AsyncMock(
            side_effect=[
                {"leads_imported": 1, "events": {}},
                {"skipped": "no_credential"},
            ]
        ),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_carestack_for_tenant",
        new=AsyncMock(),
    ) as carestack_mock:
        summary = await pull_salesforce_for_all_tenants({})

    assert summary == {
        "tenants": 2,
        "salesforce_ok": 1,
        "salesforce_skipped": 1,
        "salesforce_failed": 0,
    }
    carestack_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_carestack_provider_fanout_runs_only_carestack_pull() -> None:
    tenant_a = SimpleNamespace(id=uuid.uuid4())
    fake_tenant_svc = MagicMock()
    fake_tenant_svc.list_tenants = AsyncMock(return_value=[tenant_a])

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "packages.tenant.service.TenantService", return_value=fake_tenant_svc
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_carestack_for_tenant",
        new=AsyncMock(side_effect=[Exception("vendor timeout")]),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.pull_salesforce_for_tenant",
        new=AsyncMock(),
    ) as salesforce_mock:
        summary = await pull_carestack_for_all_tenants({})

    assert summary == {
        "tenants": 1,
        "carestack_ok": 0,
        "carestack_skipped": 0,
        "carestack_failed": 1,
    }
    salesforce_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_salesforce_pull_module_runs_provider_fanout() -> None:
    expected = {
        "tenants": 1,
        "salesforce_ok": 1,
        "salesforce_skipped": 0,
        "salesforce_failed": 0,
    }

    with patch("apps.worker.jobs.salesforce_pull.configure_logging") as configure, patch(
        "apps.worker.jobs.salesforce_pull.pull_salesforce_for_all_tenants",
        new=AsyncMock(return_value=expected),
    ) as fanout:
        result = await salesforce_pull.run()

    assert result == expected
    configure.assert_called_once()
    fanout.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_carestack_pull_module_runs_provider_fanout() -> None:
    expected = {
        "tenants": 1,
        "carestack_ok": 1,
        "carestack_skipped": 0,
        "carestack_failed": 0,
    }

    with patch("apps.worker.jobs.carestack_pull.configure_logging") as configure, patch(
        "apps.worker.jobs.carestack_pull.pull_carestack_for_all_tenants",
        new=AsyncMock(return_value=expected),
    ) as fanout:
        result = await carestack_pull.run()

    assert result == expected
    configure.assert_called_once()
    fanout.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_refresh_salesforce_tokens_aggregates_outcomes() -> None:
    tenant_a = SimpleNamespace(id=uuid.uuid4())
    tenant_b = SimpleNamespace(id=uuid.uuid4())
    tenant_c = SimpleNamespace(id=uuid.uuid4())
    fake_tenant_svc = MagicMock()
    fake_tenant_svc.list_tenants = AsyncMock(
        return_value=[tenant_a, tenant_b, tenant_c]
    )

    with patch(
        "apps.worker.jobs.salesforce_token_keepalive.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.TenantService",
        return_value=fake_tenant_svc,
    ), patch(
        "apps.worker.jobs.salesforce_token_keepalive.refresh_salesforce_token_for_tenant",
        new=AsyncMock(
            side_effect=[
                {"refreshed": True},
                {"skipped": "needs_reconnect"},
                Exception("boom"),
            ]
        ),
    ):
        summary = await refresh_salesforce_tokens({})

    assert summary["tenants"] == 3
    assert summary["refreshed"] == 1
    assert summary["needs_reconnect"] == 1
    assert summary["failed"] == 1


# ----------------------------------------------------- ENG-329 metric split


def test_carestack_counters_split_unchanged_out_of_failed() -> None:
    """A run whose CareStack feeds only deduped (idempotent re-pull) must
    report ``succeeded`` (not ``partial``) with zero genuine failures and
    the dedup volume surfaced in the ``unchanged`` bucket.

    Before ENG-329 the dedup rows were counted as ``*_skipped`` and folded
    into ``failed``, so a steady-state pull lied as ~1260 fake failures /
    permanent ``partial``.
    """
    locations = SimpleNamespace(total_seen=2)
    patients = SimpleNamespace(imported_count=0, unchanged_count=0, skipped_count=0)
    appointments = SimpleNamespace(
        imported_count=0, unchanged_count=10, skipped_count=0
    )
    treatments = SimpleNamespace(
        imported_count=0, unchanged_count=500, skipped_count=0
    )
    invoices = SimpleNamespace(imported_count=0, unchanged_count=300, skipped_count=0)
    accounting = SimpleNamespace(
        imported_count=0, unchanged_count=450, skipped_count=0
    )
    payment_summaries = SimpleNamespace(
        snapshot_count=0, skipped_count=0, error_count=0
    )

    counters = _carestack_counters(
        locations,
        patients,
        appointments,
        treatments,
        invoices,
        accounting,
        payment_summaries,
    )

    # location total_seen counts as succeeded; everything else deduped.
    assert counters["succeeded"] == 2
    assert counters["unchanged"] == 10 + 500 + 300 + 450
    assert counters["failed"] == 0
    assert counters["total"] == counters["succeeded"] + counters["unchanged"]
    # With dedup out of failed, the status is succeeded, not partial.
    assert _counter_status(counters["succeeded"], counters["failed"]) == "succeeded"


def test_carestack_counters_genuine_skips_still_fail() -> None:
    """Genuine skips (no source id, unlinked patient, non-payment folio)
    plus payment-summary errors still count as ``failed`` — they are real
    non-imports, not dedup.
    """
    locations = SimpleNamespace(total_seen=0)
    patients = SimpleNamespace(imported_count=1, unchanged_count=0, skipped_count=0)
    appointments = SimpleNamespace(
        imported_count=0, unchanged_count=0, skipped_count=2
    )
    treatments = SimpleNamespace(imported_count=0, unchanged_count=0, skipped_count=0)
    invoices = SimpleNamespace(imported_count=0, unchanged_count=0, skipped_count=0)
    accounting = SimpleNamespace(imported_count=0, unchanged_count=0, skipped_count=3)
    payment_summaries = SimpleNamespace(
        snapshot_count=0, skipped_count=0, error_count=1
    )

    counters = _carestack_counters(
        locations,
        patients,
        appointments,
        treatments,
        invoices,
        accounting,
        payment_summaries,
    )

    assert counters["succeeded"] == 1
    assert counters["unchanged"] == 0
    assert counters["failed"] == 2 + 3 + 1
    assert (
        _counter_status(counters["succeeded"], counters["failed"]) == "partial"
    )


def test_counter_status_unchanged_counts_as_health() -> None:
    """ENG-389: a steady-state guarded run (0 imported, N unchanged) with a
    single benign skip must report ``partial``, not ``failed`` — the
    unchanged bucket proves the pull worked. ``failed`` is reserved for
    runs that produced nothing at all.
    """
    # The exact shape that painted the dev card red: drain pass 2 saw 31
    # unchanged rows, zero imports, one chronically skipped SF task.
    assert _counter_status(0, 1, 31) == "partial"
    # No imports, no unchanged, real skips -> still failed.
    assert _counter_status(0, 1, 0) == "failed"
    # Defaults stay backward-compatible with the 2-arg call sites.
    assert _counter_status(0, 1) == "failed"
    assert _counter_status(5, 1) == "partial"
    assert _counter_status(0, 0, 31) == "succeeded"


# ----------------------------------------------------- ENG-428 schema refresh


class _FakeSchemaSfClient:
    """SF client fake exposing only the schema-refresh surface."""

    def __init__(self) -> None:
        self.closed = False

    async def describe(self, _resource: str) -> dict[str, Any]:
        return {"fields": [{"name": "Id", "type": "id", "custom": False}]}

    async def describe_tooling_fields(self, _resource: str) -> list[dict[str, Any]]:
        return [{"QualifiedApiName": "Id", "DataType": "Id"}]

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_refresh_sf_schemas_records_drift_in_sync_run_meta() -> None:
    integration_svc = _integration_service()
    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.SfClient.from_credential",
        return_value=_FakeSchemaSfClient(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IngestService"
    ) as ingest_cls:
        cred_cls.return_value.read_for = AsyncMock(
            side_effect=[
                {"access_token": "tok", "instance_url": "https://x"},
                {"client_id": "c", "client_secret": "s"},
            ]
        )
        ingest_cls.return_value.sync_object_schema = AsyncMock(
            return_value=SchemaDiffOut(
                provider="salesforce", object_name="Lead", added=["New__c"]
            )
        )
        result = await refresh_salesforce_schemas_for_tenant(
            {}, str(_TENANT_UUID)
        )

    assert result["objects"] == len(SF_FULL_FIDELITY_OBJECTS)
    assert result["drifted"] == len(SF_FULL_FIDELITY_OBJECTS)
    assert result["failed"] == 0
    # Drift is recorded into the sync_run meta.
    close_kwargs = integration_svc.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["status"] == "succeeded"
    assert close_kwargs["records_total"] == len(SF_FULL_FIDELITY_OBJECTS)
    drift = close_kwargs["meta"]["schema_drift"]
    assert set(drift) == set(SF_FULL_FIDELITY_OBJECTS)
    assert drift["Lead"]["added"] == ["New__c"]


@pytest.mark.asyncio
async def test_refresh_sf_schemas_skips_without_credential() -> None:
    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=_integration_service(),
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=NoCredentialError("x"))
        result = await refresh_salesforce_schemas_for_tenant({}, str(_TENANT_UUID))

    assert result == {"skipped": "no_credential"}


@pytest.mark.asyncio
async def test_refresh_carestack_schemas_records_drift() -> None:
    integration_svc = _integration_service()
    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        return_value=_fake_session_cm(),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationService",
        return_value=integration_svc,
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IngestService"
    ) as ingest_cls:
        ingest_cls.return_value.snapshot_observed_schema = AsyncMock(
            return_value=SchemaDiffOut(
                provider="carestack", object_name="patient", added=["newKey"]
            )
        )
        result = await refresh_carestack_schemas_for_tenant({}, str(_TENANT_UUID))

    n = len(_CARESTACK_SCHEMA_OBJECTS)
    assert result == {"objects": n, "drifted": n}
    close_kwargs = integration_svc.close_provider_sync_run.await_args.kwargs
    assert close_kwargs["provider"] == "carestack"
    assert close_kwargs["status"] == "succeeded"
    assert len(close_kwargs["meta"]["schema_drift"]) == n
