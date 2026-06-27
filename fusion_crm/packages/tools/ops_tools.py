"""Ops-domain tools — PHI-free."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from packages.audit.service import AuditService
from packages.ops.schemas import FollowupTaskIn
from packages.ops.service import OpsService

from .base import ToolContext
from .person_tools import _to_uid


async def get_ops_person_snapshot(
    ctx: ToolContext,
    *,
    person_uid: str | UUID,
) -> dict:
    """Return a PHI-free snapshot of a person (display name, open follow-ups, last lead status)."""
    uid = _to_uid(person_uid)
    ops = OpsService(ctx.session)
    snapshot = await ops.snapshot(ctx.tenant_id, uid)

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="get_ops_person_snapshot",
        person_uid=uid,
    )

    return snapshot.model_dump(mode="json")


async def create_followup_task(
    ctx: ToolContext,
    *,
    person_uid: str | UUID,
    title: str,
    description: str | None = None,
    due_at: datetime | None = None,
    assigned_to: str | UUID | None = None,
) -> dict:
    """Create an OPEN follow-up task for a person. Returns the new task ID."""
    uid = _to_uid(person_uid)
    payload = FollowupTaskIn(
        person_uid=uid,
        title=title,
        description=description,
        due_at=due_at,
        assigned_to=UUID(str(assigned_to)) if assigned_to is not None else None,
    )
    ops = OpsService(ctx.session)
    task = await ops.create_followup(ctx.tenant_id, payload)

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="create_followup_task",
        person_uid=uid,
        extra={"title": title},
    )

    return {"id": str(task.id), "status": task.status}
