"""Unit tests for the ENG-492 marketing historical-backfill job.

Covers:

  1. Chunking math — a 365-day window splits into contiguous, non-overlapping
     30-day windows (oldest first) with a short remainder, and edge cases.
  2. Per-(tenant, provider) credential resolution + graceful skip — no DB row
     and no env account → ``{"skipped": "no_credential"}``, ingest never built.
  3. Idempotency of a re-run — every chunk is pulled via ``import_window`` and
     the job tallies imported/unchanged/skipped across chunks.

The credential service, the provider clients, the ingest services, and
``async_session`` are fully mocked — ZERO real network or DB calls.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.jobs import marketing_backfill as job
from packages.integrations.google_ads import GoogleAdsNotConnectedError
from packages.integrations.google_analytics import GoogleAnalyticsNotConnectedError
from packages.integrations.google_search_console import (
    GoogleSearchConsoleNotConnectedError,
)
from packages.integrations.meta_ads import MetaAdsNotConnectedError

# ----------------------------------------------------------------- chunking math


def test_chunk_windows_365_into_30day_chunks() -> None:
    end = date(2026, 6, 16)
    windows = job.chunk_windows(end_date=end, days=365, chunk_days=30)

    # 365 = 12 * 30 + 5 → 13 windows.
    assert len(windows) == 13
    # Oldest first, last window ends on end_date.
    assert windows[0][0] == end - timedelta(days=364)
    assert windows[-1][1] == end
    # The newest (last) chunk is a full 30 days; the oldest is the 5-day stub.
    assert (windows[-1][1] - windows[-1][0]).days + 1 == 30
    assert (windows[0][1] - windows[0][0]).days + 1 == 5


def test_chunk_windows_are_contiguous_and_cover_exactly_the_window() -> None:
    end = date(2026, 6, 16)
    windows = job.chunk_windows(end_date=end, days=90, chunk_days=14)

    one_day = timedelta(days=1)
    # No gaps, no overlaps.
    for (s_prev, e_prev), (s_next, _e_next) in zip(windows, windows[1:], strict=False):
        assert s_next == e_prev + one_day
        assert s_prev <= e_prev
    # Exact coverage of [end-89, end].
    assert windows[0][0] == end - timedelta(days=89)
    assert windows[-1][1] == end
    total_days = sum((e - s).days + 1 for s, e in windows)
    assert total_days == 90


def test_chunk_windows_exact_multiple_has_no_remainder() -> None:
    windows = job.chunk_windows(end_date=date(2026, 6, 16), days=60, chunk_days=30)
    assert len(windows) == 2
    assert all((e - s).days + 1 == 30 for s, e in windows)


def test_chunk_windows_single_chunk_when_window_fits() -> None:
    windows = job.chunk_windows(end_date=date(2026, 6, 16), days=7, chunk_days=30)
    assert windows == [(date(2026, 6, 10), date(2026, 6, 16))]


def test_chunk_windows_rejects_bad_args() -> None:
    with pytest.raises(ValueError):
        job.chunk_windows(end_date=date(2026, 6, 16), days=0, chunk_days=30)
    with pytest.raises(ValueError):
        job.chunk_windows(end_date=date(2026, 6, 16), days=30, chunk_days=0)


# ----------------------------------------------------------------- helpers


def _fake_session_cm(session: MagicMock) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    return _cm


def _cred_svc(*, payload: dict | None, raises: Exception | None = None) -> MagicMock:
    svc = MagicMock()
    if raises is not None:
        svc.read_for = AsyncMock(side_effect=raises)
    else:
        svc.read_for = AsyncMock(return_value=payload)
    return svc


# (provider key, client attr on the job module, not-connected error)
_PROVIDERS = [
    ("google_ads", "GoogleAdsClient", GoogleAdsNotConnectedError),
    ("meta_ads", "MetaAdsClient", MetaAdsNotConnectedError),
    ("ga4", "GoogleAnalyticsClient", GoogleAnalyticsNotConnectedError),
    ("gsc", "GoogleSearchConsoleClient", GoogleSearchConsoleNotConnectedError),
]


# ----------------------------------------------------------------- graceful skip


@pytest.mark.parametrize("provider,client_attr,err", _PROVIDERS)
@pytest.mark.asyncio
async def test_skip_when_no_db_credential_and_no_env(
    provider: str, client_attr: str, err: type[Exception]
) -> None:
    """No DB row AND no env (from_env raises NotConnected) → graceful skip; no
    ingest service is built and no chunk session is opened."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    cred_svc = _cred_svc(payload=None, raises=job.NoCredentialError("none"))

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, client_attr) as client_cls, patch.object(
        job, "_import_chunk"
    ) as import_chunk:
        client_cls.from_env.side_effect = err("missing env", details={})
        result = await job.backfill_provider_for_tenant(
            {}, tenant_id, provider, days=90, chunk_days=30
        )

    assert result == {"skipped": "no_credential"}
    import_chunk.assert_not_called()
    # Credential read targeted the right provider_kind + api_key kind.
    cred_svc.read_for.assert_awaited_once()
    assert cred_svc.read_for.await_args.args[1] == job._PROVIDER_KIND[provider]
    assert cred_svc.read_for.await_args.args[2] == "api_key"


# ----------------------------------------------------------------- db preferred


@pytest.mark.asyncio
async def test_db_credential_preferred_drives_every_chunk() -> None:
    """A DB credential builds the client via ``from_credential`` (never env), and
    every window chunk is pulled via ``import_window``; counts are tallied."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    cred_svc = _cred_svc(payload={"client_id": "x"})

    built_client = MagicMock()
    built_client.close = AsyncMock()

    # Each chunk reports 1 imported / 1 unchanged / 0 skipped.
    chunk_counts = {"imported": 1, "unchanged": 1, "skipped": 0}

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, "GoogleAdsClient") as client_cls, patch.object(
        job, "_import_chunk", new=AsyncMock(return_value=dict(chunk_counts))
    ) as import_chunk:
        client_cls.from_credential.return_value = built_client
        result = await job.backfill_provider_for_tenant(
            {}, tenant_id, "google_ads", days=90, chunk_days=30
        )

    client_cls.from_credential.assert_called_with({"client_id": "x"})
    client_cls.from_env.assert_not_called()

    # 90 days / 30 → 3 chunks; each pulled once.
    assert result["chunks"] == 3
    assert result["chunks_ok"] == 3
    assert result["chunks_failed"] == 0
    assert import_chunk.await_count == 3
    assert result["imported"] == 3
    assert result["unchanged"] == 3
    assert result["skipped"] == 0
    # Probe client + one client per chunk are all closed (4 total).
    assert built_client.close.await_count == 4


@pytest.mark.asyncio
async def test_rerun_is_idempotent_all_unchanged() -> None:
    """A second run over already-loaded history captures nothing: every chunk
    comes back all-``unchanged`` and the job reports zero imported."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    cred_svc = _cred_svc(payload={"client_id": "x"})

    built_client = MagicMock()
    built_client.close = AsyncMock()

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, "GoogleAdsClient") as client_cls, patch.object(
        job,
        "_import_chunk",
        new=AsyncMock(return_value={"imported": 0, "unchanged": 5, "skipped": 0}),
    ):
        client_cls.from_credential.return_value = built_client
        result = await job.backfill_provider_for_tenant(
            {}, tenant_id, "google_ads", days=60, chunk_days=30
        )

    assert result["imported"] == 0
    assert result["unchanged"] == 10  # 2 chunks * 5
    assert result["chunks_failed"] == 0


@pytest.mark.asyncio
async def test_one_failing_chunk_does_not_abort_the_rest() -> None:
    """A chunk that raises is logged + counted failed; the remaining chunks
    still run (idempotent re-run can pick the failed one up later)."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    cred_svc = _cred_svc(payload={"client_id": "x"})
    built_client = MagicMock()
    built_client.close = AsyncMock()

    calls = {"n": 0}

    async def _flaky(*_a: Any, **_k: Any) -> dict[str, int]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return {"imported": 1, "unchanged": 0, "skipped": 0}

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, "GoogleAdsClient") as client_cls, patch.object(
        job, "_import_chunk", new=_flaky
    ):
        client_cls.from_credential.return_value = built_client
        result = await job.backfill_provider_for_tenant(
            {}, tenant_id, "google_ads", days=90, chunk_days=30
        )

    assert result["chunks"] == 3
    assert result["chunks_ok"] == 2
    assert result["chunks_failed"] == 1
    assert result["imported"] == 2


@pytest.mark.asyncio
async def test_gsc_no_verified_site_skips_provider() -> None:
    """A GSC token with no verified site raises NotConnected inside the chunk
    pull → the whole provider leg is a skip, not a failure."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    cred_svc = _cred_svc(payload={"client_id": "x"})
    built_client = MagicMock()
    built_client.close = AsyncMock()

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, "GoogleSearchConsoleClient") as client_cls, patch.object(
        job,
        "_import_chunk",
        new=AsyncMock(side_effect=GoogleSearchConsoleNotConnectedError("no site")),
    ):
        client_cls.from_credential.return_value = built_client
        result = await job.backfill_provider_for_tenant(
            {}, tenant_id, "gsc", days=60, chunk_days=30
        )

    assert result == {"skipped": "no_site"}


# ----------------------------------------------------------------- fanout


@pytest.mark.asyncio
async def test_run_fans_out_over_tenants_and_providers() -> None:
    """``run`` iterates every tenant and every selected provider, wrapping each
    leg so one failure never crashes the sweep."""
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    tenant_rows = [MagicMock(id=t1), MagicMock(id=t2)]
    tenant_svc = MagicMock()
    tenant_svc.list_tenants = AsyncMock(return_value=tenant_rows)

    session = MagicMock()

    with patch.object(job, "async_session", _fake_session_cm(session)), patch(
        "packages.tenant.service.TenantService", return_value=tenant_svc
    ), patch.object(
        job,
        "backfill_provider_for_tenant",
        new=AsyncMock(return_value={"provider": "x", "imported": 0}),
    ) as bf:
        results = await job.run(days=30, chunk_days=30, providers=("google_ads", "ga4"))

    assert len(results) == 2
    # 2 tenants * 2 providers = 4 backfill legs.
    assert bf.await_count == 4
    assert set(results[0].keys()) >= {"tenant_id", "google_ads", "ga4"}


@pytest.mark.asyncio
async def test_run_no_tenants_returns_empty() -> None:
    tenant_svc = MagicMock()
    tenant_svc.list_tenants = AsyncMock(return_value=[])
    session = MagicMock()

    with patch.object(job, "async_session", _fake_session_cm(session)), patch(
        "packages.tenant.service.TenantService", return_value=tenant_svc
    ):
        results = await job.run(days=30, chunk_days=30)

    assert results == []
