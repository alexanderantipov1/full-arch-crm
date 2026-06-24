"""Agent entry point for chat human-in-the-loop proposals (ENG-440, Block G).

This is the thin door an agent uses to propose an action in chat WITHOUT
touching the database. It delegates to
:class:`packages.integrations.chat.agent_actions.AgentActionService`, the
chat-side store + post. The import matrix permits ``agent_runtime`` →
``integrations`` (and forbids ``agent_runtime`` → ``enrichment``), so the
agent reaches the proposal store only through this governed service boundary —
never a repository, never the ORM, never a raw session beyond the one the
caller boundary already owns.

Execution of an approved annotation happens later, at the worker boundary
(``apps/worker/jobs/chat_inbound_map.py``), which is the only place allowed to
import both ``integrations`` and ``enrichment``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.agent_action_schemas import (
    AgentActionProposalIn,
    AgentActionProposalOut,
)
from packages.integrations.chat.agent_actions import AgentActionService


class AgentChatActions:
    """Agent-facing facade for proposing chat actions with human approval."""

    def __init__(self, session: AsyncSession) -> None:
        self._service = AgentActionService(session)

    async def propose_annotation(
        self,
        tenant_id: TenantId,
        *,
        channel: str,
        subject_type: str,
        subject_id: UUID,
        key: str,
        value: dict[str, object],
        note: str | None = None,
        principal: Principal,
    ) -> AgentActionProposalOut:
        """Propose an enrichment annotation for human Approve/Reject in chat.

        The bound action runs only AFTER a human approves the click; on
        approval the worker boundary calls ``EnrichmentService.add_annotation``
        with ``source="agent"``.
        """
        payload: dict[str, object] = {
            "subject_type": subject_type,
            "subject_id": str(subject_id),
            "key": key,
            "value": value,
        }
        if note is not None:
            payload["note"] = note

        proposal = await self._service.propose(
            tenant_id,
            AgentActionProposalIn(
                channel=channel,
                kind="annotation",
                payload=payload,
            ),
            principal=principal,
        )
        return AgentActionProposalOut.model_validate(proposal)


__all__ = ["AgentChatActions"]
