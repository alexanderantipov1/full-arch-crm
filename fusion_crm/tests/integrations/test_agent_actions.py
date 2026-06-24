"""Integration tests for the agent human-in-the-loop loop (ENG-440, Block G).

Exercises the chat-side proposal store + the worker-boundary resolution against
the REAL local Postgres so the ``integrations.agent_action_proposal`` table, its
constraints, the cross-schema FKs, and the cross-package execution into
``enrichment.record_annotation`` are verified against the actual DB shape — not
a mock. Only the OUTBOUND ChatProvider is mocked (no live Mattermost). The suite
skips cleanly when no local DB is reachable.

Covered scenarios:

1. ``propose`` persists a pending row AND posts an interactive message whose
   attachment actions carry ``context.token`` (== the stored inbound
   webhook_secret), the ``proposal_ref``, and a ``decision``.
2. Approve via the worker path → proposal ``executed`` AND a real
   ``enrichment.record_annotation`` row with ``source='agent'`` and
   ``author_actor_id`` set.
3. Reject via the worker path → ``rejected``, NO annotation created.
4. Idempotent — two worker passes over the same approve action execute the
   annotation exactly once.
5. Unknown ``proposal_ref`` → safe no-op, raw event still marked processed.
6. Audit rows written for proposed + decided + executed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

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

INBOUND_TOKEN = "block-g-inbound-secret-token"  # noqa: S105 — test fixture, not real


class _FakeProvider:
    """Captures the posted ChatMessage; returns a deterministic message id."""

    def __init__(self, *, ok: bool = True, error: str | None = None) -> None:
        self.posted: list[object] = []
        self.ok = ok
        self.error = error

    async def post(self, message: object):  # noqa: ANN001 — ChatMessage
        from packages.integrations.chat.base import ChatPostResult

        self.posted.append(message)
        return ChatPostResult(
            ok=self.ok,
            provider_message_id="post-123" if self.ok else None,
            error=self.error,
        )


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="staff@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
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


async def _seed_tenant(slug_prefix: str) -> TenantId:
    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"{slug_prefix}-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, "
                "status, created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', "
                "'en-US', 'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-440 Test"},
        )
    return TenantId(tid)


async def _seed_inbound_secret(tenant_id: TenantId) -> None:
    """Store the mattermost/webhook_secret credential the propose path reads."""
    from packages.tenant.credential_service import IntegrationCredentialService

    async with async_session() as session:
        await IntegrationCredentialService(session).upsert(
            tenant_id,
            "mattermost",
            "webhook_secret",
            {"token": INBOUND_TOKEN},
            principal=_principal(tenant_id),
        )
        await session.commit()


async def _cleanup_tenant(tid: TenantId) -> None:
    from sqlalchemy import text

    async with async_session() as session:
        await session.execute(
            text(
                "DELETE FROM integrations.agent_action_proposal WHERE tenant_id = :id"
            ),
            {"id": tid},
        )
        await session.execute(
            text("DELETE FROM enrichment.record_annotation WHERE tenant_id = :id"),
            {"id": tid},
        )
        await session.execute(
            text("DELETE FROM ingest.raw_event WHERE tenant_id = :id"), {"id": tid}
        )
        await session.execute(
            text(
                "DELETE FROM actor.actor_identifier WHERE actor_id IN "
                "(SELECT id FROM actor.actor WHERE tenant_id = :id)"
            ),
            {"id": tid},
        )
        await session.execute(
            text("DELETE FROM actor.actor WHERE tenant_id = :id"), {"id": tid}
        )
        await session.execute(
            text("DELETE FROM tenant.integration_credential WHERE tenant_id = :id"),
            {"id": tid},
        )
        await session.execute(
            text("DELETE FROM audit.access_log WHERE tenant_id = :id"), {"id": tid}
        )
        await session.execute(
            text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
        )


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")
    tid = await _seed_tenant("eng440-test")
    await _seed_inbound_secret(tid)
    try:
        yield tid
    finally:
        await _cleanup_tenant(tid)


async def _capture_action(
    tenant_id: TenantId,
    *,
    proposal_ref: str,
    decision: str,
    user_id: str,
) -> None:
    """Simulate Block E capturing a mattermost.action button click."""
    from packages.ingest.schemas import RawEventIn
    from packages.ingest.service import IngestService
    from packages.integrations.chat.inbound import EVENT_TYPE_ACTION, INBOUND_SOURCE

    async with async_session() as session:
        await IngestService(session).capture(
            tenant_id,
            RawEventIn(
                source=INBOUND_SOURCE,
                event_type=EVENT_TYPE_ACTION,
                external_id=f"trigger-{proposal_ref}",
                received_at=datetime.now(UTC),
                payload={
                    "user_id": user_id,
                    "context": {
                        "token": INBOUND_TOKEN,
                        "proposal_ref": proposal_ref,
                        "decision": decision,
                    },
                },
            ),
        )
        await session.commit()


async def _propose(tenant_id: TenantId, *, subject_id: uuid.UUID) -> tuple[str, object]:
    """Run propose with a fake provider; return (proposal_ref, fake_provider)."""
    from packages.integrations.agent_action_schemas import AgentActionProposalIn
    from packages.integrations.chat import agent_actions as aa_mod
    from packages.integrations.chat.agent_actions import AgentActionService

    fake = _FakeProvider()

    async def _fake_resolver(_tid, _kind, _session):  # noqa: ANN001
        return fake

    original = aa_mod.resolve_chat_provider
    aa_mod.resolve_chat_provider = _fake_resolver  # type: ignore[assignment]
    try:
        async with async_session() as session:
            svc = AgentActionService(session)
            proposal = await svc.propose(
                tenant_id,
                AgentActionProposalIn(
                    channel="town-square",
                    kind="annotation",
                    payload={
                        "subject_type": "person",
                        "subject_id": str(subject_id),
                        "key": "consult_notes",
                        "value": {"text": "Agent suggests a morning follow-up"},
                        "note": "from agent",
                    },
                ),
                principal=_principal(tenant_id),
            )
            ref = proposal.proposal_ref
            await session.commit()
    finally:
        aa_mod.resolve_chat_provider = original  # type: ignore[assignment]
    return ref, fake


# --- 1. propose persists + posts a token-carrying card ------------------


async def test_propose_persists_and_posts_token(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    subject_id = uuid.uuid4()
    ref, fake = await _propose(tenant_id, subject_id=subject_id)

    # Persisted pending row with the provider message id recorded.
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, kind, channel, provider_message_id, payload "
                    "FROM integrations.agent_action_proposal WHERE proposal_ref = :r"
                ),
                {"r": ref},
            )
        ).one()
    assert row.status == "pending"
    assert row.kind == "annotation"
    assert row.channel == "town-square"
    assert row.provider_message_id == "post-123"

    # The posted card's attachment actions carry the inbound token, the ref,
    # and a decision.
    assert len(fake.posted) == 1  # type: ignore[attr-defined]
    message = fake.posted[0]  # type: ignore[attr-defined]
    attachments = message.extra["attachments"]
    actions = attachments[0]["actions"]
    decisions = {a["integration"]["context"]["decision"] for a in actions}
    assert decisions == {"approve", "reject"}
    for action in actions:
        ctx = action["integration"]["context"]
        # The token MUST be the inbound secret so Block E verifies the click.
        assert ctx["token"] == INBOUND_TOKEN
        assert ctx["proposal_ref"] == ref
        assert action["integration"]["url"].endswith(
            "/integrations/chat/mattermost/action"
        )


# --- 1b. propose with a failing provider marks the proposal failed -------


async def test_propose_post_failure_marks_failed(tenant_id: TenantId) -> None:
    """N2: provider ``ok=False`` → proposal ``failed`` (not stranded pending).

    A card that never reached the channel cannot be clicked, so leaving it
    ``pending`` would keep it forever-actionable. The proposal is persisted as
    ``failed`` with the error and an ``agent.action.failed`` audit row.
    """
    from sqlalchemy import text

    from packages.integrations.agent_action_schemas import AgentActionProposalIn
    from packages.integrations.chat import agent_actions as aa_mod
    from packages.integrations.chat.agent_actions import AgentActionService

    fake = _FakeProvider(ok=False, error="channel not found")

    async def _fake_resolver(_tid, _kind, _session):  # noqa: ANN001
        return fake

    original = aa_mod.resolve_chat_provider
    aa_mod.resolve_chat_provider = _fake_resolver  # type: ignore[assignment]
    try:
        async with async_session() as session:
            svc = AgentActionService(session)
            proposal = await svc.propose(
                tenant_id,
                AgentActionProposalIn(
                    channel="town-square",
                    kind="annotation",
                    payload={
                        "subject_type": "person",
                        "subject_id": str(uuid.uuid4()),
                        "key": "consult_notes",
                        "value": {"text": "x"},
                    },
                ),
                principal=_principal(tenant_id),
            )
            ref = proposal.proposal_ref
            await session.commit()
    finally:
        aa_mod.resolve_chat_provider = original  # type: ignore[assignment]

    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, result FROM integrations.agent_action_proposal "
                    "WHERE proposal_ref = :r"
                ),
                {"r": ref},
            )
        ).one()
        assert row.status == "failed"
        assert row.result["error"] == "channel not found"

        actions = (
            await session.execute(
                text(
                    "SELECT action FROM audit.access_log WHERE tenant_id = :tid "
                    "AND action LIKE 'agent.action.%'"
                ),
                {"tid": tenant_id},
            )
        ).scalars().all()
    assert "agent.action.proposed" in actions
    assert "agent.action.failed" in actions


# --- 2. approve via the worker path executes the annotation -------------


async def test_worker_approve_executes_annotation(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from apps.worker.jobs.chat_inbound_map import map_chat_inbound

    subject_id = uuid.uuid4()
    ref, _ = await _propose(tenant_id, subject_id=subject_id)
    await _capture_action(
        tenant_id, proposal_ref=ref, decision="approve", user_id="mm-user-1"
    )

    result = await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)
    assert result["executed"] == 1
    assert result["decisions"] == 1

    async with async_session() as session:
        proposal = (
            await session.execute(
                text(
                    "SELECT status, decided_by_actor_id, result "
                    "FROM integrations.agent_action_proposal WHERE proposal_ref = :r"
                ),
                {"r": ref},
            )
        ).one()
        assert proposal.status == "executed"
        assert proposal.decided_by_actor_id is not None

        annotation = (
            await session.execute(
                text(
                    "SELECT subject_type, subject_id, key, source, author_actor_id "
                    "FROM enrichment.record_annotation WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
        ).all()
    assert len(annotation) == 1
    assert annotation[0].subject_type == "person"
    assert annotation[0].subject_id == subject_id
    assert annotation[0].source == "agent"
    assert annotation[0].author_actor_id is not None


# --- 3. reject creates no annotation ------------------------------------


async def test_worker_reject_no_annotation(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from apps.worker.jobs.chat_inbound_map import map_chat_inbound

    subject_id = uuid.uuid4()
    ref, _ = await _propose(tenant_id, subject_id=subject_id)
    await _capture_action(
        tenant_id, proposal_ref=ref, decision="reject", user_id="mm-user-2"
    )

    result = await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)
    assert result["decisions"] == 1
    assert result["executed"] == 0

    async with async_session() as session:
        status = (
            await session.execute(
                text(
                    "SELECT status FROM integrations.agent_action_proposal "
                    "WHERE proposal_ref = :r"
                ),
                {"r": ref},
            )
        ).scalar_one()
        count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM enrichment.record_annotation "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
        ).scalar_one()
    assert status == "rejected"
    assert count == 0


# --- 4. idempotent — second pass executes exactly once ------------------


async def test_worker_approve_idempotent(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from apps.worker.jobs.chat_inbound_map import map_chat_inbound

    subject_id = uuid.uuid4()
    ref, _ = await _propose(tenant_id, subject_id=subject_id)

    # Capture the SAME approve action twice (e.g. a re-delivery).
    await _capture_action(
        tenant_id, proposal_ref=ref, decision="approve", user_id="mm-user-3"
    )
    await _capture_action(
        tenant_id, proposal_ref=ref, decision="approve", user_id="mm-user-3"
    )

    await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)
    # A second drain pass: even if a row reappeared, record_decision guards it.
    await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)

    async with async_session() as session:
        count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM enrichment.record_annotation "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
        ).scalar_one()
        status = (
            await session.execute(
                text(
                    "SELECT status FROM integrations.agent_action_proposal "
                    "WHERE proposal_ref = :r"
                ),
                {"r": ref},
            )
        ).scalar_one()
    assert count == 1
    assert status == "executed"


# --- 5. unknown proposal_ref → safe no-op -------------------------------


async def test_worker_unknown_ref_safe_noop(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from apps.worker.jobs.chat_inbound_map import map_chat_inbound

    await _capture_action(
        tenant_id,
        proposal_ref="does-not-exist",
        decision="approve",
        user_id="mm-user-4",
    )

    # Must not raise; the raw event is still marked processed.
    result = await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)
    assert result["decisions"] == 0
    assert result["executed"] == 0

    async with async_session() as session:
        unprocessed = (
            await session.execute(
                text(
                    "SELECT count(*) FROM ingest.raw_event "
                    "WHERE tenant_id = :tid AND processed_at IS NULL"
                ),
                {"tid": tenant_id},
            )
        ).scalar_one()
    assert unprocessed == 0


# --- 6. audit rows for proposed + decided + executed --------------------


async def test_audit_rows_written(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from apps.worker.jobs.chat_inbound_map import map_chat_inbound

    subject_id = uuid.uuid4()
    ref, _ = await _propose(tenant_id, subject_id=subject_id)
    await _capture_action(
        tenant_id, proposal_ref=ref, decision="approve", user_id="mm-user-5"
    )
    await map_chat_inbound({}, batch_size=100, tenant_id=tenant_id)

    async with async_session() as session:
        actions = (
            await session.execute(
                text(
                    "SELECT action FROM audit.access_log WHERE tenant_id = :tid "
                    "AND action LIKE 'agent.action.%'"
                ),
                {"tid": tenant_id},
            )
        ).scalars().all()
    assert "agent.action.proposed" in actions
    assert "agent.action.decided" in actions
    assert "agent.action.executed" in actions
