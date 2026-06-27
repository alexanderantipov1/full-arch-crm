"""End-to-end dispatch through a real MattermostAdapter (ENG-435, Block B).

Drives the Block C drain worker against the REAL local Postgres but with
the Mattermost HTTP call stubbed via ``respx``: enqueue an outbox row,
monkeypatch ``resolve_chat_provider`` to return a real
:class:`MattermostAdapter` whose ``httpx.AsyncClient`` traffic is mocked,
drain, and assert the row reaches ``sent`` with the provider message id.

The suite skips cleanly when no local DB is reachable (same pattern as
``test_notification_dispatch``). A live post against a running Mattermost
server is an operator step (ENG-434) and is NOT covered here.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from packages.core.security import Principal, Role
from packages.core.types import TenantId

try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)

_BASE_URL = "https://chat.example.com"
_POSTS_URL = f"{_BASE_URL}/api/v4/posts"
_TOKEN = "bot-token-secret"


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


async def _db_reachable() -> bool:
    from sqlalchemy import text

    from packages.db.session import engine

    try:
        await engine.dispose()
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — DB down / unreachable
        return False


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng435-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-435 Test"},
        )

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            await session.execute(
                text(
                    "DELETE FROM integrations.notification_outbox WHERE tenant_id = :id"
                ),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM audit.access_log WHERE tenant_id = :id"),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
            )


async def test_drain_sends_via_real_mattermost_adapter(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.worker.jobs import notification_dispatch
    from packages.integrations.chat.mattermost import MattermostAdapter
    from packages.integrations.notification_repository import (
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    async def _resolver(tid, kind, session):  # noqa: ANN001
        # Real adapter, real Block C resolver signature; httpx mocked below.
        return MattermostAdapter(_BASE_URL, _TOKEN)

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    # ENG-458: the outbox carries a team-qualified channel reference; the
    # dispatcher resolves team → channel id before posting.
    team_id = "team0fusion0000000000000aa"
    channel_id = "chan0leads00000000000000aa"

    async with async_session() as session:
        svc = NotificationService(session)
        row = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(
                event_type="lead.created",
                channel="fusion/leads",
                provider_kind="mattermost",
                payload={"text": "New lead abc — https://x/leads/abc"},
            ),
            principal=_principal(tenant_id),
        )
        outbox_id = row.id

    with respx.mock(assert_all_called=True) as rx:
        rx.get(f"{_BASE_URL}/api/v4/teams/name/fusion").mock(
            return_value=httpx.Response(200, json={"id": team_id})
        )
        rx.get(
            f"{_BASE_URL}/api/v4/teams/{team_id}/channels/name/leads"
        ).mock(return_value=httpx.Response(200, json={"id": channel_id}))
        route = rx.post(_POSTS_URL).mock(
            return_value=httpx.Response(201, json={"id": "mm-real-1"})
        )
        summary = await notification_dispatch.drain_notification_outbox({})

    assert summary["sent"] == 1, summary
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {_TOKEN}"
    # The post targets the RESOLVED channel id, not the raw "fusion/leads".
    import json as _json

    assert _json.loads(request.content)["channel_id"] == channel_id

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(outbox_id)
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert refreshed.payload.get("provider_message_id") == "mm-real-1"
