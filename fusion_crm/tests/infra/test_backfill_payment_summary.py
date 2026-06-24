"""Unit tests for the ENG-305 throttled payment-summary backfill script.

The script is a thin orchestration layer around
``CareStackPaymentSummaryIngestService.import_payment_summary_for_patients``
— it resolves linked CareStack patient_ids, opens a sync_run, and
delegates the sweep. These tests cover the orchestration:

* ``--max-patients`` is honored at the source-link query.
* ``--dry-run`` never touches CareStack OR the ingest service.
* Sleep is injectable so throttle paths complete instantly.
* CareStack is fully mocked. ZERO real network calls.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import uuid
from argparse import Namespace
from contextlib import asynccontextmanager
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load the script as a module without requiring ``infra/`` to be a
# package. ``infra/`` is not part of the editable distribution
# (``pyproject.toml`` includes only ``packages*`` + ``apps*``), so we
# keep the test import surface explicit.
_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "backfill_payment_summary.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_backfill_payment_summary", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_payment_summary = _load_script()

_TENANT_UUID = uuid.uuid4()
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000305")


def _fake_session_cm() -> Any:
    session = MagicMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    cm = _cm()
    # Stash the bare session on the context manager so tests can assert
    # on it after entry without re-opening the CM.
    cm.session = session  # type: ignore[attr-defined]
    return cm


def _link(patient_id: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        source_id=patient_id,
        source_system="carestack",
        source_kind="patient",
        person_uid=uuid.uuid4(),
    )


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "max_patients": 2000,
        "sleep_seconds": 0.5,
        "commit_every": 50,
        "dry_run": False,
        # ENG-307: default to False so the existing tests keep exercising
        # the default ``list_source_links_for_dashboard`` resolver path.
        "only_with_payments": False,
    }
    base.update(overrides)
    return Namespace(**base)


class _SleepRecorder:
    """Async sleep stand-in that records waits without blocking."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


# ---------------------------------------------------------------- argparse


def test_parse_args_defaults_match_spec() -> None:
    args = backfill_payment_summary.parse_args(
        ["--tenant-id", str(_TENANT_UUID)]
    )
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.max_patients == 2000
    assert args.sleep_seconds == 0.5
    assert args.commit_every == 50
    assert args.dry_run is False


def test_parse_args_supports_dry_run_and_overrides() -> None:
    args = backfill_payment_summary.parse_args(
        [
            "--tenant-id",
            str(_TENANT_UUID),
            "--max-patients",
            "100",
            "--sleep-seconds",
            "0.2",
            "--commit-every",
            "10",
            "--dry-run",
        ]
    )
    assert args.max_patients == 100
    assert args.sleep_seconds == 0.2
    assert args.commit_every == 10
    assert args.dry_run is True


def test_parse_args_supports_only_with_payments_flag() -> None:
    """ENG-307: ``--only-with-payments`` defaults False and flips True when
    set; existing flags keep their defaults."""
    default_args = backfill_payment_summary.parse_args(
        ["--tenant-id", str(_TENANT_UUID)]
    )
    assert default_args.only_with_payments is False

    enabled_args = backfill_payment_summary.parse_args(
        ["--tenant-id", str(_TENANT_UUID), "--only-with-payments"]
    )
    assert enabled_args.only_with_payments is True
    assert enabled_args.max_patients == 2000


def test_payment_transaction_codes_match_accounting_service_classifier() -> None:
    """The script's PAYMENT_CODES tuple MUST match the codes the accounting
    ingest service classifies as payment-related (cash IN, allocations,
    deletes, refunds). Drift here would silently re-introduce the
    full-tenant 55,677-patient sweep the ``--only-with-payments`` flag
    exists to prevent.
    """
    from packages.ingest.carestack_accounting_transaction_service import (
        _PAYMENT_CODE_TO_KIND,
        _REFUND_TRANSACTION_CODES,
    )

    expected = frozenset(_PAYMENT_CODE_TO_KIND.keys()) | _REFUND_TRANSACTION_CODES
    assert set(backfill_payment_summary.PAYMENT_TRANSACTION_CODES) == expected


# ---------------------------------------------------------------- main: credential gate


@pytest.mark.asyncio
async def test_main_returns_2_when_carestack_credential_missing() -> None:
    """Missing CareStack credential exits non-zero so a cron wrapper can
    distinguish "nothing to do" from "no creds — needs operator action".
    """
    session_cm = _fake_session_cm()
    no_cred = backfill_payment_summary.NoCredentialError(
        "no creds", details={"provider": "carestack"}
    )

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "CareStackClient"
    ) as cs_client_cls:
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        client_factory = MagicMock()
        rc = await backfill_payment_summary.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 2
    client_factory.assert_not_called()
    cs_client_cls.from_credential.assert_not_called()


# ---------------------------------------------------------------- main: --max-patients cap


@pytest.mark.asyncio
async def test_main_honors_max_patients_at_source_link_query() -> None:
    """``--max-patients=3`` over 10 linked patients must process only 3."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x", "client_secret": "y"}
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link(str(p)) for p in range(2000, 2003)]
    )
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=3, skipped_count=0, error_count=0, patient_count=3
        )
    )
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args(max_patients=3),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    assert rc == 0
    # The cap was forwarded to the source-link query.
    list_call = identity_repo.list_source_links_for_dashboard.await_args
    assert list_call.kwargs["limit"] == 3
    assert list_call.kwargs["source_system"] == "carestack"
    assert list_call.kwargs["source_kind"] == "patient"
    # The sweep saw exactly the 3 patient_ids the repo returned.
    sweep_call = ingest_svc.import_payment_summary_for_patients.await_args
    assert sweep_call.args[1] == ["2000", "2001", "2002"]
    # And the sync_run accounting saw matching counts.
    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call.kwargs["status"] == "succeeded"
    assert close_call.kwargs["records_total"] == 3
    assert close_call.kwargs["records_succeeded"] == 3


# ---------------------------------------------------------------- main: --dry-run


@pytest.mark.asyncio
async def test_main_dry_run_does_not_touch_carestack_or_ingest_service(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--dry-run`` resolves the patient set and prints it. Zero HTTP."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x", "client_secret": "y"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("9001"), _link("9002"), _link(None), _link("   ")]
    )
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock()
    cs_client = MagicMock()
    cs_client.get_payment_summary = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args(dry_run=True),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 0
    # CareStack client was NOT constructed and NOT awaited.
    client_factory.assert_not_called()
    cs_client.get_payment_summary.assert_not_awaited()
    # Ingest sweep stayed silent.
    ingest_svc.import_payment_summary_for_patients.assert_not_awaited()
    # No sync_run is opened — there is nothing to journal.
    integration_svc.open_provider_sync_run.assert_not_awaited()
    # Stdout lists the resolved patient_ids one per line (blanks filtered).
    # ``configure_logging`` is NOT invoked in ``main`` directly, but
    # structlog may be set up by another fixture in the same session;
    # filter to lines that exactly match a resolved patient_id so the
    # assertion is robust to ambient log output.
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    patient_id_lines = [line for line in lines if line in {"9001", "9002"}]
    assert patient_id_lines == ["9001", "9002"]


# ---------------------------------------------------------------- main: sleep injection


@pytest.mark.asyncio
async def test_main_forwards_injected_sleep_to_sweep() -> None:
    """The injected ``sleep`` is forwarded to the underlying sweep so
    throttle + backoff paths complete instantly under test."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("9001"), _link("9002")]
    )
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=2, skipped_count=0, error_count=0, patient_count=2
        )
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    cs_client.close = AsyncMock()
    sleep = _SleepRecorder()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args(sleep_seconds=0.25, commit_every=7),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
            sleep=sleep,
        )

    assert rc == 0
    sweep_call = ingest_svc.import_payment_summary_for_patients.await_args
    assert sweep_call.kwargs["sleep"] is sleep
    assert sweep_call.kwargs["sleep_seconds"] == 0.25
    assert sweep_call.kwargs["commit_every"] == 7
    assert sweep_call.kwargs["commit"] is session_cm.session.commit  # type: ignore[attr-defined]
    cs_client.close.assert_awaited_once()


# ---------------------------------------------------------------- main: empty set


@pytest.mark.asyncio
async def test_main_returns_zero_without_opening_sync_run_when_no_patients() -> None:
    """If the tenant has no usable linked patients, exit successfully
    without opening a sync_run — nothing to journal."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link(None), _link("   ")]
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock()
    integration_svc.close_provider_sync_run = AsyncMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock()
    cs_client_factory = MagicMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=cs_client_factory,
        )

    assert rc == 0
    integration_svc.open_provider_sync_run.assert_not_awaited()
    ingest_svc.import_payment_summary_for_patients.assert_not_awaited()
    cs_client_factory.assert_not_called()


# ---------------------------------------------------------------- main: sweep failure closes sync_run


@pytest.mark.asyncio
async def test_main_closes_sync_run_failed_when_sweep_raises() -> None:
    """An unexpected exception in the sweep must close the sync_run as
    ``failed`` before propagating — never leave a sync_run open."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("9001")]
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    boom = RuntimeError("network exploded")
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(side_effect=boom)
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        with pytest.raises(RuntimeError):
            await backfill_payment_summary.main(
                _args(),
                session_factory=lambda: session_cm,
                client_factory=lambda _payload: cs_client,
            )

    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "failed"
    cs_client.close.assert_awaited_once()


# ---------------------------------------------------------------- ENG-307: --only-with-payments


def _args_with_filter(**overrides: object) -> Namespace:
    """Same as ``_args`` but with ``only_with_payments=True`` by default."""
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "max_patients": 2000,
        "sleep_seconds": 0.5,
        "commit_every": 50,
        "dry_run": False,
        "only_with_payments": True,
    }
    base.update(overrides)
    return Namespace(**base)


@pytest.mark.asyncio
async def test_only_with_payments_invokes_filtered_resolver() -> None:
    """When the flag is set, patient_ids come from
    :meth:`IngestRepository.list_carestack_patients_with_payment_activity`
    AND :meth:`IdentityRepository.list_source_links_for_dashboard` is
    NEVER called. This is the whole reason the flag exists — picking the
    has-payments subset off the default resolver would still walk the
    55,677-patient pool."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    ingest_repo = MagicMock()
    ingest_repo.list_carestack_patients_with_payment_activity = AsyncMock(
        return_value=[_link("9001"), _link("9002")]
    )
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("SHOULD-NOT-BE-USED")]
    )
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=2, skipped_count=0, error_count=0, patient_count=2
        )
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args_with_filter(),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    assert rc == 0
    # Filtered resolver was used, default resolver was NOT consulted.
    ingest_repo.list_carestack_patients_with_payment_activity.assert_awaited_once()
    identity_repo.list_source_links_for_dashboard.assert_not_awaited()
    # The has-payments patient_ids reached the sweep.
    sweep_call = ingest_svc.import_payment_summary_for_patients.await_args
    assert sweep_call.args[1] == ["9001", "9002"]


@pytest.mark.asyncio
async def test_default_path_does_not_call_filtered_resolver() -> None:
    """When the flag is absent, behaviour matches today: the default
    resolver is used and the filtered resolver is never constructed.
    Regressions here would silently change the all-linked sweep into
    a smaller has-payments sweep — a quiet operational behaviour
    change."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("9001")]
    )
    ingest_repo = MagicMock()
    ingest_repo.list_carestack_patients_with_payment_activity = AsyncMock(
        return_value=[_link("SHOULD-NOT-BE-USED")]
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=1, skipped_count=0, error_count=0, patient_count=1
        )
    )
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    assert rc == 0
    identity_repo.list_source_links_for_dashboard.assert_awaited_once()
    ingest_repo.list_carestack_patients_with_payment_activity.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_with_payments_forwards_max_patients_cap_and_codes() -> None:
    """``--max-patients`` is the budget cap for the throttled sweep — the
    filtered resolver MUST honor it. The payment-code allow-list MUST be
    the canonical accounting-service set (typo-resistant).
    """
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    ingest_repo = MagicMock()
    ingest_repo.list_carestack_patients_with_payment_activity = AsyncMock(
        return_value=[_link(str(i)) for i in range(3)]
    )
    identity_repo = MagicMock()
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=3, skipped_count=0, error_count=0, patient_count=3
        )
    )
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args_with_filter(max_patients=3),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    assert rc == 0
    resolver_call = (
        ingest_repo.list_carestack_patients_with_payment_activity.await_args
    )
    assert resolver_call.args[0] == backfill_payment_summary.TenantId(_TENANT_UUID)
    assert resolver_call.kwargs["limit"] == 3
    forwarded_codes = set(resolver_call.kwargs["payment_codes"])
    # The forwarded set must exactly match the canonical accounting-service
    # classifier — no typos, no manual list.
    from packages.ingest.carestack_accounting_transaction_service import (
        _PAYMENT_CODE_TO_KIND,
        _REFUND_TRANSACTION_CODES,
    )

    assert forwarded_codes == set(_PAYMENT_CODE_TO_KIND.keys()) | set(
        _REFUND_TRANSACTION_CODES
    )


@pytest.mark.asyncio
async def test_only_with_payments_dry_run_skips_carestack() -> None:
    """``--dry-run --only-with-payments`` must resolve the filtered
    patient_id set and print it, but never construct the CareStack
    client and never open a sync_run."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    ingest_repo = MagicMock()
    ingest_repo.list_carestack_patients_with_payment_activity = AsyncMock(
        return_value=[_link("9001"), _link("9002")]
    )
    identity_repo = MagicMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock()
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    client_factory = MagicMock(return_value=cs_client)

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_payment_summary.main(
            _args_with_filter(dry_run=True),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 0
    # Filtered resolver was used.
    ingest_repo.list_carestack_patients_with_payment_activity.assert_awaited_once()
    # CareStack stays cold.
    client_factory.assert_not_called()
    integration_svc.open_provider_sync_run.assert_not_awaited()
    ingest_svc.import_payment_summary_for_patients.assert_not_awaited()


@pytest.mark.asyncio
async def test_logs_carry_selector_field_when_filter_active() -> None:
    """The patient-resolution log line MUST include ``selector`` so a
    forensic sweep of the structured logs can tell ``has_payments``
    runs apart from default ``all_linked`` runs.

    We patch the script's structlog logger directly: structlog renders
    differently depending on the test process' configure_logging state,
    and the contract we care about is "the kwarg reaches the logger",
    not how it's serialized downstream."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    ingest_repo = MagicMock()
    ingest_repo.list_carestack_patients_with_payment_activity = AsyncMock(
        return_value=[_link("9001")]
    )
    identity_repo = MagicMock()
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=1, skipped_count=0, error_count=0, patient_count=1
        )
    )
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ), patch.object(backfill_payment_summary, "log") as mocked_log:
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        await backfill_payment_summary.main(
            _args_with_filter(),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    selector_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.kwargs.get("selector") is not None
    ]
    assert selector_calls, (
        "expected at least one log.info call to include selector=; "
        f"got info calls: {mocked_log.info.call_args_list}"
    )
    assert all(
        call.kwargs["selector"] == "has_payments" for call in selector_calls
    ), f"unexpected selector value: {selector_calls}"


@pytest.mark.asyncio
async def test_logs_carry_selector_field_when_default_path() -> None:
    """Default path emits ``selector="all_linked"`` so operators can tell
    the two run shapes apart in log forensics — same kwarg, different
    value."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    identity_repo = MagicMock()
    identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=[_link("9001")]
    )
    ingest_repo = MagicMock()
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    ingest_svc = MagicMock()
    ingest_svc.import_payment_summary_for_patients = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_count=1, skipped_count=0, error_count=0, patient_count=1
        )
    )
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_payment_summary, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_payment_summary, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_payment_summary, "IngestRepository", return_value=ingest_repo
    ), patch.object(
        backfill_payment_summary, "IdentityRepository", return_value=identity_repo
    ), patch.object(
        backfill_payment_summary,
        "CareStackPaymentSummaryIngestService",
        return_value=ingest_svc,
    ), patch.object(backfill_payment_summary, "log") as mocked_log:
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        await backfill_payment_summary.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    selector_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.kwargs.get("selector") is not None
    ]
    assert selector_calls, "default path must still tag logs with selector"
    assert all(
        call.kwargs["selector"] == "all_linked" for call in selector_calls
    ), f"unexpected selector value: {selector_calls}"
