"""Pydantic DTOs for the agent human-in-the-loop layer (ENG-440, Block G).

``*In`` schemas are the service inputs; ``*Out`` schemas are read-only
projections that accept ORM rows via ``model_validate(obj)``. Kept in a
dedicated module so the HITL layer stays separable from the notification
DTOs and the legacy provider-plumbing DTOs in ``schemas.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentActionKind = Literal["annotation"]
AgentActionProposalStatus = Literal[
    "pending", "approved", "rejected", "executed", "failed"
]
AgentActionDecision = Literal["approve", "reject"]


class AgentActionProposalIn(BaseModel):
    """An agent's proposal of an action awaiting a human Approve/Reject.

    ``payload`` carries the bound action parameters. For ``kind='annotation'``
    it is ``{subject_type, subject_id, key, value, note?}`` — the shape the
    worker boundary feeds into ``EnrichmentService.add_annotation`` on approve.
    """

    channel: str = Field(min_length=1, max_length=255)
    kind: AgentActionKind = "annotation"
    payload: dict[str, object] = Field(default_factory=dict)


class AgentActionProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    proposal_ref: str
    channel: str
    kind: str
    payload: dict[str, object]
    status: AgentActionProposalStatus
    provider_message_id: str | None
    decided_by_actor_id: UUID | None
    decided_at: datetime | None
    result: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AgentActionDecision",
    "AgentActionKind",
    "AgentActionProposalIn",
    "AgentActionProposalOut",
    "AgentActionProposalStatus",
]
