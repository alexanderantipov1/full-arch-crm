"""Map captured Mattermost inbound raw events → actors (ENG-438, Block E).

Block E captures every signed inbound Mattermost callback verbatim into
``ingest.raw_event`` on the API hot path. This worker drains those
unprocessed rows OFF the hot path and performs the only mapping Block E
owns: resolve / attach the Mattermost user to an internal ``actor.actor``
via ``actor.actor_identifier`` (``kind="mattermost_user_id"``,
``value=user_id``), then mark the raw event processed.

Block G (agent HITL, ENG-440) EXTENDS this worker: when a captured row is a
``mattermost.action`` carrying a ``proposal_ref`` + ``decision`` in its
``context``, this boundary resolves the decision through
``AgentActionService.record_decision`` and, when the decision is an approval of
an ``annotation`` proposal, EXECUTES the bound action through
``EnrichmentService.add_annotation`` (``source="agent"``) and records the
outcome. The worker is the ONLY place allowed to import both ``integrations``
and ``enrichment`` (the import matrix forbids ``integrations`` →
``enrichment``), so the unit of work that crosses that boundary lives here.

DEFERRED (NOT done here):

* recording chat replies as ``interaction`` annotations → Block F
  (``record_annotation``, ENG-439) free-text reply path.

So this job links the actor, resolves any agent-action decision, records a
STRUCTURED, non-PII outcome on the row, then marks it processed. The verbatim
text stays in ``raw_event.payload`` — we never log it.

Idempotency / safety:

* only ``processed_at IS NULL`` rows are touched (``list_unprocessed``);
* a row with no ``user_id`` is still marked processed (with an outcome of
  ``no_user_id``) so it does not jam the queue — there is nothing to link;
* ``attach_identifier`` is idempotent on ``(kind, value)`` so re-runs and
  repeated users do not create duplicate actors / identifiers;
* ``record_decision`` is idempotent — an already-decided proposal is never
  re-flipped or re-executed, so a re-delivered click executes the annotation
  exactly once even if the same raw event were reprocessed;
* per-row failures mark the row with an error and continue — one bad row
  must not stall the batch.
"""

from __future__ import annotations

from uuid import UUID

from packages.actor.schemas import ActorIdentifierIn, ActorIn
from packages.actor.service import ActorService
from packages.core.config import get_settings
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.enrichment.schemas import AnnotationIn
from packages.enrichment.service import EnrichmentService
from packages.ingest.service import IngestService
from packages.integrations.chat.agent_actions import AgentActionService
from packages.integrations.chat.inbound import EVENT_TYPE_ACTION, INBOUND_SOURCE
from packages.tenant.service import TenantService

log = get_logger("worker.chat_inbound")

# Identifier kind for a Mattermost user (see packages/actor/CLAUDE.md).
ACTOR_KIND_MATTERMOST_USER = "mattermost_user_id"


def _system_principal(tenant_id: TenantId) -> Principal:
    """A synthesised principal for worker-side audit rows (Block G)."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "worker.chat_inbound_map"},
    )


def _context_value(payload: dict[str, object], key: str) -> str | None:
    """Read a string ``context.<key>`` from a captured action payload."""
    context = payload.get("context")
    if isinstance(context, dict):
        value = context.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _user_id_from_payload(payload: dict[str, object]) -> str | None:
    """Extract the Mattermost ``user_id`` from a captured inbound payload.

    Outgoing webhooks carry it at the top level; interactive actions may
    carry it at the top level or inside ``context``. Mirrors the parse rules
    in ``packages.integrations.chat.inbound`` without importing the dataclass
    (the worker reads the persisted dict, not the request).
    """
    top = payload.get("user_id")
    if isinstance(top, str) and top:
        return top
    context = payload.get("context")
    if isinstance(context, dict):
        nested = context.get("user_id")
        if isinstance(nested, str) and nested:
            return nested
    return None


async def _resolve_agent_action(
    payload: dict[str, object],
    *,
    tenant_id: TenantId,
    actor_id: UUID,
    agent_actions: AgentActionService,
    enrichment: EnrichmentService,
    principal: Principal,
) -> dict[str, bool]:
    """Resolve (and, on approve, execute) one agent-action button click.

    Reads ``context.proposal_ref`` + ``context.decision``, records the human
    decision via ``AgentActionService.record_decision`` (idempotent — a
    re-delivered click never re-flips or re-executes), then, when the proposal
    is now ``approved`` and ``kind == "annotation"``, executes the bound action
    through ``EnrichmentService.add_annotation`` (``source="agent"``) and marks
    the proposal executed / failed. Returns whether a decision was recorded and
    whether an execution ran.

    A missing / unknown ``proposal_ref`` is a safe no-op: ``record_decision``
    returns ``None`` and the caller still marks the raw event processed.
    """
    result = {"decided": False, "executed": False}

    proposal_ref = _context_value(payload, "proposal_ref")
    decision = _context_value(payload, "decision")
    if proposal_ref is None or decision is None:
        return result

    proposal = await agent_actions.record_decision(
        tenant_id,
        proposal_ref,
        decision,
        actor_id=actor_id,
        principal=principal,
    )
    if proposal is None:
        # Unknown proposal_ref — safe no-op.
        return result
    result["decided"] = True

    # Execute exactly once: only a freshly-approved annotation proposal runs.
    # ``approved`` (not ``executed``/``failed``) guards against a re-delivered
    # click double-executing — a second pass sees ``executed`` and skips here.
    if proposal.status == "approved" and proposal.kind == "annotation":
        try:
            # ``AnnotationIn`` validates the bound payload (subject_type,
            # subject_id, key, value, optional note). It coerces the
            # str-serialised subject_id back to a UUID and rejects a malformed
            # payload at the service boundary — which routes into mark_failed.
            annotation_in = AnnotationIn.model_validate(
                {
                    **dict(proposal.payload),
                    "source": "agent",
                    "author_actor_id": actor_id,
                }
            )
            annotation = await enrichment.add_annotation(
                tenant_id,
                annotation_in,
                principal=principal,
            )
            await agent_actions.mark_executed(
                tenant_id,
                proposal,
                result={"annotation_id": str(annotation.id)},
                principal=principal,
            )
            result["executed"] = True
        except Exception as exc:  # noqa: BLE001 — record + continue (per CLAUDE.md)
            await agent_actions.mark_failed(
                tenant_id,
                proposal,
                error=str(exc),
                principal=principal,
            )
            log.warning(
                "chat_inbound.map.agent_action.execute_error",
                tenant_id=str(tenant_id),
                proposal_id=str(proposal.id),
                error_type=type(exc).__name__,
            )

    return result


async def map_chat_inbound(
    _ctx: dict,
    *,
    batch_size: int = 100,
    tenant_id: TenantId | None = None,
) -> dict:
    """Drain unprocessed Mattermost raw events; link actors; mark processed.

    ``tenant_id`` is the Phase-2 hook (kwarg-passed tenant). When omitted the
    job resolves the bootstrap default slug, mirroring
    ``process_unprocessed_events`` (ENG-128).
    """
    settings = get_settings()
    linked = 0
    skipped_no_user = 0
    decisions = 0
    executed = 0
    errors = 0

    async with async_session() as session:
        if tenant_id is None:
            tenant = await TenantService(session).resolve_default(
                settings.tenant_default_slug
            )
            tenant_id = TenantId(tenant.id)

        ingest = IngestService(session)
        actors = ActorService(session)
        agent_actions = AgentActionService(session)
        enrichment = EnrichmentService(session)
        principal = _system_principal(tenant_id)

        # Filter by source at the DB level: the global unprocessed backlog can
        # be huge (>1M ingest rows), so a generic batch would never include the
        # rare Mattermost rows. Pull only our source.
        events = await ingest.list_unprocessed(
            tenant_id, limit=batch_size, source=INBOUND_SOURCE
        )
        for event in events:

            user_id = _user_id_from_payload(event.payload)
            if user_id is None:
                await ingest.mark_processed(tenant_id, event.id)
                skipped_no_user += 1
                log.info(
                    "chat_inbound.map.no_user_id",
                    tenant_id=str(tenant_id),
                    raw_event_id=str(event.id),
                    event_type=event.event_type,
                )
                continue

            try:
                actor = await actors.find_by_identifier(
                    tenant_id, ACTOR_KIND_MATTERMOST_USER, user_id
                )
                if actor is None:
                    actor = await actors.upsert_actor(
                        tenant_id,
                        ActorIn(
                            actor_type="human",
                            name=f"Mattermost user {user_id}",
                            identifiers=[
                                ActorIdentifierIn(
                                    kind=ACTOR_KIND_MATTERMOST_USER,
                                    value=user_id,
                                ),
                            ],
                        ),
                    )

                # Block G: resolve an agent-action decision when this row is an
                # interactive button click carrying a proposal_ref + decision.
                if event.event_type == EVENT_TYPE_ACTION:
                    outcome = await _resolve_agent_action(
                        event.payload,
                        tenant_id=tenant_id,
                        actor_id=actor.id,
                        agent_actions=agent_actions,
                        enrichment=enrichment,
                        principal=principal,
                    )
                    if outcome["decided"]:
                        decisions += 1
                    if outcome["executed"]:
                        executed += 1

                await ingest.mark_processed(tenant_id, event.id)
                linked += 1
                log.info(
                    "chat_inbound.map.linked",
                    tenant_id=str(tenant_id),
                    raw_event_id=str(event.id),
                    event_type=event.event_type,
                    actor_id=str(actor.id),
                )
            except Exception as exc:
                # Per packages/CLAUDE.md: ``except Exception`` only. One bad
                # row must not stall the batch; record the error and move on.
                errors += 1
                await ingest.mark_error(tenant_id, event.id, str(exc))
                log.warning(
                    "chat_inbound.map.error",
                    tenant_id=str(tenant_id),
                    raw_event_id=str(event.id),
                    error_type=type(exc).__name__,
                )

    log.info(
        "chat_inbound.map.done",
        tenant_id=str(tenant_id),
        linked=linked,
        skipped_no_user=skipped_no_user,
        decisions=decisions,
        executed=executed,
        errors=errors,
    )
    return {
        "linked": linked,
        "skipped_no_user": skipped_no_user,
        "decisions": decisions,
        "executed": executed,
        "errors": errors,
    }
