"""Agent human-in-the-loop action service (ENG-440, Block G).

The agent proposes an action in chat carrying **Approve** / **Reject**
buttons; a human clicks one; the click flows back through the EXISTING signed
inbound path (Block E captures it to ``ingest.raw_event``); the worker
boundary resolves the decision and, on approve, EXECUTES the bound action
through a domain service. This service owns the chat-side half of that loop:

* :meth:`AgentActionService.propose` — persist a pending proposal and post an
  interactive message whose button ``context`` carries the inbound
  ``webhook_secret`` token (so Block E verifies the action), the
  ``proposal_ref`` (so the worker can match it back), and the ``decision``.
* :meth:`AgentActionService.record_decision` — idempotently record the human
  decision (approve / reject). It NEVER executes the bound action — that is
  the worker boundary's job (the import matrix forbids ``integrations`` →
  ``enrichment``).
* :meth:`AgentActionService.mark_executed` / :meth:`mark_failed` — record the
  terminal execution outcome.

Architecture constraint (``packages/CLAUDE.md`` import matrix):
``integrations`` MUST NOT import ``enrichment``. Therefore the proposal store
and the decision logic live here, but the EXECUTION of an approved action
(which calls ``EnrichmentService``) happens at the worker boundary
(``apps/worker/jobs/chat_inbound_map.py``), an app that may import both.

Service rules (``packages/CLAUDE.md``): services never commit and never roll
back; the caller boundary owns the unit of work. Every state change writes an
``audit.access_log`` row in the same unit of work.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.tenant.credential_service import IntegrationCredentialService

from ..agent_action_repository import AgentActionProposalRepository
from ..agent_action_schemas import AgentActionProposalIn
from ..models import AGENT_ACTION_KINDS, AgentActionProposal
from .base import ChatMessage
from .inbound import (
    EVENT_TYPE_ACTION,
    INBOUND_CREDENTIAL_KIND,
    INBOUND_PROVIDER_KIND,
)
from .resolver import resolve_chat_provider

log = get_logger("integrations.chat.agent_actions")

AUDIT_AGENT_ACTION_PROPOSED = "agent.action.proposed"
AUDIT_AGENT_ACTION_DECIDED = "agent.action.decided"
AUDIT_AGENT_ACTION_EXECUTED = "agent.action.executed"
AUDIT_AGENT_ACTION_FAILED = "agent.action.failed"

# The Mattermost-facing callback for interactive button actions. Block E
# verifies the ``context.token`` against the tenant's stored inbound secret.
ACTION_CALLBACK_PATH = "/integrations/chat/mattermost/action"

# When the credential payload does not carry an ``action_callback_base`` we
# fall back to this local value Mattermost can reach (it runs in docker compose
# alongside the API; ``host.docker.internal`` resolves the host from inside the
# Mattermost container). Production sets ``action_callback_base`` explicitly.
DEFAULT_ACTION_CALLBACK_BASE = "http://host.docker.internal:8000"


class InvalidAgentActionError(ValueError):
    """Raised when a proposal is malformed (unknown kind, etc.)."""


class AgentActionService:
    """Chat-side half of the agent HITL loop (propose + decision recording)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AgentActionProposalRepository(session)
        self._credentials = IntegrationCredentialService(session)
        self._audit = AuditService(session)

    async def propose(
        self,
        tenant_id: TenantId,
        data: AgentActionProposalIn,
        *,
        principal: Principal,
    ) -> AgentActionProposal:
        """Persist a pending proposal and post the Approve/Reject card.

        The button ``context`` carries the inbound ``webhook_secret`` token so
        Block E can verify the action click, plus the generated
        ``proposal_ref`` and a ``decision`` (``approve`` / ``reject``). The
        provider message id is stored for traceability.
        """
        if data.kind not in AGENT_ACTION_KINDS:
            raise InvalidAgentActionError(
                f"unknown agent action kind {data.kind!r}; "
                f"expected one of {AGENT_ACTION_KINDS}"
            )

        proposal_ref = secrets.token_urlsafe(24)
        proposal = AgentActionProposal(
            tenant_id=tenant_id,
            proposal_ref=proposal_ref,
            channel=data.channel,
            kind=data.kind,
            payload=dict(data.payload),
            status="pending",
        )
        await self._repo.add(proposal)

        # Read the inbound webhook secret — the SAME token Block E verifies on
        # the way back in. It rides in the button context so the click is
        # authenticated. Never logged.
        inbound = await self._credentials.read_for(
            tenant_id, INBOUND_PROVIDER_KIND, INBOUND_CREDENTIAL_KIND
        )
        token = inbound.get("token")
        if not isinstance(token, str) or not token:
            raise InvalidAgentActionError(
                "mattermost webhook_secret credential missing token"
            )
        callback_base = inbound.get("action_callback_base")
        if not isinstance(callback_base, str) or not callback_base:
            callback_base = DEFAULT_ACTION_CALLBACK_BASE
        callback_url = f"{callback_base.rstrip('/')}{ACTION_CALLBACK_PATH}"

        message = self._build_message(
            channel=data.channel,
            proposal_ref=proposal_ref,
            kind=data.kind,
            token=token,
            callback_url=callback_url,
        )
        provider = await resolve_chat_provider(tenant_id, "mattermost", self._session)
        result = await provider.post(message)
        if result.provider_message_id is not None:
            proposal.provider_message_id = result.provider_message_id

        await self._audit.record(
            principal=principal,
            action=AUDIT_AGENT_ACTION_PROPOSED,
            resource="integrations.agent_action_proposal",
            extra={
                "tenant_id": str(tenant_id),
                "proposal_id": str(proposal.id),
                "proposal_ref": proposal_ref,
                "kind": data.kind,
                "channel": data.channel,
                "posted": result.ok,
            },
        )
        log.info(
            "agent_action.proposed",
            tenant_id=str(tenant_id),
            proposal_id=str(proposal.id),
            kind=data.kind,
            posted=result.ok,
        )

        # If the card never reached the channel, the human can NEVER click
        # Approve / Reject — so leaving the proposal ``pending`` would strand
        # it as forever-actionable. Mark it ``failed`` (still persisted for
        # traceability) and record an ``agent.action.failed`` audit row.
        if not result.ok:
            proposal.status = "failed"
            proposal.result = {"error": (result.error or "post failed")[:2000]}
            await self._audit.record(
                principal=principal,
                action=AUDIT_AGENT_ACTION_FAILED,
                resource="integrations.agent_action_proposal",
                extra={
                    "tenant_id": str(tenant_id),
                    "proposal_id": str(proposal.id),
                    "proposal_ref": proposal_ref,
                    "kind": data.kind,
                    "error_type": "post_failed",
                },
            )
            log.warning(
                "agent_action.propose.post_failed",
                tenant_id=str(tenant_id),
                proposal_id=str(proposal.id),
            )
        # Load server-default columns (created_at/updated_at) so callers can
        # build an Out DTO from this instance without triggering async-illegal
        # lazy IO on attribute access.
        await self._session.refresh(proposal)
        return proposal

    async def record_decision(
        self,
        tenant_id: TenantId,
        proposal_ref: str,
        decision: str,
        *,
        actor_id: UUID | None,
        principal: Principal,
    ) -> AgentActionProposal | None:
        """Record the human decision; idempotent. NEVER executes the action.

        Returns the proposal in its post-decision state, or ``None`` when no
        proposal matches the ``proposal_ref`` (safe no-op for the worker).
        When the proposal is ALREADY decided (status != ``pending``) it is
        returned unchanged — a re-delivered click must not flip or re-execute.
        """
        proposal = await self._repo.get_by_ref(tenant_id, proposal_ref)
        if proposal is None:
            log.info(
                "agent_action.decision.unknown_ref",
                tenant_id=str(tenant_id),
            )
            return None
        if proposal.status != "pending":
            # Already decided (and possibly executed) — idempotent return.
            return proposal

        new_status = "approved" if decision == "approve" else "rejected"
        proposal.status = new_status
        proposal.decided_by_actor_id = actor_id
        proposal.decided_at = datetime.now(UTC)
        await self._session.flush()

        await self._audit.record(
            principal=principal,
            action=AUDIT_AGENT_ACTION_DECIDED,
            resource="integrations.agent_action_proposal",
            extra={
                "tenant_id": str(tenant_id),
                "proposal_id": str(proposal.id),
                "proposal_ref": proposal_ref,
                "decision": new_status,
                "actor_id": str(actor_id) if actor_id is not None else None,
            },
        )
        log.info(
            "agent_action.decided",
            tenant_id=str(tenant_id),
            proposal_id=str(proposal.id),
            decision=new_status,
        )
        return proposal

    async def mark_executed(
        self,
        tenant_id: TenantId,
        proposal: AgentActionProposal,
        *,
        result: dict[str, object],
        principal: Principal,
    ) -> AgentActionProposal:
        """Terminal success — record the execution result + audit row."""
        proposal.status = "executed"
        proposal.result = dict(result)
        await self._session.flush()
        await self._audit.record(
            principal=principal,
            action=AUDIT_AGENT_ACTION_EXECUTED,
            resource="integrations.agent_action_proposal",
            extra={
                "tenant_id": str(tenant_id),
                "proposal_id": str(proposal.id),
                "proposal_ref": proposal.proposal_ref,
                "kind": proposal.kind,
            },
        )
        log.info(
            "agent_action.executed",
            tenant_id=str(tenant_id),
            proposal_id=str(proposal.id),
        )
        return proposal

    async def mark_failed(
        self,
        tenant_id: TenantId,
        proposal: AgentActionProposal,
        *,
        error: str,
        principal: Principal,
    ) -> AgentActionProposal:
        """Terminal failure — record the error reason + audit row."""
        proposal.status = "failed"
        proposal.result = {"error": error[:2000]}
        await self._session.flush()
        await self._audit.record(
            principal=principal,
            action=AUDIT_AGENT_ACTION_FAILED,
            resource="integrations.agent_action_proposal",
            extra={
                "tenant_id": str(tenant_id),
                "proposal_id": str(proposal.id),
                "proposal_ref": proposal.proposal_ref,
                "kind": proposal.kind,
                "error_type": "execution_error",
            },
        )
        log.warning(
            "agent_action.failed",
            tenant_id=str(tenant_id),
            proposal_id=str(proposal.id),
        )
        return proposal

    # --- Internals ----------------------------------------------------

    @staticmethod
    def _build_message(
        *,
        channel: str,
        proposal_ref: str,
        kind: str,
        token: str,
        callback_url: str,
    ) -> ChatMessage:
        """Build the interactive Approve/Reject message.

        Mattermost interactive buttons live in a message ATTACHMENT under
        ``props.attachments[*].actions``. The adapter maps
        ``ChatMessage.extra["attachments"]`` → ``props.attachments``. Each
        action's ``integration.url`` is our action callback; its
        ``integration.context`` carries the inbound token (so Block E verifies
        the click), the ``proposal_ref``, and the ``decision``.
        """

        def _action(name: str, decision: str) -> dict[str, object]:
            return {
                "id": decision,
                "name": name,
                "integration": {
                    "url": callback_url,
                    "context": {
                        "token": token,
                        "proposal_ref": proposal_ref,
                        "decision": decision,
                        "event_type": EVENT_TYPE_ACTION,
                    },
                },
            }

        attachment = {
            "text": f"Agent proposes an action ({kind}). Approve or reject?",
            "actions": [
                _action("Approve", "approve"),
                _action("Reject", "reject"),
            ],
        }
        return ChatMessage(
            channel=channel,
            text="Agent action awaiting your decision",
            extra={"attachments": [attachment]},
        )


__all__ = [
    "AUDIT_AGENT_ACTION_DECIDED",
    "AUDIT_AGENT_ACTION_EXECUTED",
    "AUDIT_AGENT_ACTION_FAILED",
    "AUDIT_AGENT_ACTION_PROPOSED",
    "AgentActionService",
    "InvalidAgentActionError",
]
