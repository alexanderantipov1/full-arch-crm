"""Tests for ``CatalogService`` (ENG-420).

The service is a thin wrapper around the CareStack
``/api/v1.0/procedure-codes`` endpoint and the repository upsert. These
tests pin the contract:

* empty / non-array response handling,
* the defensive ``max_codes`` cap,
* SQL ``batch_size`` is honoured (so a misbehaving payload doesn't
  exceed Postgres' parameter limit on a single ON CONFLICT statement),
* the service flushes but NEVER commits and NEVER rolls back — the
  caller boundary owns the unit of work,
* repository exceptions propagate so the caller can rollback,
* the resolver passthrough,
* idempotent re-runs against the same payload.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.catalog.service import CatalogService


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    return session


def _stub_client(body: Any) -> MagicMock:
    client = MagicMock()
    client.get = AsyncMock(return_value=body)
    return client


@pytest.mark.asyncio
async def test_sync_empty_response_returns_zeroed_counts() -> None:
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client([])

    out = await svc.sync_procedure_codes_from_carestack(client)

    assert out.imported == 0
    assert out.total_seen == 0
    assert out.error_count == 0
    client.get.assert_awaited_once_with("api/v1.0/procedure-codes")
    # Service must never commit or rollback — caller owns the UoW.
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_non_array_response_returns_zero_and_logs() -> None:
    """A wrapped envelope or 4xx-shaped object must not crash — log +
    return zero so the Cloud Run Job exits cleanly."""
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client({"error": "boom"})

    out = await svc.sync_procedure_codes_from_carestack(client)

    assert out.imported == 0
    assert out.total_seen == 0
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_calls_correct_endpoint() -> None:
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client(
        [{"id": 1, "code": "D0120", "description": "Periodic exam"}]
    )

    await svc.sync_procedure_codes_from_carestack(client)

    # Per docs/integrations/carestack/resources/procedure-codes.md
    client.get.assert_awaited_once_with("api/v1.0/procedure-codes")


@pytest.mark.asyncio
async def test_sync_flushes_but_does_not_commit_or_rollback() -> None:
    """The caller boundary owns the UoW. The service flushes so the
    upsert is visible inside the open transaction, but never commits
    and never rolls back — even on success."""
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client(
        [{"id": 1, "code": "D0120", "description": "Periodic exam"}]
    )

    await svc.sync_procedure_codes_from_carestack(client)

    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_splits_into_sql_batches_of_batch_size() -> None:
    """``batch_size=2`` over 5 rows must produce at least two repo
    upserts so a large catalog doesn't fly through Postgres' 65535
    parameter limit on a single ``ON CONFLICT`` statement."""
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client(
        [
            {"id": i, "code": f"D{i:04d}", "description": f"row {i}"}
            for i in range(1, 6)
        ]
    )

    upsert_calls: list[int] = []

    async def _spy_upsert(rows: list[dict[str, Any]]) -> int:
        upsert_calls.append(len(rows))
        return len(rows)

    svc._repo.upsert_procedure_codes = _spy_upsert  # type: ignore[method-assign]

    out = await svc.sync_procedure_codes_from_carestack(client, batch_size=2)

    assert out.imported == 5
    assert out.total_seen == 5
    # 5 rows / batch 2 = 3 batches of [2, 2, 1].
    assert upsert_calls == [2, 2, 1]
    # Caller owns commit — service never touches it.
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_respects_max_codes_cap() -> None:
    """The defensive cap stops the upsert at ``max_codes`` rows even when
    CareStack returns more."""
    session = _fake_session()
    svc = CatalogService(session)
    client = _stub_client(
        [
            {"id": i, "code": f"D{i:04d}", "description": f"row {i}"}
            for i in range(1, 51)
        ]
    )

    out = await svc.sync_procedure_codes_from_carestack(client, max_codes=10)

    assert out.total_seen == 10
    assert out.imported == 10


@pytest.mark.asyncio
async def test_sync_is_idempotent_on_repeat() -> None:
    """Running the same payload twice with a real (stubbed) repo upsert
    keeps the visible side effects the same per call — the upstream
    contract is ``ON CONFLICT (carestack_code_id) DO UPDATE``."""
    session = _fake_session()
    svc = CatalogService(session)
    body = [
        {
            "id": 117408,
            "code": "D7240",
            "description": "Removal of impacted tooth — completely bony",
            "codeTypeId": 1,
            "cdtCategoryId": 10,
        },
    ]
    client = _stub_client(body)

    first = await svc.sync_procedure_codes_from_carestack(client)
    second = await svc.sync_procedure_codes_from_carestack(client)

    assert first.imported == 1
    assert second.imported == 1
    assert first.error_count == 0
    assert second.error_count == 0


@pytest.mark.asyncio
async def test_sync_propagates_upsert_exception_for_caller_rollback() -> None:
    """A repository failure must escape the service — the caller
    (Cloud Run Job entry point / operator backfill script) owns the
    rollback so partial upserts never persist."""
    session = _fake_session()
    svc = CatalogService(session)
    body = [
        {"id": i, "code": f"D{i:04d}", "description": f"row {i}"}
        for i in range(1, 7)
    ]
    client = _stub_client(body)

    async def _boom_upsert(_rows: list[dict[str, Any]]) -> int:
        raise RuntimeError("simulated DB hiccup")

    svc._repo.upsert_procedure_codes = _boom_upsert  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="simulated DB hiccup"):
        await svc.sync_procedure_codes_from_carestack(client, batch_size=2)

    # The service did not silently rollback or commit on its way out —
    # the caller boundary owns that.
    session.rollback.assert_not_awaited()
    session.commit.assert_not_awaited()


# ---------------------------------------------------------------- ENG-538 by-id sync


class _FakeCareStackError(Exception):
    """CareStack-shaped error: carries a ``details`` dict with ``status``."""

    def __init__(self, status: int) -> None:
        super().__init__(f"carestack {status}")
        self.details = {"status": status}


def _by_id_client(
    mapping: dict[int, dict[str, Any]],
    *,
    errors: dict[int, Exception] | None = None,
    error_then_ok: dict[int, list[Exception]] | None = None,
) -> MagicMock:
    """Stub a client exposing ``get_procedure_code(code_id)``.

    ``mapping`` resolves an id → entry dict. ``errors`` raises for an id.
    ``error_then_ok`` raises the queued exceptions then falls through to
    ``mapping`` (exercises the backoff/retry path).
    """
    errors = errors or {}
    error_then_ok = error_then_ok or {}
    client = MagicMock()

    async def _get(code_id: int) -> dict[str, Any]:
        cid = int(code_id)
        queue = error_then_ok.get(cid)
        if queue:
            raise queue.pop(0)
        if cid in errors:
            raise errors[cid]
        return mapping[cid]

    client.get_procedure_code = AsyncMock(side_effect=_get)
    return client


async def _noop_sleep(_seconds: float) -> None:
    return None


def _service_with_repo(
    *, known: dict[int, tuple[str, str | None]] | None = None
) -> tuple[CatalogService, list[list[dict[str, Any]]]]:
    """Build a service over a fake session with stubbed repo resolve/upsert.

    Returns the service and a capture list of the row-batches passed to
    the upsert so a test can assert exactly which rows were written.
    """
    svc = CatalogService(_fake_session())
    svc._repo.resolve_procedure_codes = AsyncMock(  # type: ignore[method-assign]
        return_value=dict(known or {})
    )
    written: list[list[dict[str, Any]]] = []

    async def _spy_upsert(rows: list[dict[str, Any]]) -> int:
        written.append(list(rows))
        return len(rows)

    svc._repo.upsert_procedure_codes = _spy_upsert  # type: ignore[method-assign]
    return svc, written


@pytest.mark.asyncio
async def test_by_id_sync_upserts_resolved_real_codes() -> None:
    """Each requested id is resolved via the by-id endpoint and upserted;
    all-new ids are reported as drift NEW (ENG-538)."""
    svc, written = _service_with_repo(known={})
    client = _by_id_client(
        {
            6100: {
                "id": 6100,
                "code": "D6010",
                "description": "Surgical placement of implant body",
                "cdtCategoryId": 8,
                "codeTypeId": 1,
            },
            6111: {
                "id": 6111,
                "code": "D6058",
                "description": "Abutment supported porcelain/ceramic crown",
                "cdtCategoryId": 8,
            },
        }
    )

    out = await svc.sync_procedure_codes_by_id(
        client, [6100, 6111], sleep=_noop_sleep
    )

    assert out.requested == 2
    assert out.resolved == 2
    assert out.imported == 2
    assert sorted(out.new_codes) == [6100, 6111]
    assert out.changed == []
    assert out.unresolved == []
    # Both rows reached the upsert.
    flat = [row for batch in written for row in batch]
    assert {r["id"] for r in flat} == {6100, 6111}


@pytest.mark.asyncio
async def test_by_id_sync_detects_changed_code_or_description() -> None:
    """A code whose description moved upstream is surfaced as CHANGED and
    re-written; the unchanged sibling is skipped (so ``updated_at`` stays
    a real last-changed signal)."""
    svc, written = _service_with_repo(
        known={
            6100: ("D6010", "OLD description"),
            6111: ("D6058", "Abutment supported porcelain/ceramic crown"),
        }
    )
    client = _by_id_client(
        {
            6100: {
                "id": 6100,
                "code": "D6010",
                "description": "Surgical placement of implant body",
            },
            6111: {
                "id": 6111,
                "code": "D6058",
                "description": "Abutment supported porcelain/ceramic crown",
            },
        }
    )

    out = await svc.sync_procedure_codes_by_id(
        client, [6100, 6111], sleep=_noop_sleep
    )

    assert out.new_codes == []
    assert [c.carestack_code_id for c in out.changed] == [6100]
    assert out.changed[0].old_description == "OLD description"
    assert out.changed[0].new_description == "Surgical placement of implant body"
    # Only the changed row is written; the unchanged one is skipped.
    flat = [row for batch in written for row in batch]
    assert {r["id"] for r in flat} == {6100}
    assert out.imported == 1


@pytest.mark.asyncio
async def test_by_id_sync_unchanged_rows_are_not_written() -> None:
    """Re-running over a catalog that already matches writes nothing."""
    svc, written = _service_with_repo(
        known={6100: ("D6010", "Surgical placement of implant body")}
    )
    client = _by_id_client(
        {
            6100: {
                "id": 6100,
                "code": "D6010",
                "description": "Surgical placement of implant body",
            }
        }
    )

    out = await svc.sync_procedure_codes_by_id(client, [6100], sleep=_noop_sleep)

    assert out.imported == 0
    assert out.new_codes == []
    assert out.changed == []
    assert written == []


@pytest.mark.asyncio
async def test_by_id_sync_surfaces_unresolved_on_404() -> None:
    """A 404 (code retired upstream) is surfaced as ``unresolved``, not a
    crash, and never written."""
    svc, written = _service_with_repo(known={})
    client = _by_id_client(
        {6100: {"id": 6100, "code": "D6010", "description": "x"}},
        errors={9999: _FakeCareStackError(404)},
    )

    out = await svc.sync_procedure_codes_by_id(
        client, [6100, 9999], sleep=_noop_sleep
    )

    assert out.resolved == 1
    assert out.unresolved == [9999]
    assert out.new_codes == [6100]


@pytest.mark.asyncio
async def test_by_id_sync_retries_on_429_then_succeeds() -> None:
    """A retryable 429 is retried with injected (instant) backoff and then
    resolves."""
    svc, _ = _service_with_repo(known={})
    client = _by_id_client(
        {6100: {"id": 6100, "code": "D6010", "description": "x"}},
        error_then_ok={6100: [_FakeCareStackError(429)]},
    )

    out = await svc.sync_procedure_codes_by_id(
        client, [6100], max_retries=2, sleep=_noop_sleep
    )

    assert out.resolved == 1
    assert out.new_codes == [6100]
    assert client.get_procedure_code.await_count == 2


@pytest.mark.asyncio
async def test_by_id_sync_treats_410_as_unresolved() -> None:
    """410 Gone (code retired upstream) joins 404 as a non-fatal
    ``unresolved`` — never written, never raised (ENG-538)."""
    svc, written = _service_with_repo(known={})
    client = _by_id_client(
        {6100: {"id": 6100, "code": "D6010", "description": "x"}},
        errors={9999: _FakeCareStackError(410)},
    )

    out = await svc.sync_procedure_codes_by_id(
        client, [6100, 9999], sleep=_noop_sleep
    )

    assert out.resolved == 1
    assert out.unresolved == [9999]
    assert out.new_codes == [6100]
    flat = [row for batch in written for row in batch]
    assert {r["id"] for r in flat} == {6100}


@pytest.mark.asyncio
async def test_by_id_sync_propagates_non_carestack_error() -> None:
    """A non-CareStack-shaped error is a real bug — it must propagate so
    the caller rolls back, not be masked as ``unresolved``."""
    svc, _ = _service_with_repo(known={})
    client = MagicMock()
    client.get_procedure_code = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await svc.sync_procedure_codes_by_id(client, [6100], sleep=_noop_sleep)


@pytest.mark.asyncio
async def test_by_id_sync_propagates_401_auth_error() -> None:
    """ENG-538 BLOCKER: a 401 (bad/expired CareStack credential) is an
    auth/config failure — it MUST propagate so the boundary rolls back and
    fails loudly, NOT be masked as ``unresolved`` and committed."""
    svc, written = _service_with_repo(known={})
    client = _by_id_client({}, errors={6100: _FakeCareStackError(401)})

    with pytest.raises(_FakeCareStackError):
        await svc.sync_procedure_codes_by_id(client, [6100], sleep=_noop_sleep)

    # Nothing was written on the way out.
    assert written == []


@pytest.mark.asyncio
async def test_by_id_sync_propagates_403_forbidden() -> None:
    """ENG-538 BLOCKER: a 403 (forbidden / scope/config) propagates too."""
    svc, _ = _service_with_repo(known={})
    client = _by_id_client({}, errors={6100: _FakeCareStackError(403)})

    with pytest.raises(_FakeCareStackError):
        await svc.sync_procedure_codes_by_id(client, [6100], sleep=_noop_sleep)


@pytest.mark.asyncio
async def test_by_id_sync_propagates_400_bad_request() -> None:
    """ENG-538 BLOCKER: a 400 (bad request) is non-retryable and non-missing
    → propagate, do not silently call the code ``unresolved``."""
    svc, _ = _service_with_repo(known={})
    client = _by_id_client({}, errors={6100: _FakeCareStackError(400)})

    with pytest.raises(_FakeCareStackError):
        await svc.sync_procedure_codes_by_id(client, [6100], sleep=_noop_sleep)


@pytest.mark.asyncio
async def test_by_id_sync_propagates_on_503_retry_exhaustion() -> None:
    """ENG-538 BLOCKER: a transient 503 that never clears must RAISE after the
    retries are exhausted — swallowing it as ``unresolved`` would commit an
    incomplete catalog during an upstream outage."""
    svc, _ = _service_with_repo(known={})
    client = _by_id_client({}, errors={6100: _FakeCareStackError(503)})

    with pytest.raises(_FakeCareStackError):
        await svc.sync_procedure_codes_by_id(
            client, [6100], max_retries=2, sleep=_noop_sleep
        )

    # Initial attempt + 2 retries = 3 calls before it gives up and raises.
    assert client.get_procedure_code.await_count == 3


@pytest.mark.asyncio
async def test_ensure_procedure_codes_single_attempt_no_retry_on_503() -> None:
    """ENG-538 CONCERN: the self-fill path (``ensure_procedure_codes``) uses a
    single-attempt / no-throttle policy — a retryable 503 raises after exactly
    ONE call, so it never holds the ingest unit of work through the multi-second
    backoff the standalone backfill uses."""
    svc, _ = _service_with_repo(known={})
    client = _by_id_client({}, errors={6100: _FakeCareStackError(503)})

    with pytest.raises(_FakeCareStackError):
        await svc.ensure_procedure_codes(client, [6100], sleep=_noop_sleep)

    assert client.get_procedure_code.await_count == 1


@pytest.mark.asyncio
async def test_ensure_procedure_codes_only_fetches_missing() -> None:
    """Self-fill resolves ONLY the ids not already in the catalog and
    returns the newly-inserted ids (ENG-538)."""
    svc, _ = _service_with_repo(known={6100: ("D6010", "already known")})
    client = _by_id_client(
        {228501: {"id": 228501, "code": "D6010.A", "description": "Implant All on X"}}
    )

    new_ids = await svc.ensure_procedure_codes(
        client, [6100, 228501], sleep=_noop_sleep
    )

    assert new_ids == [228501]
    # The already-known id is never fetched.
    fetched = {c.args[0] for c in client.get_procedure_code.await_args_list}
    assert fetched == {228501}


@pytest.mark.asyncio
async def test_resolve_procedure_codes_passes_through_to_repo() -> None:
    session = _fake_session()
    svc = CatalogService(session)

    expected = {117408: ("D7240", "Removal of impacted tooth")}
    svc._repo.resolve_procedure_codes = AsyncMock(return_value=expected)  # type: ignore[method-assign]

    out = await svc.resolve_procedure_codes([117408])
    assert out == expected
    svc._repo.resolve_procedure_codes.assert_awaited_once_with([117408])
