"""Unit tests for the ENG-420 CareStack procedure-code backfill script.

The script is a thin orchestration layer around
``CatalogService.sync_procedure_codes_from_carestack`` — it loads
credentials, builds the CareStack client, and either prints ids
(``dry-run`` default) or runs the upsert.

* Dry-run is the default: fetch + print ids only, never call
  ``CatalogService``.
* ``--apply`` calls the service with ``max_codes`` + ``batch_size``
  forwarded.
* The script owns the unit of work — successful ``--apply`` commits
  on the session; a service exception rolls back and re-raises.
* Missing CareStack credential → exit code 2 so a cron wrapper can
  distinguish "nothing to do" from "no creds — needs operator
  action".
* CareStack HTTP surface is fully mocked. ZERO real network calls.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import uuid
from argparse import Namespace
from contextlib import asynccontextmanager
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load the script as a module without requiring ``infra/`` to be a
# package (mirrors tests/infra/test_backfill_providers.py).
_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "backfill_procedure_codes.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_backfill_procedure_codes", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_procedure_codes = _load_script()

_TENANT_UUID = uuid.uuid4()


def _fake_session_cm() -> Any:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
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
        "apply": False,
        "max_codes": 20_000,
        "sleep_seconds": 0.1,
    }
    base.update(overrides)
    return Namespace(**base)


def _ingest_stub(code_ids: list[int] | None = None) -> Any:
    """Stub ``IngestService`` exposing only the by-id work-list enumeration."""
    ingest = MagicMock()
    ingest.distinct_treatment_procedure_code_ids = AsyncMock(
        return_value=code_ids if code_ids is not None else [6100, 6111]
    )
    return ingest


class _ByIdOutcome:
    """Stand-in for ``ProcedureCodeByIdSyncOut``."""

    requested = 2
    resolved = 2
    unresolved: list[int] = []
    imported = 2
    new_codes: list[int] = [6100, 6111]
    changed: list[object] = []


# ---------------------------------------------------------------- argparse


def test_parse_args_defaults_to_dry_run() -> None:
    """Default is dry-run; you must pass --apply to write."""
    args = backfill_procedure_codes.parse_args(
        ["--tenant-id", str(_TENANT_UUID)]
    )
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.apply is False
    assert args.max_codes == 20_000
    assert args.sleep_seconds == 0.1


def test_parse_args_supports_apply_and_overrides() -> None:
    args = backfill_procedure_codes.parse_args(
        [
            "--tenant-id",
            str(_TENANT_UUID),
            "--apply",
            "--max-codes",
            "100",
            "--sleep-seconds",
            "0",
        ]
    )
    assert args.apply is True
    assert args.max_codes == 100
    assert args.sleep_seconds == 0


# ---------------------------------------------------------------- credential gate


@pytest.mark.asyncio
async def test_main_returns_2_when_carestack_credential_missing() -> None:
    """No CareStack credential = exit 2."""
    session_cm = _fake_session_cm()
    no_cred = backfill_procedure_codes.NoCredentialError(
        "no creds", details={"provider": "carestack"}
    )

    with patch.object(
        backfill_procedure_codes, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_procedure_codes, "CareStackClient"
    ) as cs_cls:
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        client_factory = MagicMock()
        rc = await backfill_procedure_codes.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 2
    client_factory.assert_not_called()
    cs_cls.from_credential.assert_not_called()


# ---------------------------------------------------------------- dry-run


@pytest.mark.asyncio
async def test_main_dry_run_prints_ids_without_writes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Default mode: enumerate + print work-list ids only — no CareStack
    by-id calls, no service call, no upsert (ENG-538)."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    cs_client = MagicMock()
    cs_client.get_procedure_code = AsyncMock()
    cs_client.close = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)
    catalog_svc = MagicMock()
    catalog_svc.sync_procedure_codes_by_id = AsyncMock()

    with patch.object(
        backfill_procedure_codes, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_procedure_codes,
        "IngestService",
        return_value=_ingest_stub([117408, 1]),
    ), patch.object(
        backfill_procedure_codes,
        "CatalogService",
        return_value=catalog_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_procedure_codes.main(
            _args(),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 0
    catalog_svc.sync_procedure_codes_by_id.assert_not_awaited()
    cs_client.get_procedure_code.assert_not_awaited()
    captured = capsys.readouterr()
    id_lines = [
        line for line in captured.out.splitlines() if line in {"117408", "1"}
    ]
    assert sorted(id_lines) == ["1", "117408"]


# ---------------------------------------------------------------- --apply


@pytest.mark.asyncio
async def test_main_apply_calls_by_id_service_with_worklist() -> None:
    """``--apply`` must enumerate the work-list from ingest and hand it to
    the by-id sync, capping at ``--max-codes`` and forwarding the
    throttle (ENG-538)."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    cs_client = MagicMock()
    cs_client.close = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)

    catalog_svc = MagicMock()
    catalog_svc.sync_procedure_codes_by_id = AsyncMock(return_value=_ByIdOutcome())

    with patch.object(
        backfill_procedure_codes, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_procedure_codes,
        "IngestService",
        return_value=_ingest_stub([6100, 6111, 228501]),
    ), patch.object(
        backfill_procedure_codes,
        "CatalogService",
        return_value=catalog_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        rc = await backfill_procedure_codes.main(
            _args(apply=True, max_codes=2, sleep_seconds=0),
            session_factory=lambda: session_cm,
            client_factory=client_factory,
        )

    assert rc == 0
    catalog_svc.sync_procedure_codes_by_id.assert_awaited_once()
    call = catalog_svc.sync_procedure_codes_by_id.await_args
    # client first positional, work-list second — capped to max_codes=2.
    assert call.args[1] == [6100, 6111]
    assert call.kwargs["sleep_seconds"] == 0
    # Boundary owns the UoW — commit lands on success, no rollback.
    session_cm.session.commit.assert_awaited_once()
    session_cm.session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_apply_rolls_back_when_service_raises() -> None:
    """If the catalog sync raises, the script must roll the partial
    upsert back before re-raising. The service flushes but never
    commits/rolls back — that responsibility lives here."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    cs_client = MagicMock()
    cs_client.close = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)

    catalog_svc = MagicMock()
    catalog_svc.sync_procedure_codes_by_id = AsyncMock(
        side_effect=RuntimeError("simulated DB hiccup")
    )

    with patch.object(
        backfill_procedure_codes, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_procedure_codes,
        "IngestService",
        return_value=_ingest_stub(),
    ), patch.object(
        backfill_procedure_codes,
        "CatalogService",
        return_value=catalog_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        with pytest.raises(RuntimeError, match="simulated DB hiccup"):
            await backfill_procedure_codes.main(
                _args(apply=True),
                session_factory=lambda: session_cm,
                client_factory=client_factory,
            )

    session_cm.session.rollback.assert_awaited_once()
    session_cm.session.commit.assert_not_awaited()
    cs_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_apply_closes_carestack_client_even_on_error() -> None:
    """If the catalog sync raises, the HTTP client must still close so
    we don't leak the httpx connection pool."""
    session_cm = _fake_session_cm()
    payload = {"client_id": "x"}
    cs_client = MagicMock()
    cs_client.close = AsyncMock()
    client_factory = MagicMock(return_value=cs_client)

    catalog_svc = MagicMock()
    catalog_svc.sync_procedure_codes_by_id = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    with patch.object(
        backfill_procedure_codes, "IntegrationCredentialService"
    ) as cred_cls, patch.object(
        backfill_procedure_codes,
        "IngestService",
        return_value=_ingest_stub(),
    ), patch.object(
        backfill_procedure_codes,
        "CatalogService",
        return_value=catalog_svc,
    ):
        cred_cls.return_value.read_for = AsyncMock(return_value=payload)
        with pytest.raises(RuntimeError):
            await backfill_procedure_codes.main(
                _args(apply=True),
                session_factory=lambda: session_cm,
                client_factory=client_factory,
            )

    cs_client.close.assert_awaited_once()
