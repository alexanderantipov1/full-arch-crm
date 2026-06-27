"""Unit tests for the ENG-308 CareStack providers backfill script.

The script is a thin orchestration layer around
``CareStackProviderIngestService.import_providers`` — it fetches the
provider directory once, opens a sync_run, and delegates the upsert.
These tests cover the orchestration shape (mirroring
``test_backfill_payment_summary.py``):

* ``--dry-run`` never opens a sync_run and never calls the upsert.
* ``--max-providers`` is forwarded to the service cap.
* CareStack is fully mocked. ZERO real network calls.
* Missing CareStack credential exits non-zero so a cron wrapper can
  distinguish "nothing to do" from "no creds — needs operator action".
* A sweep failure closes the sync_run as ``failed``.
* Structured log lines carry a ``selector="providers"`` field so
  forensic sweeps can tell provider runs apart from payment-summary
  runs.
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
    / "backfill_providers.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_backfill_providers", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_providers = _load_script()

_TENANT_UUID = uuid.uuid4()
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000308")


def _fake_session_cm() -> Any:
    """Replicates the helper from ``test_backfill_payment_summary.py``.

    Yields a MagicMock session with an awaitable ``commit`` so the
    sweep's per-batch commit hook completes; the test can also reach
    the session through ``cm.session`` for assertions.
    """
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    cm = _cm()
    cm.session = session  # type: ignore[attr-defined]
    return cm


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "max_providers": 2000,
        "sleep_seconds": 0.5,
        "commit_every": 50,
        "dry_run": False,
    }
    base.update(overrides)
    return Namespace(**base)


# ---------------------------------------------------------------- argparse


def test_parse_args_defaults_match_spec() -> None:
    args = backfill_providers.parse_args(["--tenant-id", str(_TENANT_UUID)])
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.max_providers == 2000
    assert args.sleep_seconds == 0.5
    assert args.commit_every == 50
    assert args.dry_run is False


def test_parse_args_supports_dry_run_and_overrides() -> None:
    args = backfill_providers.parse_args(
        [
            "--tenant-id",
            str(_TENANT_UUID),
            "--max-providers",
            "100",
            "--sleep-seconds",
            "0.2",
            "--commit-every",
            "10",
            "--dry-run",
        ]
    )
    assert args.max_providers == 100
    assert args.sleep_seconds == 0.2
    assert args.commit_every == 10
    assert args.dry_run is True


# ---------------------------------------------------------------- credential gate


@pytest.mark.asyncio
async def test_main_returns_2_when_carestack_credential_missing() -> None:
    """No CareStack credential = exit 2. The cron wrapper uses this to
    distinguish "nothing to do" from "no creds — needs operator action"."""
    session_cm = _fake_session_cm()
    no_cred = backfill_providers.NoCredentialError(
        "no creds", details={"provider": "carestack"}
    )

    with patch.object(
        backfill_providers, "IntegrationCredentialService"
    ) as cred_cls, patch.object(backfill_providers, "CareStackClient") as cs_cls:
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        client_factory = MagicMock()
        rc = await backfill_providers.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 2
    client_factory.assert_not_called()
    cs_cls.from_credential.assert_not_called()


# ---------------------------------------------------------------- --dry-run


@pytest.mark.asyncio
async def test_main_dry_run_does_not_open_sync_run_or_upsert(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--dry-run`` fetches the provider list and prints ids — zero DB
    writes, zero sync_run accounting."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(
        return_value=[
            {"id": 17, "firstName": "Aram", "lastName": "Torosyan"},
            {"id": 99, "firstName": "Beth", "lastName": "Smith"},
            {"id": None, "firstName": "Bad"},
        ]
    )
    cs_client.close = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock()
    provider_svc = MagicMock()
    provider_svc.import_providers = AsyncMock()

    with patch.object(
        backfill_providers, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_providers,
        "IntegrationService",
        return_value=integration_svc,
    ), patch.object(
        backfill_providers,
        "CareStackProviderIngestService",
        return_value=provider_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_providers.main(
            _args(dry_run=True),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 0
    # No sync_run, no upsert.
    integration_svc.open_provider_sync_run.assert_not_awaited()
    provider_svc.import_providers.assert_not_awaited()
    # Stdout listed only the usable provider ids.
    captured = capsys.readouterr()
    id_lines = [line for line in captured.out.splitlines() if line in {"17", "99"}]
    assert id_lines == ["17", "99"]


# ---------------------------------------------------------------- --max-providers cap


@pytest.mark.asyncio
async def test_main_forwards_max_providers_cap_to_service() -> None:
    """``--max-providers=3`` MUST reach the service so a CareStack
    response of 5000 rows never wraps the whole sweep."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    provider_svc = MagicMock()
    provider_svc.import_providers = AsyncMock(
        return_value=SimpleNamespace(imported=3, total_seen=3, error_count=0)
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_providers, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_providers, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_providers,
        "CareStackProviderIngestService",
        return_value=provider_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_providers.main(
            _args(max_providers=3, commit_every=7),
            session_factory=lambda: session_cm,
            client_factory=lambda _payload: cs_client,
        )

    assert rc == 0
    call = provider_svc.import_providers.await_args
    assert call.kwargs["max_providers"] == 3
    assert call.kwargs["commit_every"] == 7
    assert call.kwargs["commit"] is session_cm.session.commit  # type: ignore[attr-defined]
    cs_client.close.assert_awaited_once()
    close = integration_svc.close_provider_sync_run.await_args
    assert close.kwargs["status"] == "succeeded"
    assert close.kwargs["records_total"] == 3
    assert close.kwargs["records_succeeded"] == 3


# ---------------------------------------------------------------- sweep failure


@pytest.mark.asyncio
async def test_main_closes_sync_run_failed_when_sweep_raises() -> None:
    """An unexpected exception in the sweep must close the sync_run as
    ``failed`` before propagating — never leave a sync_run open."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    boom = RuntimeError("network exploded")
    provider_svc = MagicMock()
    provider_svc.import_providers = AsyncMock(side_effect=boom)
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_providers, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_providers, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_providers,
        "CareStackProviderIngestService",
        return_value=provider_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        with pytest.raises(RuntimeError):
            await backfill_providers.main(
                _args(),
                session_factory=lambda: session_cm,
                client_factory=lambda _payload: cs_client,
            )

    close = integration_svc.close_provider_sync_run.await_args
    assert close is not None
    assert close.kwargs["status"] == "failed"
    cs_client.close.assert_awaited_once()


# ---------------------------------------------------------------- selector log field


@pytest.mark.asyncio
async def test_logs_carry_selector_providers_field() -> None:
    """Every info log emitted by the script MUST carry
    ``selector="providers"`` so a forensic log sweep can tell provider
    runs apart from other backfill scripts."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    provider_svc = MagicMock()
    provider_svc.import_providers = AsyncMock(
        return_value=SimpleNamespace(imported=1, total_seen=1, error_count=0)
    )
    integration_svc = MagicMock()
    integration_svc.open_provider_sync_run = AsyncMock(
        return_value=SimpleNamespace(id=_SYNC_RUN_ID)
    )
    integration_svc.close_provider_sync_run = AsyncMock()
    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    with patch.object(
        backfill_providers, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_providers, "IntegrationService", return_value=integration_svc
    ), patch.object(
        backfill_providers,
        "CareStackProviderIngestService",
        return_value=provider_svc,
    ), patch.object(backfill_providers, "log") as mocked_log:
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        await backfill_providers.main(
            _args(),
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
        call.kwargs["selector"] == "providers" for call in selector_calls
    ), f"unexpected selector value: {selector_calls}"
