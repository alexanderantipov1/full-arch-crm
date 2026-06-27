"""Unit tests for the Mattermost inbound mapping worker (ENG-438, Block E).

The job links each captured ``mattermost`` raw event's user to an internal
actor via ``actor_identifier`` (``kind="mattermost_user_id"``) and marks the
row processed. These tests stub the session + services so no DB is touched;
they assert the linking, idempotency on a second pass, and the no-user-id
fast path.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from apps.worker.jobs import chat_inbound_map as job_mod
from packages.core.types import TenantId


class _FakeIngest:
    """Tracks unprocessed rows + processed/error marks."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.processed: list[uuid.UUID] = []
        self.errors: list[tuple[uuid.UUID, str]] = []
        self.list_unprocessed_sources: list[str | None] = []

    async def list_unprocessed(self, tenant_id, limit=100, source=None):  # noqa: ANN001
        # Mirror the real ``IngestService.list_unprocessed`` source filter the
        # worker now passes (``source="mattermost"``); record it so the test
        # can assert the worker scopes the scan.
        self.list_unprocessed_sources.append(source)
        return [
            e
            for e in self._events
            if e.id not in self.processed
            and (source is None or e.source == source)
        ]

    async def mark_processed(self, tenant_id, event_id):  # noqa: ANN001
        self.processed.append(event_id)

    async def mark_error(self, tenant_id, event_id, error):  # noqa: ANN001
        self.errors.append((event_id, error))


class _FakeActors:
    """In-memory actor identifier store; idempotent on (kind, value)."""

    def __init__(self) -> None:
        self.by_identifier: dict[tuple[str, str], Any] = {}
        self.upserts = 0

    async def find_by_identifier(self, tenant_id, kind, value):  # noqa: ANN001
        return self.by_identifier.get((kind, value))

    async def upsert_actor(self, tenant_id, payload):  # noqa: ANN001
        self.upserts += 1
        actor = SimpleNamespace(id=uuid.uuid4(), name=payload.name)
        for ident in payload.identifiers:
            self.by_identifier[(ident.kind, ident.value)] = actor
        return actor


def _raw_event(*, source: str, payload: dict[str, object]) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source=source,
        event_type="mattermost.webhook",
        payload=payload,
    )


def _install(monkeypatch, ingest: _FakeIngest, actors: _FakeActors) -> None:
    tenant_id = uuid.uuid4()

    @asynccontextmanager
    async def _fake_session():
        yield object()

    class _FakeTenantService:
        def __init__(self, session):  # noqa: ANN001
            pass

        async def resolve_default(self, slug):  # noqa: ANN001
            return SimpleNamespace(id=tenant_id)

    monkeypatch.setattr(job_mod, "async_session", _fake_session)
    monkeypatch.setattr(job_mod, "TenantService", _FakeTenantService)
    monkeypatch.setattr(job_mod, "IngestService", lambda session: ingest)
    monkeypatch.setattr(job_mod, "ActorService", lambda session: actors)
    monkeypatch.setattr(
        job_mod, "get_settings", lambda: SimpleNamespace(tenant_default_slug="t")
    )
    return TenantId(tenant_id)


async def test_links_actor_and_marks_processed(monkeypatch) -> None:
    event = _raw_event(
        source="mattermost", payload={"user_id": "mm-user-1", "text": "hi"}
    )
    ingest = _FakeIngest([event])
    actors = _FakeActors()
    _install(monkeypatch, ingest, actors)

    result = await job_mod.map_chat_inbound({})

    assert result["linked"] == 1
    assert event.id in ingest.processed
    assert ("mattermost_user_id", "mm-user-1") in actors.by_identifier
    assert actors.upserts == 1
    # The worker scopes the unprocessed scan to the Mattermost source so the
    # rare chat rows are not starved behind the huge generic ingest backlog.
    assert ingest.list_unprocessed_sources == ["mattermost"]


async def test_idempotent_on_second_pass(monkeypatch) -> None:
    event = _raw_event(
        source="mattermost", payload={"user_id": "mm-user-1", "text": "hi"}
    )
    ingest = _FakeIngest([event])
    actors = _FakeActors()
    _install(monkeypatch, ingest, actors)

    await job_mod.map_chat_inbound({})
    # Second pass: the row is already processed → list_unprocessed returns []
    # and no new actor is created.
    result2 = await job_mod.map_chat_inbound({})

    assert result2["linked"] == 0
    assert actors.upserts == 1  # not incremented


async def test_no_user_id_marks_processed_without_actor(monkeypatch) -> None:
    event = _raw_event(source="mattermost", payload={"text": "no user here"})
    ingest = _FakeIngest([event])
    actors = _FakeActors()
    _install(monkeypatch, ingest, actors)

    result = await job_mod.map_chat_inbound({})

    assert result["skipped_no_user"] == 1
    assert event.id in ingest.processed
    assert actors.upserts == 0


async def test_non_mattermost_rows_are_ignored(monkeypatch) -> None:
    event = _raw_event(source="salesforce", payload={"user_id": "x"})
    ingest = _FakeIngest([event])
    actors = _FakeActors()
    _install(monkeypatch, ingest, actors)

    result = await job_mod.map_chat_inbound({})

    assert result["linked"] == 0
    assert event.id not in ingest.processed
    assert actors.upserts == 0
