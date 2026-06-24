"""HTTP-level tests for ``GET /health/ingest`` payment_freshness (ENG-327).

Four endpoint cases:

* **ok** — recent payment_recorded event inside clinic hours.
* **stale** — payment older than the 3h threshold during clinic hours.
* **quiet-hours** — payment older than 3h overnight (status downgrades).
* **unknown** — no payment_recorded events for the tenant.

We freeze ``now`` by monkey-patching the ``datetime`` name in
``apps.api.routers.health`` so the clinic-hours branch is deterministic.
Services are stubbed (``InteractionService`` /
``IntegrationService``) — the repo/service path is exercised by
``tests/interaction/test_repository.py`` against real Postgres, so a
service-level stub here is the right boundary: it lets us assert the
route's classification logic without dragging a live DB into every
table case.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_db,
    get_integration_service,
    get_interaction_service,
    get_tenant_id,
)
from apps.api.routers import health as health_module
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _fake_db() -> MagicMock:
    db = MagicMock()
    # The route's existing "providers" loop calls ``db.execute(stmt)``
    # synchronously-awaited. Stub it to an empty result so the test
    # focuses on payment_freshness without standing up integration_account
    # / sync_run rows.
    rows_result = MagicMock()
    rows_result.all.return_value = []
    db.execute = AsyncMock(return_value=rows_result)
    return db


def _build_app(
    *,
    integration: MagicMock,
    interaction: MagicMock,
) -> FastAPI:
    app = FastAPI()
    app.include_router(health_module.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_tenant_id] = lambda: _TENANT_ID
    app.dependency_overrides[get_integration_service] = lambda: integration
    app.dependency_overrides[get_interaction_service] = lambda: interaction
    return app


def _freeze_now(monkeypatch: pytest.MonkeyPatch, frozen: datetime) -> None:
    """Replace ``datetime`` in the health router so ``datetime.now(UTC)`` returns ``frozen``.

    The router does ``from datetime import datetime`` then calls
    ``datetime.now(UTC)``; we shadow that name with a lightweight stub
    whose ``now`` returns ``frozen``. ``timedelta`` arithmetic in the
    module still uses the real class via ``frozen``'s return value.
    """

    class _FrozenDatetime:
        @staticmethod
        def now(tz: object = None) -> datetime:
            if tz is None:
                return frozen.replace(tzinfo=None)
            return frozen.astimezone(tz)  # type: ignore[arg-type]

    monkeypatch.setattr(health_module, "datetime", _FrozenDatetime)


def _carestack_sync_run(
    *,
    status: str = "succeeded",
    finished_at: datetime | None = None,
) -> list:
    run = SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        started_at=finished_at - timedelta(minutes=5)
        if finished_at is not None
        else None,
        finished_at=finished_at,
    )
    return [(run, "carestack")]


# --- Time anchors ---
# 15:00 UTC on 2026-06-03 == 08:00 America/Los_Angeles (PDT, UTC-7) —
# safely inside the half-open 07:00-19:00 clinic window.
_CLINIC_OPEN_UTC = datetime(2026, 6, 3, 15, 0, tzinfo=UTC)  # 08:00 PDT
# 06:00 UTC == 23:00 PDT previous evening: outside the window.
_OVERNIGHT_UTC = datetime(2026, 6, 3, 6, 0, tzinfo=UTC)  # 23:00 PDT prev day
# 14:00 UTC == 07:00 PDT — the inclusive lower edge of the clinic window.
_CLINIC_OPEN_EDGE_UTC = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
# 02:00 UTC on 2026-06-04 == 19:00 PDT on 2026-06-03 — the exclusive
# upper edge of the clinic window (so `_in_clinic_hours` is False).
_CLINIC_CLOSE_EDGE_UTC = datetime(2026, 6, 4, 2, 0, tzinfo=UTC)


def test_payment_freshness_ok_inside_clinic_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recent payment + recent sync = green on both facets."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)

    last_payment = _CLINIC_OPEN_UTC - timedelta(minutes=30)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=10)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    assert resp.status_code == 200
    body = resp.json()
    freshness = body["payment_freshness"]
    assert freshness["tenant_id"] == str(_TENANT_ID)
    assert freshness["last_accounting_sync"]["status"] == "ok"
    assert freshness["last_accounting_sync"]["last_status"] == "succeeded"
    assert freshness["last_accounting_sync"]["age_seconds"] == 600
    assert freshness["last_payment"]["status"] == "ok"
    assert freshness["last_payment"]["clinic_hours"] is True
    assert freshness["last_payment"]["age_seconds"] == 1800

    interaction.max_event_occurred_at.assert_awaited_once_with(
        _TENANT_ID, kind="payment_recorded"
    )
    integration.list_latest_runs_for_tenant.assert_awaited_once_with(
        _TENANT_ID, provider="carestack", limit=1
    )


def test_payment_freshness_stale_during_clinic_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payment older than 3h while clinic is open → ``stale``."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)

    # 4h stale, well past the 3h threshold.
    last_payment = _CLINIC_OPEN_UTC - timedelta(hours=4)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=20)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    assert resp.status_code == 200
    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "stale"
    assert freshness["last_payment"]["clinic_hours"] is True


def test_payment_freshness_quiet_hours_overnight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payment older than 3h while clinic is closed → ``quiet-hours``."""
    _freeze_now(monkeypatch, _OVERNIGHT_UTC)

    last_payment = _OVERNIGHT_UTC - timedelta(hours=5)
    last_sync_finished = _OVERNIGHT_UTC - timedelta(minutes=30)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    assert resp.status_code == 200
    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "quiet-hours"
    assert freshness["last_payment"]["clinic_hours"] is False


def test_payment_freshness_unknown_when_no_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No payment_recorded events at all → ``unknown``; no sync runs → ``unknown``."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=None)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(return_value=[])

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    assert resp.status_code == 200
    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "unknown"
    assert freshness["last_payment"]["last_payment_at"] is None
    assert freshness["last_payment"]["age_seconds"] is None
    assert freshness["last_payment"]["clinic_hours"] is True
    assert freshness["last_accounting_sync"]["status"] == "unknown"
    assert freshness["last_accounting_sync"]["finished_at"] is None
    assert freshness["last_accounting_sync"]["age_seconds"] is None


def test_payment_freshness_sync_failed_surfaces_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed last sync_run shows ``status=failed`` regardless of recency."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)

    last_payment = _CLINIC_OPEN_UTC - timedelta(minutes=20)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=5)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="failed", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    assert resp.status_code == 200
    freshness = resp.json()["payment_freshness"]
    assert freshness["last_accounting_sync"]["status"] == "failed"
    assert freshness["last_accounting_sync"]["last_status"] == "failed"
    # Data freshness is independent — payment is recent so it stays ok.
    assert freshness["last_payment"]["status"] == "ok"


def test_payment_freshness_block_carries_no_phi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The freshness block must surface only timestamps / counts / status — no PHI."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)

    last_payment = _CLINIC_OPEN_UTC - timedelta(minutes=15)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=5)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    body = resp.text
    # PII strings from `tests/interaction/test_service.py`'s no-PII fixture
    # MUST NOT appear in the freshness output. If any of these surface,
    # someone widened the contract and the test should fail before merge.
    for needle in (
        "John",
        "Smith",
        "john@example.com",
        "+15555551234",
        "1980-01-01",
        "123 Main St",
        "MRN-78901",
        "patient reports back pain",
    ):
        assert needle not in body, f"PHI string leaked into /health/ingest: {needle!r}"


# ---------------------------------------------------------------------------
# Boundary tests for the half-open clinic window and the 3h freshness edge.
# These cases pin behaviour at the exact boundary so a future tweak to
# `_in_clinic_hours` (e.g. inclusive vs exclusive end) or to
# `_PAYMENT_FRESHNESS_THRESHOLD` (e.g. `<` vs `<=`) trips immediately.
# ---------------------------------------------------------------------------


def test_in_clinic_hours_true_at_07_00_local_edge() -> None:
    """The lower edge 07:00 LA (14:00 UTC) must be inside the window."""
    assert health_module._in_clinic_hours(_CLINIC_OPEN_EDGE_UTC) is True


def test_in_clinic_hours_false_at_19_00_local_edge() -> None:
    """The upper edge 19:00 LA (02:00 UTC next day) must be OUTSIDE
    the half-open window (`[7, 19)`)."""
    assert health_module._in_clinic_hours(_CLINIC_CLOSE_EDGE_UTC) is False


def test_payment_freshness_stale_at_07_00_open_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A >3h-old payment at the 07:00 LA edge is `stale` — proves the edge
    is treated as clinic-open."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_EDGE_UTC)
    # 4h old, well past 3h.
    last_payment = _CLINIC_OPEN_EDGE_UTC - timedelta(hours=4)
    last_sync_finished = _CLINIC_OPEN_EDGE_UTC - timedelta(minutes=10)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "stale"
    assert freshness["last_payment"]["clinic_hours"] is True


def test_payment_freshness_quiet_hours_at_19_00_close_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A >3h-old payment at the 19:00 LA close edge is `quiet-hours` —
    proves the upper edge is treated as clinic-closed (half-open)."""
    _freeze_now(monkeypatch, _CLINIC_CLOSE_EDGE_UTC)
    last_payment = _CLINIC_CLOSE_EDGE_UTC - timedelta(hours=4)
    last_sync_finished = _CLINIC_CLOSE_EDGE_UTC - timedelta(minutes=10)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "quiet-hours"
    assert freshness["last_payment"]["clinic_hours"] is False


def test_payment_freshness_ok_exactly_at_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A payment exactly 3h old during clinic hours stays `ok` —
    pins the inclusive edge of `age <= _PAYMENT_FRESHNESS_THRESHOLD`."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)
    last_payment = _CLINIC_OPEN_UTC - timedelta(hours=3)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=5)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "ok"
    assert freshness["last_payment"]["age_seconds"] == 3 * 3600


def test_payment_freshness_stale_one_second_past_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3h + 1s during clinic hours flips to `stale` — pins the exclusive
    side of the threshold."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)
    last_payment = _CLINIC_OPEN_UTC - timedelta(hours=3, seconds=1)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=5)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")

    freshness = resp.json()["payment_freshness"]
    assert freshness["last_payment"]["status"] == "stale"
    assert freshness["last_payment"]["age_seconds"] == 3 * 3600 + 1


def test_health_ingest_logs_payment_freshness_status_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale during clinic hours emits a log line carrying
    ``payment_freshness_status="stale"`` — Cloud Monitoring's log-based
    metric filter in ``infra/scripts/provision_monitoring.sh`` depends on
    that exact key + value."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)
    last_payment = _CLINIC_OPEN_UTC - timedelta(hours=4)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=10)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    mocked_log = MagicMock()
    monkeypatch.setattr(health_module, "log", mocked_log)

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")
    assert resp.status_code == 200

    stale_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.kwargs.get("payment_freshness_status") == "stale"
    ]
    assert stale_calls, (
        "expected /health/ingest to emit a log.info call with "
        f"payment_freshness_status=stale; got: {mocked_log.info.call_args_list}"
    )
    # tenant_id + accounting_sync_status must travel on the same line so
    # the log-based metric reader has a single jsonPayload to filter on.
    sole = stale_calls[0]
    assert sole.kwargs["tenant_id"] == str(_TENANT_ID)
    assert sole.kwargs["accounting_sync_status"] in {
        "ok",
        "stale",
        "failed",
        "unknown",
    }


def test_health_ingest_logs_payment_freshness_status_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Healthy probe still emits the log line — the metric filter selects
    the `="stale"` subset, but the line must be present on every probe so
    the absence-of-line itself is never a silent failure mode."""
    _freeze_now(monkeypatch, _CLINIC_OPEN_UTC)
    last_payment = _CLINIC_OPEN_UTC - timedelta(minutes=30)
    last_sync_finished = _CLINIC_OPEN_UTC - timedelta(minutes=5)

    interaction = MagicMock()
    interaction.max_event_occurred_at = AsyncMock(return_value=last_payment)
    integration = MagicMock()
    integration.list_latest_runs_for_tenant = AsyncMock(
        return_value=_carestack_sync_run(
            status="succeeded", finished_at=last_sync_finished
        )
    )

    mocked_log = MagicMock()
    monkeypatch.setattr(health_module, "log", mocked_log)

    app = _build_app(integration=integration, interaction=interaction)
    with TestClient(app) as client:
        resp = client.get("/health/ingest")
    assert resp.status_code == 200

    ok_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.kwargs.get("payment_freshness_status") == "ok"
    ]
    assert ok_calls, (
        "expected /health/ingest to emit a log.info call with "
        f"payment_freshness_status=ok; got: {mocked_log.info.call_args_list}"
    )
