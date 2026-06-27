"""Unit tests for the ENG-540 treatment-procedure replay script.

The script is a thin orchestration layer over
``CareStackTreatmentIngestService.reproject_treatments_from_raw``: it enumerates
captured treatment-procedure raw_events in resumable batches, re-projects each
batch, and commits per batch. No CareStack feed pull ever happens; the client
is built solely so ENG-538 self-fill can resolve a missing code by id.

* Dry-run is the default — count candidates only, never project or commit.
* ``--apply`` paginates, projects each batch, commits per batch, and advances
  the external-id cursor.
* The script owns the unit of work — a batch error rolls back and re-raises.
* CareStack + DB are fully mocked. ZERO real network or DB calls.
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

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "replay_treatment_procedures.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_replay_treatment_procedures", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


replay = _load_script()

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
        "batch_size": 500,
        "max_batches": 0,
        "start_after": None,
        "since_days": 0,
    }
    base.update(overrides)
    return Namespace(**base)


def _result(imported: int = 0, unchanged: int = 0, skipped: int = 0) -> Any:
    return MagicMock(
        imported_count=imported, unchanged_count=unchanged, skipped_count=skipped
    )


# ---------------------------------------------------------------- argparse


def test_parse_args_defaults_to_dry_run() -> None:
    args = replay._parse_args(["--tenant-id", str(_TENANT_UUID)])
    assert args.apply is False
    assert args.batch_size == 500
    assert args.max_batches == 0
    assert args.start_after is None
    assert args.since_days == 0


def test_parse_args_rejects_bad_batch_size() -> None:
    with pytest.raises(SystemExit):
        replay._parse_args(["--batch-size", "0"])
    with pytest.raises(SystemExit):
        replay._parse_args(["--batch-size", "99999"])


def test_parse_args_rejects_negative_bounds() -> None:
    with pytest.raises(SystemExit):
        replay._parse_args(["--max-batches", "-1"])
    with pytest.raises(SystemExit):
        replay._parse_args(["--since-days", "-1"])


# ---------------------------------------------------------------- dry-run


@pytest.mark.asyncio
async def test_dry_run_counts_candidates_and_never_writes() -> None:
    session_cm = _fake_session_cm()
    ingest = MagicMock()
    ingest.count_distinct_external_ids_by_type = AsyncMock(return_value=42)

    with patch.object(replay, "IngestService", return_value=ingest):
        rc = await replay.run(_args(apply=False), session_factory=lambda: session_cm)

    assert rc == 0
    ingest.count_distinct_external_ids_by_type.assert_awaited_once()
    session_cm.session.commit.assert_not_awaited()


# ---------------------------------------------------------------- apply


@pytest.mark.asyncio
async def test_apply_paginates_projects_and_commits_per_batch() -> None:
    session_cm = _fake_session_cm()

    # Two full pages then an empty page → loop stops.
    page1 = [(uuid.uuid4(), "1001", {"id": 1001}), (uuid.uuid4(), "1002", {"id": 1002})]
    page2 = [(uuid.uuid4(), "1003", {"id": 1003})]
    ingest = MagicMock()
    ingest.list_latest_by_type_paginated = AsyncMock(side_effect=[page1, page2, []])

    svc = MagicMock()
    svc.reproject_treatments_from_raw = AsyncMock(
        side_effect=[_result(imported=2), _result(imported=1)]
    )

    no_cred = replay.NoCredentialError("no creds", details={"provider": "carestack"})
    with patch.object(replay, "IngestService", return_value=ingest), patch.object(
        replay, "CareStackTreatmentIngestService", return_value=svc
    ), patch.object(replay, "IntegrationCredentialService") as cred_cls, patch.object(
        replay, "CareStackClient"
    ) as cs_cls:
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        rc = await replay.run(_args(apply=True), session_factory=lambda: session_cm)

    assert rc == 0
    # No credential → no real CareStack client built (no-pull stand-in used).
    cs_cls.from_credential.assert_not_called()
    # Projected both non-empty pages; committed once per batch.
    assert svc.reproject_treatments_from_raw.await_count == 2
    assert session_cm.session.commit.await_count == 2
    # Cursor advanced to the last external_id of each page.
    first_cursor = ingest.list_latest_by_type_paginated.await_args_list[1].kwargs[
        "after_external_id"
    ]
    assert first_cursor == "1002"


@pytest.mark.asyncio
async def test_apply_rolls_back_and_reraises_on_batch_error() -> None:
    session_cm = _fake_session_cm()
    page1 = [(uuid.uuid4(), "1001", {"id": 1001})]
    ingest = MagicMock()
    ingest.list_latest_by_type_paginated = AsyncMock(return_value=page1)

    svc = MagicMock()
    svc.reproject_treatments_from_raw = AsyncMock(side_effect=RuntimeError("boom"))

    no_cred = replay.NoCredentialError("no creds", details={"provider": "carestack"})
    with patch.object(replay, "IngestService", return_value=ingest), patch.object(
        replay, "CareStackTreatmentIngestService", return_value=svc
    ), patch.object(replay, "IntegrationCredentialService") as cred_cls, patch.object(
        replay, "CareStackClient"
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        with pytest.raises(RuntimeError, match="boom"):
            await replay.run(_args(apply=True), session_factory=lambda: session_cm)

    session_cm.session.rollback.assert_awaited()
    session_cm.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_stops_at_max_batches_with_resume_cursor() -> None:
    session_cm = _fake_session_cm()
    page1 = [(uuid.uuid4(), "1001", {"id": 1001})]
    ingest = MagicMock()
    # Would return forever; max-batches=1 must stop after one batch.
    ingest.list_latest_by_type_paginated = AsyncMock(return_value=page1)

    svc = MagicMock()
    svc.reproject_treatments_from_raw = AsyncMock(return_value=_result(imported=1))

    no_cred = replay.NoCredentialError("no creds", details={"provider": "carestack"})
    with patch.object(replay, "IngestService", return_value=ingest), patch.object(
        replay, "CareStackTreatmentIngestService", return_value=svc
    ), patch.object(replay, "IntegrationCredentialService") as cred_cls, patch.object(
        replay, "CareStackClient"
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=no_cred)
        rc = await replay.run(
            _args(apply=True, max_batches=1), session_factory=lambda: session_cm
        )

    assert rc == 0
    assert svc.reproject_treatments_from_raw.await_count == 1
    assert session_cm.session.commit.await_count == 1
