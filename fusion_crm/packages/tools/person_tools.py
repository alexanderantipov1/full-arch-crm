"""Identity-domain tools."""

from __future__ import annotations

from uuid import UUID

from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError
from packages.core.types import PersonUID
from packages.identity.service import IdentityService

from .base import ToolContext


async def resolve_person(
    ctx: ToolContext,
    *,
    phone: str | None = None,
    email: str | None = None,
) -> dict | None:
    """Resolve a Person by phone or email.

    Returns ``{"person_uid": "<uuid>", "display_name": "..."}`` or ``None`` if
    no match. Exactly one of ``phone`` or ``email`` MUST be provided.
    """
    if bool(phone) == bool(email):
        raise ValidationError("provide exactly one of phone, email")

    identity = IdentityService(ctx.session)
    tenant_id = ctx.tenant_id
    person = (
        await identity.resolve_by_phone(tenant_id, phone)  # type: ignore[arg-type]
        if phone
        else await identity.resolve_by_email(tenant_id, email)  # type: ignore[arg-type]
    )

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="resolve_person",
        person_uid=PersonUID(person.id) if person else None,
        extra={"by": "phone" if phone else "email"},
    )

    if person is None:
        return None
    return {"person_uid": str(person.id), "display_name": person.display_name}


def _to_uid(value: str | UUID) -> PersonUID:
    return PersonUID(value if isinstance(value, UUID) else UUID(value))
