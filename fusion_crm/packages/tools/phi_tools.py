"""PHI-domain tools.

These tools require a principal with ``can_read_phi() == True`` — enforced
inside ``PhiService``. Both an authorisation check AND an audit row are
guaranteed for every successful (and every denied) call.
"""

from __future__ import annotations

from uuid import UUID

from packages.phi.service import PhiService

from .base import ToolContext
from .person_tools import _to_uid


async def get_phi_person_snapshot(
    ctx: ToolContext,
    *,
    person_uid: str | UUID,
    reason: str = "agent.phi.snapshot",
) -> dict:
    """Return a clinically aware snapshot of a person.

    Requires the calling principal to have a PHI-read role; otherwise raises
    ``PHIAccessDeniedError``. ``reason`` is recorded on the audit row.
    """
    uid = _to_uid(person_uid)
    phi = PhiService(ctx.session, ctx.principal)
    snapshot = await phi.snapshot(ctx.tenant_id, uid, reason=reason)
    # NOTE: PhiService writes the audit entry itself — do NOT double-log here.
    return snapshot.model_dump(mode="json")
