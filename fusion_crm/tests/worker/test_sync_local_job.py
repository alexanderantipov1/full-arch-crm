"""Unit tests for the ENG-330 local-dev drain (``run_local_sync``).

The per-tenant pulls are monkeypatched so no DB / provider HTTP is
touched. We assert that:

- the drain loops a provider until a pass imports 0 rows (caught up),
- a ``{"skipped": ...}`` result short-circuits that leg,
- ``max_passes`` caps a never-caught-up leg,
- the summary aggregates ``total_imported`` / ``caught_up`` correctly,
- CareStack receives ``max_pages`` and Salesforce does not.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from apps.worker.jobs import sync_local_job
from packages.core.exceptions import ValidationError


def _env(imported: int) -> dict[str, Any]:
    """A pull result envelope carrying a single imported_count."""
    return {"treatments": {"imported_count": imported}}


@pytest.mark.asyncio
async def test_drain_loops_until_caught_up(monkeypatch: pytest.MonkeyPatch) -> None:
    counts = iter([5, 3, 0])
    cs_calls: list[dict[str, Any]] = []

    async def _cs(_ctx: dict[str, Any], tenant_id: str, *, max_pages: int) -> dict[str, Any]:
        cs_calls.append({"tenant_id": tenant_id, "max_pages": max_pages})
        return _env(next(counts))

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        return {"skipped": "no_credential"}

    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)
    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["carestack"], max_pages=40, max_passes=10
    )

    assert len(cs_calls) == 3  # 5, 3, then 0 stops the loop
    assert all(c["max_pages"] == 40 for c in cs_calls)
    leg = summary["results"][0]
    assert leg["provider"] == "carestack"
    assert leg["passes"] == 3
    assert leg["imported"] == 8
    assert leg["caught_up"] is True
    assert summary["total_imported"] == 8
    assert summary["caught_up"] is True
    assert isinstance(summary["elapsed_seconds"], float)


@pytest.mark.asyncio
async def test_skipped_leg_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    cs_calls = 0

    async def _cs(_ctx: dict[str, Any], tenant_id: str, *, max_pages: int) -> dict[str, Any]:
        nonlocal cs_calls
        cs_calls += 1
        return {"skipped": "no_credential"}

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        return {"skipped": "no_credential"}

    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)
    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["carestack"], max_passes=5
    )

    # Skipped after exactly one pass — no looping.
    assert cs_calls == 1
    leg = summary["results"][0]
    assert leg["skipped"] == "no_credential"
    assert leg["passes"] == 1
    assert leg["imported"] == 0
    # A skipped leg does not block the top-level caught_up flag.
    assert summary["caught_up"] is True
    assert summary["total_imported"] == 0


@pytest.mark.asyncio
async def test_max_passes_caps_never_caught_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _cs(_ctx: dict[str, Any], tenant_id: str, *, max_pages: int) -> dict[str, Any]:
        return _env(7)  # always imports — never catches up

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        return {"skipped": "no_credential"}

    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)
    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["carestack"], max_passes=4
    )

    leg = summary["results"][0]
    assert leg["passes"] == 4
    assert leg["imported"] == 28
    assert leg["caught_up"] is False
    assert summary["caught_up"] is False


@pytest.mark.asyncio
async def test_salesforce_does_not_receive_max_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sf_calls: list[tuple[Any, ...]] = []

    async def _cs(_ctx: dict[str, Any], tenant_id: str, *, max_pages: int) -> dict[str, Any]:
        return _env(0)

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        # No max_pages kwarg accepted — heterogeneous SF bounding.
        sf_calls.append((tenant_id,))
        return {"leads": {"imported_count": 0}}

    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)
    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["salesforce"], max_pages=40
    )

    assert sf_calls == [("t1",)]
    assert summary["results"][0]["provider"] == "salesforce"
    assert summary["results"][0]["caught_up"] is True


@pytest.mark.asyncio
async def test_defaults_resolve_all_tenants_and_both_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _list() -> list[str]:
        return ["ta", "tb"]

    async def _cs(_ctx: dict[str, Any], tenant_id: str, *, max_pages: int) -> dict[str, Any]:
        return _env(0)

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        return {"leads": {"imported_count": 0}}

    monkeypatch.setattr(sync_local_job, "_list_tenant_ids", _list)
    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)
    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync()

    # 2 tenants x 2 providers = 4 legs.
    assert len(summary["results"]) == 4
    providers = {leg["provider"] for leg in summary["results"]}
    assert providers == {"carestack", "salesforce"}
    tenants = {leg["tenant_id"] for leg in summary["results"]}
    assert tenants == {"ta", "tb"}


# ---------------------------------------------------------- ENG-351 deep mode


@pytest.mark.asyncio
async def test_deep_calls_backfill_once_per_tenant_with_parsed_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """deep=True runs ``backfill_carestack_for_tenant`` ONCE per tenant with
    the parsed ``since``, and the summary carries ``deep: true``."""
    backfill_calls: list[tuple[str, datetime]] = []

    async def _backfill(
        _ctx: dict[str, Any], tenant_id: str, since: datetime
    ) -> dict[str, Any]:
        backfill_calls.append((tenant_id, since))
        return _env(11)

    # Fast path must NOT be used in deep mode.
    async def _cs(
        _ctx: dict[str, Any], tenant_id: str, *, max_pages: int
    ) -> dict[str, Any]:
        raise AssertionError("watermark pull must not run in deep mode")

    monkeypatch.setattr(
        sync_local_job, "backfill_carestack_for_tenant", _backfill
    )
    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1", "t2"],
        providers=["carestack"],
        deep=True,
        since="2026-06-01",
    )

    # Called exactly once per tenant — no pass-loop.
    assert len(backfill_calls) == 2
    assert [c[0] for c in backfill_calls] == ["t1", "t2"]
    # Parsed to an aware UTC datetime at midnight.
    assert backfill_calls[0][1] == datetime(2026, 6, 1, tzinfo=UTC)
    assert all(c[1].tzinfo is not None for c in backfill_calls)

    assert summary["deep"] is True
    assert summary["since"] == datetime(2026, 6, 1, tzinfo=UTC).isoformat()
    assert summary["total_imported"] == 22
    assert all(leg["passes"] == 1 for leg in summary["results"])
    assert summary["caught_up"] is True


@pytest.mark.asyncio
async def test_deep_default_since_is_30_days_ago(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[datetime] = []

    async def _backfill(
        _ctx: dict[str, Any], tenant_id: str, since: datetime
    ) -> dict[str, Any]:
        captured.append(since)
        return _env(0)

    monkeypatch.setattr(
        sync_local_job, "backfill_carestack_for_tenant", _backfill
    )

    before = datetime.now(UTC)
    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["carestack"], deep=True
    )

    assert len(captured) == 1
    delta_days = (before - captured[0]).total_seconds() / 86400
    assert 29.9 < delta_days < 30.1
    assert summary["deep"] is True
    assert summary["since"] is not None


@pytest.mark.asyncio
async def test_deep_skipped_backfill_leg_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _backfill(
        _ctx: dict[str, Any], tenant_id: str, since: datetime
    ) -> dict[str, Any]:
        return {"skipped": "no_credential"}

    monkeypatch.setattr(
        sync_local_job, "backfill_carestack_for_tenant", _backfill
    )

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"],
        providers=["carestack"],
        deep=True,
        since="2026-06-01",
    )

    leg = summary["results"][0]
    assert leg["skipped"] == "no_credential"
    assert leg["imported"] == 0
    assert summary["caught_up"] is True


@pytest.mark.asyncio
async def test_deep_salesforce_uses_normal_pull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Salesforce deep is not implemented — it falls back to its normal pull,
    run once."""
    sf_calls: list[str] = []

    async def _sf(_ctx: dict[str, Any], tenant_id: str) -> dict[str, Any]:
        sf_calls.append(tenant_id)
        return {"leads": {"imported_count": 0}}

    monkeypatch.setattr(sync_local_job, "pull_salesforce_for_tenant", _sf)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"],
        providers=["salesforce"],
        deep=True,
        since="2026-06-01",
    )

    assert sf_calls == ["t1"]
    assert summary["results"][0]["provider"] == "salesforce"
    assert summary["deep"] is True


@pytest.mark.asyncio
async def test_deep_rejects_unparseable_since() -> None:
    with pytest.raises(ValidationError):
        await sync_local_job.run_local_sync(
            tenant_ids=["t1"],
            providers=["carestack"],
            deep=True,
            since="not-a-date",
        )


@pytest.mark.asyncio
async def test_fast_mode_summary_has_deep_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _cs(
        _ctx: dict[str, Any], tenant_id: str, *, max_pages: int
    ) -> dict[str, Any]:
        return _env(0)

    monkeypatch.setattr(sync_local_job, "pull_carestack_for_tenant", _cs)

    summary = await sync_local_job.run_local_sync(
        tenant_ids=["t1"], providers=["carestack"]
    )

    assert summary["deep"] is False
    assert summary["since"] is None
