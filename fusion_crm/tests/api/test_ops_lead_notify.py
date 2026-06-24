"""API-boundary tests for the ``create_lead`` -> ``lead.created`` emit.

Two contracts are proven here:

1. The ``has_phone`` field-control bool (ENG-433): it is OMITTED when the lead
   payload carries no phone hint at all (UNKNOWN must not fire the
   ``has_phone == false`` rule), ``False`` when present-but-empty, ``True`` when
   a phone hint is present — and the RAW payload phone string is never copied
   verbatim into the context.
2. ENG-460: the messenger is an authorized PHI surface, so the route resolves
   the patient's real ``name`` + ``phone`` via ``IdentityService`` at the
   boundary (so the full-mode rich card is not degraded to empty fields).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.routers import ops as ops_router

_RESOLVED_NAME = "Test Patient"
_RESOLVED_PHONE = "+19998887777"


async def _emit_context_for(extra: dict[str, object]) -> dict[str, object]:
    """Call ``create_lead`` with mocked deps and return the emitted context."""
    lead = MagicMock()
    lead.source = "salesforce"
    lead.person_uid = uuid.uuid4()

    svc = MagicMock()
    svc.create_lead = AsyncMock(return_value=lead)

    events = MagicMock()
    events.emit = AsyncMock()

    # ENG-460: name + phone are resolved at the boundary via IdentityService.
    person = MagicMock()
    person.display_name = _RESOLVED_NAME
    identity = MagicMock()
    identity.get_person = AsyncMock(return_value=person)
    identity.get_primary_phone = AsyncMock(return_value=_RESOLVED_PHONE)

    principal = MagicMock()
    principal.require_tenant.return_value = uuid.uuid4()

    payload = MagicMock()
    payload.extra = extra

    # ``create_lead`` ends with ``LeadOut.model_validate(lead)``; bypass it so we
    # don't have to build a full ORM Lead — we only assert the emit context.
    original = ops_router.LeadOut.model_validate
    ops_router.LeadOut.model_validate = staticmethod(lambda obj: obj)  # type: ignore[assignment]
    try:
        await ops_router.create_lead(
            payload, principal, svc=svc, events=events, identity=identity
        )
    finally:
        ops_router.LeadOut.model_validate = original  # type: ignore[assignment]

    events.emit.assert_awaited_once()
    context = events.emit.await_args.args[2]
    return context


@pytest.mark.asyncio
async def test_no_phone_hint_omits_has_phone_so_rule_does_not_fire() -> None:
    context = await _emit_context_for({})
    assert "has_phone" not in context  # UNKNOWN -> omitted -> rule won't match


@pytest.mark.asyncio
async def test_present_but_empty_phone_emits_has_phone_false() -> None:
    context = await _emit_context_for({"phone": ""})
    assert context["has_phone"] is False


@pytest.mark.asyncio
async def test_present_phone_emits_has_phone_true_and_resolves_real_identity() -> None:
    context = await _emit_context_for({"phone": "+15558675309"})
    assert context["has_phone"] is True
    # ENG-460: the rich card carries the real name + phone resolved via
    # IdentityService — NOT the raw payload ``extra`` value.
    assert context["name"] == _RESOLVED_NAME
    assert context["phone"] == _RESOLVED_PHONE
    # The raw payload extra phone feeds ONLY the has_phone bool, never verbatim.
    assert "+15558675309" not in str(context)
