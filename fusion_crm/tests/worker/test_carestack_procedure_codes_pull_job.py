"""Unit tests for the ENG-420 CareStack procedure-code Cloud Run Job.

This job is the scheduled refresh entry point. It fans out across every
tenant, skips tenants without a CareStack credential, isolates per-tenant
failures so one bad tenant cannot kill the rest of the run, and — most
importantly — owns the unit of work at the job boundary (the
``CatalogService`` flushes but never commits/rolls back).

CareStack HTTP and the Postgres session are fully mocked; the tests
exercise the orchestration shape only. ZERO real network or DB calls.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.jobs import carestack_procedure_codes_pull as job
from packages.core.exceptions import PlatformError

# ---------------------------------------------------------------- helpers


def _fake_session_cm(session: MagicMock) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    return _cm


def _fresh_session() -> MagicMock:
    """Build a fake AsyncSession with the boundary methods the job
    touches (commit / rollback) wired as AsyncMocks."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


class _Outcome:
    """Stand-in for ``ProcedureCodeByIdSyncOut`` — only the fields the job
    log line reads."""

    def __init__(self, imported: int = 1, resolved: int = 1) -> None:
        self.requested = resolved
        self.resolved = resolved
        self.unresolved: list[int] = []
        self.imported = imported
        self.new_codes: list[int] = []
        self.changed: list[object] = []


def _ingest_stub(code_ids: list[int] | None = None) -> MagicMock:
    """Stub ``IngestService`` exposing only the by-id work-list enumeration."""
    ingest = MagicMock()
    ingest.distinct_treatment_procedure_code_ids = AsyncMock(
        return_value=code_ids if code_ids is not None else [6100, 6111]
    )
    return ingest


# ---------------------------------------------------------------- fanout


@pytest.mark.asyncio
async def test_run_with_no_tenants_returns_empty_summary() -> None:
    """Empty-tenant fanout: zero tenants discovered → the job exits
    cleanly with an all-zero summary and never opens a CareStack
    client."""

    with patch.object(job, "_list_tenant_ids", AsyncMock(return_value=[])):
        summary = await job.run()

    assert summary == {
        "tenants": 0,
        "procedure_codes_ok": 0,
        "procedure_codes_skipped": 0,
        "procedure_codes_failed": 0,
    }


# ---------------------------------------------------------------- credential skip


@pytest.mark.asyncio
async def test_pull_for_tenant_returns_skipped_when_credential_missing() -> None:
    """No CareStack credential for the tenant must yield ``skipped`` so
    the run summary can distinguish "nothing to do" from "failed". The
    CareStack client is NEVER constructed in this leg."""
    session = _fresh_session()
    tenant_id = str(uuid.uuid4())

    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(
        side_effect=job.NoCredentialError(
            "no creds", details={"provider": "carestack"}
        )
    )

    with patch.object(job, "async_session", _fake_session_cm(session)), \
         patch.object(job, "IntegrationCredentialService", return_value=cred_svc), \
         patch.object(job, "CareStackClient") as cs_cls, \
         patch.object(job, "CatalogService") as svc_cls:
        outcome = await job._pull_for_tenant(tenant_id)

    assert outcome == "skipped"
    cs_cls.from_credential.assert_not_called()
    svc_cls.assert_not_called()
    # No upsert ran, so no commit / rollback either.
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_pull_for_tenant_skips_on_platform_error_credential_path() -> None:
    """A ``PlatformError`` from the credential lookup is also a skip —
    same handling as ``NoCredentialError`` because both mean "no usable
    credential right now"."""
    session = _fresh_session()
    tenant_id = str(uuid.uuid4())

    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(
        side_effect=PlatformError("creds locked")
    )

    with patch.object(job, "async_session", _fake_session_cm(session)), \
         patch.object(job, "IntegrationCredentialService", return_value=cred_svc), \
         patch.object(job, "CareStackClient") as cs_cls:
        outcome = await job._pull_for_tenant(tenant_id)

    assert outcome == "skipped"
    cs_cls.from_credential.assert_not_called()


# ---------------------------------------------------------------- commit ownership


@pytest.mark.asyncio
async def test_pull_for_tenant_commits_at_boundary_on_success() -> None:
    """Boundary contract: the JOB commits the unit of work, not the
    service. On success the session must commit exactly once and never
    rollback."""
    session = _fresh_session()
    tenant_id = str(uuid.uuid4())

    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(return_value={"client_id": "x"})

    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    svc = MagicMock()
    svc.sync_procedure_codes_by_id = AsyncMock(
        return_value=_Outcome(imported=7, resolved=7)
    )

    with patch.object(job, "async_session", _fake_session_cm(session)), \
         patch.object(job, "IntegrationCredentialService", return_value=cred_svc), \
         patch.object(job, "IngestService", return_value=_ingest_stub()), \
         patch.object(job, "CareStackClient") as cs_cls, \
         patch.object(job, "CatalogService", return_value=svc):
        cs_cls.from_credential.return_value = cs_client
        outcome = await job._pull_for_tenant(tenant_id)

    assert outcome == "ok"
    svc.sync_procedure_codes_by_id.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    cs_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_pull_for_tenant_rolls_back_when_service_raises() -> None:
    """A repository / service exception must escape the service
    (no swallow-and-continue inside the service) and be caught at the
    job boundary, which rolls the partial upsert back before re-raising.
    The CareStack HTTP client must still close (no connection leak)."""
    session = _fresh_session()
    tenant_id = str(uuid.uuid4())

    cred_svc = MagicMock()
    cred_svc.read_for = AsyncMock(return_value={"client_id": "x"})

    cs_client = MagicMock()
    cs_client.close = AsyncMock()

    svc = MagicMock()
    svc.sync_procedure_codes_by_id = AsyncMock(
        side_effect=RuntimeError("simulated DB hiccup")
    )

    with patch.object(job, "async_session", _fake_session_cm(session)), \
         patch.object(job, "IntegrationCredentialService", return_value=cred_svc), \
         patch.object(job, "IngestService", return_value=_ingest_stub()), \
         patch.object(job, "CareStackClient") as cs_cls, \
         patch.object(job, "CatalogService", return_value=svc):
        cs_cls.from_credential.return_value = cs_client
        with pytest.raises(RuntimeError, match="simulated DB hiccup"):
            await job._pull_for_tenant(tenant_id)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    cs_client.close.assert_awaited_once()


# ---------------------------------------------------------------- exception isolation


@pytest.mark.asyncio
async def test_run_isolates_per_tenant_exceptions() -> None:
    """Per-tenant exception isolation: one tenant raising must not abort
    the run. The summary counts the failure and the other tenants still
    process."""
    tenant_ok = str(uuid.uuid4())
    tenant_bad = str(uuid.uuid4())
    tenant_skip = str(uuid.uuid4())

    async def _fake_pull(tid: str) -> str:
        if tid == tenant_bad:
            raise RuntimeError("simulated boom")
        if tid == tenant_skip:
            return "skipped"
        return "ok"

    with patch.object(
        job,
        "_list_tenant_ids",
        AsyncMock(return_value=[tenant_ok, tenant_bad, tenant_skip]),
    ), patch.object(job, "_pull_for_tenant", _fake_pull):
        summary = await job.run()

    assert summary["tenants"] == 3
    assert summary["procedure_codes_ok"] == 1
    assert summary["procedure_codes_skipped"] == 1
    assert summary["procedure_codes_failed"] == 1


@pytest.mark.asyncio
async def test_pull_procedure_codes_for_all_tenants_calls_run() -> None:
    """The arq-shaped alias must funnel into the same ``run()`` entry
    point so future schedulers see the identical summary shape."""

    with patch.object(
        job,
        "_list_tenant_ids",
        AsyncMock(return_value=[]),
    ):
        summary = await job.pull_procedure_codes_for_all_tenants({})

    assert summary == {
        "tenants": 0,
        "procedure_codes_ok": 0,
        "procedure_codes_skipped": 0,
        "procedure_codes_failed": 0,
    }
