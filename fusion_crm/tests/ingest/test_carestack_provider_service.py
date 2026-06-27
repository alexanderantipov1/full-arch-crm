"""Tests for the CareStack provider ingest service (ENG-308).

The service is a thin wrapper around the CareStack ``/api/v1.0/providers``
endpoint:

* Fetch the flat unpaginated provider array.
* Idempotently upsert into ``ingest.carestack_provider`` via the
  repository.
* Return counts for the operator log.

These tests pin the contract: empty list, batch commits every N,
caller-supplied commit callable so the unit-of-work test can assert
on it, and a cap (``max_providers``) so a runaway response never wraps
the whole transaction.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.carestack_provider_service import (
    CareStackProviderIngestService,
)

_TENANT = TenantId(uuid.uuid4())


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    # The real upsert path calls ``session.execute(stmt)``; tests that
    # don't override ``svc._repo.upsert_providers`` rely on the underlying
    # repo's success path, which requires ``execute`` to be awaitable.
    session.execute = AsyncMock(return_value=MagicMock())
    return session


@pytest.mark.asyncio
async def test_import_providers_empty_response_returns_zeroed_counts() -> None:
    """CareStack returns an empty array — service must not commit and
    return zeroed counts."""
    session = _fake_session()
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(return_value=[])
    svc = CareStackProviderIngestService(session=session, carestack_client=cs_client)

    out = await svc.import_providers(_TENANT)

    assert out.imported == 0
    assert out.total_seen == 0
    assert out.error_count == 0
    cs_client.list_providers.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_providers_commits_every_n() -> None:
    """A flat array of 5 providers with ``commit_every=2`` MUST commit at
    least twice (after rows 2 and 4) so a large response does not wrap
    the entire run in one transaction."""
    session = _fake_session()
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(
        return_value=[
            {"id": 1, "firstName": "A", "lastName": "B"},
            {"id": 2, "firstName": "C", "lastName": "D"},
            {"id": 3, "firstName": "E", "lastName": "F"},
            {"id": 4, "firstName": "G", "lastName": "H"},
            {"id": 5, "firstName": "I", "lastName": "J"},
        ]
    )
    commit = AsyncMock()
    svc = CareStackProviderIngestService(session=session, carestack_client=cs_client)

    out = await svc.import_providers(
        _TENANT, commit_every=2, commit=commit
    )

    assert out.imported == 5
    assert out.total_seen == 5
    assert out.error_count == 0
    # 5 providers, commit_every=2 → 2 mid-run commits (after 2 and 4) +
    # 1 final commit = 3 awaits.
    assert commit.await_count == 3


@pytest.mark.asyncio
async def test_import_providers_caps_at_max_providers() -> None:
    """``max_providers=2`` over a 5-row response MUST persist only 2 and
    return ``total_seen=2``. The cap exists to bound run time when a
    tenant has thousands of providers."""
    session = _fake_session()
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(
        return_value=[{"id": i, "firstName": "x", "lastName": "y"} for i in range(5)]
    )
    repo_calls: list[list[dict[str, Any]]] = []

    async def fake_upsert(tenant_id: TenantId, providers: Any) -> int:
        rows = list(providers)
        repo_calls.append(rows)
        return len(rows)

    svc = CareStackProviderIngestService(session=session, carestack_client=cs_client)
    svc._repo.upsert_providers = fake_upsert  # type: ignore[assignment]

    out = await svc.import_providers(_TENANT, max_providers=2)

    assert out.total_seen == 2
    assert out.imported == 2
    # No call ever saw more than the cap.
    assert all(len(batch) <= 2 for batch in repo_calls)


@pytest.mark.asyncio
async def test_import_providers_isolates_repo_failure_per_batch() -> None:
    """If the repository raises on one batch, the service records the
    error and keeps going on the next batch (so a single poison provider
    never zeroes the whole import)."""
    session = _fake_session()
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(
        return_value=[
            {"id": 1, "firstName": "A", "lastName": "B"},
            {"id": 2, "firstName": "C", "lastName": "D"},
            {"id": 3, "firstName": "E", "lastName": "F"},
            {"id": 4, "firstName": "G", "lastName": "H"},
        ]
    )

    call_count = {"n": 0}

    async def flaky_upsert(tenant_id: TenantId, providers: Any) -> int:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated db hiccup")
        return len(list(providers))

    svc = CareStackProviderIngestService(session=session, carestack_client=cs_client)
    svc._repo.upsert_providers = flaky_upsert  # type: ignore[assignment]

    out = await svc.import_providers(_TENANT, commit_every=2)

    # First batch (rows 1-2) failed, second batch (rows 3-4) succeeded.
    assert out.imported == 2
    assert out.error_count >= 1
    assert out.total_seen == 4


@pytest.mark.asyncio
async def test_import_providers_skips_entries_with_no_id() -> None:
    """Providers without an id are silently dropped — the upsert key is
    ``provider_carestack_id`` so an id-less row is unusable."""
    session = _fake_session()
    cs_client = MagicMock()
    cs_client.list_providers = AsyncMock(
        return_value=[
            {"firstName": "no-id-1"},
            {"id": 7, "firstName": "valid"},
            {"id": None, "firstName": "null-id"},
        ]
    )
    svc = CareStackProviderIngestService(session=session, carestack_client=cs_client)

    out = await svc.import_providers(_TENANT)

    assert out.imported == 1
    assert out.total_seen == 1
