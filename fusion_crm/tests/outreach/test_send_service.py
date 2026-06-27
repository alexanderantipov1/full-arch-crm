"""Tests for ``PickMailboxService`` and ``SendService`` (ENG-132).

The repositories + audit service are mocked so these tests can run
without a Postgres instance. Repository behaviours that require real
DB semantics (the FOR UPDATE SKIP LOCKED batch lock, the partial
unique index on credentials) are covered by the integration suite
and by their respective domains.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.outreach.models import (
    Campaign,
    CampaignMailboxStrategy,
    Send,
    SendStatus,
)
from packages.outreach.send_service import (
    AUDIT_MAILBOX_ROUTED,
    AUDIT_SEND_ENQUEUED,
    NoMailboxAvailable,
    PickMailboxService,
    SendService,
)


def _principal() -> Principal:
    return Principal(id=uuid.uuid4(), email="op@example.com")


def _credential_dto(
    *,
    id: uuid.UUID | None = None,
    provider_kind: str = "google_workspace",
    status: str = "active",
    is_default: bool = False,
    tags: list[str] | None = None,
    location_id: uuid.UUID | None = None,
    mailbox_email: str | None = "info@galleriaoms.com",
) -> Any:
    """Stand-in for ``IntegrationCredentialOut`` — only the fields
    ``PickMailboxService`` reads.
    """
    obj = MagicMock()
    obj.id = id or uuid.uuid4()
    obj.provider_kind = provider_kind
    obj.status = status
    obj.is_default = is_default
    obj.tags = tags or []
    obj.location_id = location_id
    obj.mailbox_email = mailbox_email
    return obj


def _capture_add(captured: list[Any]) -> Any:
    """Build an async ``side_effect`` for a repo's ``add`` method.

    Sets an id + created_at on Send rows so the service sees a
    well-formed row after the (mocked) flush.
    """

    async def _f(obj: Any) -> Any:
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        if isinstance(obj, Send) and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
            obj.updated_at = obj.created_at
        captured.append(obj)
        return obj

    return _f


# --- PickMailboxService --------------------------------------------------


def _picker() -> tuple[PickMailboxService, MagicMock]:
    service = PickMailboxService(MagicMock())
    service._credentials = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()  # type: ignore[attr-defined]
    return service, service._credentials  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pick_mailbox_step_4_default_fallback() -> None:
    """When only a default mailbox exists, step 4 returns it."""
    tenant_id = TenantId(uuid.uuid4())
    default = _credential_dto(is_default=True)
    other = _credential_dto(is_default=False)

    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[other, default])

    chosen = await service.pick(tenant_id, principal=_principal())
    assert chosen.id == default.id
    call_kwargs = service._audit.record.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["action"] == AUDIT_MAILBOX_ROUTED
    assert call_kwargs["extra"]["strategy_step"] == 4


@pytest.mark.asyncio
async def test_pick_mailbox_auto_route_prefers_location_pinned() -> None:
    """Step 1 — location + tag match wins over default."""
    tenant_id = TenantId(uuid.uuid4())
    location_id = uuid.uuid4()

    galleria_pinned = _credential_dto(
        tags=["marketing"], location_id=location_id
    )
    default = _credential_dto(is_default=True)

    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[default, galleria_pinned])

    chosen = await service.pick(
        tenant_id,
        intent_tag="marketing",
        recipient_location_id=location_id,
        principal=_principal(),
    )
    assert chosen.id == galleria_pinned.id
    call_kwargs = service._audit.record.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["extra"]["strategy_step"] == 1


@pytest.mark.asyncio
async def test_pick_mailbox_step_2_tag_only() -> None:
    """Step 2 — intent_tag matches but no location."""
    tenant_id = TenantId(uuid.uuid4())
    tagged = _credential_dto(tags=["marketing"])
    default = _credential_dto(is_default=True)

    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[default, tagged])

    chosen = await service.pick(
        tenant_id,
        intent_tag="marketing",
        principal=_principal(),
    )
    assert chosen.id == tagged.id
    call_kwargs = service._audit.record.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["extra"]["strategy_step"] == 2


@pytest.mark.asyncio
async def test_pick_mailbox_step_3_provider_hint_default() -> None:
    """Step 3 — provider hint plus is_default."""
    tenant_id = TenantId(uuid.uuid4())
    google_default = _credential_dto(
        provider_kind="google_workspace", is_default=True
    )
    ms_default = _credential_dto(
        provider_kind="microsoft_365", is_default=True
    )

    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[google_default, ms_default])

    chosen = await service.pick(
        tenant_id,
        provider_hint="microsoft_365",
        principal=_principal(),
    )
    assert chosen.id == ms_default.id
    call_kwargs = service._audit.record.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["extra"]["strategy_step"] == 3


@pytest.mark.asyncio
async def test_pick_mailbox_no_mailbox_raises_when_no_credentials() -> None:
    tenant_id = TenantId(uuid.uuid4())
    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[])

    with pytest.raises(NoMailboxAvailable):
        await service.pick(tenant_id, principal=_principal())


@pytest.mark.asyncio
async def test_pick_mailbox_no_match_raises() -> None:
    """Mailboxes exist but no rule matches (no default, no tag, no loc)."""
    tenant_id = TenantId(uuid.uuid4())
    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(
        return_value=[_credential_dto(is_default=False)]
    )

    with pytest.raises(NoMailboxAvailable):
        await service.pick(tenant_id, principal=_principal())


@pytest.mark.asyncio
async def test_pick_mailbox_filters_to_email_providers_only() -> None:
    """SF / CareStack credentials must never be returned as mailboxes."""
    tenant_id = TenantId(uuid.uuid4())
    sf_default = _credential_dto(
        provider_kind="salesforce", is_default=True
    )
    google_default = _credential_dto(
        provider_kind="google_workspace", is_default=True
    )

    service, creds = _picker()
    creds.list_for_tenant = AsyncMock(return_value=[sf_default, google_default])

    chosen = await service.pick(tenant_id, principal=_principal())
    assert chosen.id == google_default.id


# --- SendService.enqueue_campaign ---------------------------------------


def _campaign_row(
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    mailbox_strategy: str = CampaignMailboxStrategy.EXPLICIT.value,
    mailbox_credential_id: uuid.UUID | None = None,
    recipients: list[dict[str, Any]] | None = None,
) -> Campaign:
    c = Campaign(
        tenant_id=tenant_id,
        template_id=template_id,
        name="Q2 recall",
        recipient_query={"recipients": recipients or []},
        mailbox_credential_id=mailbox_credential_id,
        mailbox_strategy=mailbox_strategy,
    )
    c.id = uuid.uuid4()
    c.scheduled_for = None
    return c


def _template_row(
    *, tenant_id: uuid.UUID, intent_tags: list[str] | None = None
) -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.tenant_id = tenant_id
    t.intent_tags = intent_tags or []
    return t


def _make_send_service() -> tuple[SendService, dict[str, MagicMock]]:
    session = MagicMock()
    service = SendService(session)
    service._campaigns = MagicMock()  # type: ignore[attr-defined]
    service._templates = MagicMock()  # type: ignore[attr-defined]
    service._sends = MagicMock()  # type: ignore[attr-defined]
    service._queue = MagicMock()  # type: ignore[attr-defined]
    service._suppression = MagicMock()  # type: ignore[attr-defined]
    service._picker = MagicMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]

    service._suppression.is_suppressed = AsyncMock(return_value=False)  # type: ignore[attr-defined]
    service._picker.pick = AsyncMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()  # type: ignore[attr-defined]

    return service, {
        "campaigns": service._campaigns,  # type: ignore[attr-defined]
        "templates": service._templates,  # type: ignore[attr-defined]
        "sends": service._sends,  # type: ignore[attr-defined]
        "queue": service._queue,  # type: ignore[attr-defined]
        "suppression": service._suppression,  # type: ignore[attr-defined]
        "picker": service._picker,  # type: ignore[attr-defined]
        "audit": service._audit,  # type: ignore[attr-defined]
    }


@pytest.mark.asyncio
async def test_enqueue_campaign_materialises_queue_rows_explicit() -> None:
    """Explicit strategy: every recipient gets a send + queue row."""
    tenant_id = TenantId(uuid.uuid4())
    template = _template_row(tenant_id=tenant_id)
    credential_id = uuid.uuid4()
    campaign = _campaign_row(
        tenant_id=tenant_id,
        template_id=template.id,
        mailbox_strategy=CampaignMailboxStrategy.EXPLICIT.value,
        mailbox_credential_id=credential_id,
        recipients=[
            {"email": "a@example.com"},
            {"email": "b@example.com"},
            {"email": "c@example.com"},
        ],
    )
    service, mocks = _make_send_service()
    mocks["campaigns"].get_for_tenant = AsyncMock(return_value=campaign)
    mocks["templates"].get_for_tenant = AsyncMock(return_value=template)

    sends_captured: list[Send] = []
    queue_captured: list[Any] = []
    mocks["sends"].add = AsyncMock(side_effect=_capture_add(sends_captured))
    mocks["queue"].add = AsyncMock(side_effect=_capture_add(queue_captured))

    count = await service.enqueue_campaign(
        tenant_id, campaign.id, principal=_principal()
    )
    assert count == 3
    assert len(sends_captured) == 3
    assert len(queue_captured) == 3
    for s in sends_captured:
        assert s.mailbox_credential_id == credential_id
        assert s.status == SendStatus.QUEUED.value
    # Picker must NOT have been called for explicit strategy.
    assert mocks["picker"].pick.await_count == 0


@pytest.mark.asyncio
async def test_enqueue_campaign_skips_suppressed_recipients() -> None:
    """Suppressed recipients get a send row (status=unsubscribed) and NO queue row."""
    tenant_id = TenantId(uuid.uuid4())
    template = _template_row(tenant_id=tenant_id)
    credential_id = uuid.uuid4()
    campaign = _campaign_row(
        tenant_id=tenant_id,
        template_id=template.id,
        mailbox_credential_id=credential_id,
        recipients=[
            {"email": "ok@example.com"},
            {"email": "blocked@example.com"},
        ],
    )
    service, mocks = _make_send_service()
    mocks["campaigns"].get_for_tenant = AsyncMock(return_value=campaign)
    mocks["templates"].get_for_tenant = AsyncMock(return_value=template)

    async def _suppressed(_tenant_id: Any, email: str) -> bool:
        return email == "blocked@example.com"

    mocks["suppression"].is_suppressed = AsyncMock(side_effect=_suppressed)

    sends_captured: list[Send] = []
    queue_captured: list[Any] = []
    mocks["sends"].add = AsyncMock(side_effect=_capture_add(sends_captured))
    mocks["queue"].add = AsyncMock(side_effect=_capture_add(queue_captured))

    count = await service.enqueue_campaign(
        tenant_id, campaign.id, principal=_principal()
    )
    # Two send rows; one queue row only (the suppressed one is not queued).
    assert count == 1
    assert len(sends_captured) == 2
    assert len(queue_captured) == 1
    statuses = {s.status for s in sends_captured}
    assert SendStatus.UNSUBSCRIBED.value in statuses
    assert SendStatus.QUEUED.value in statuses


@pytest.mark.asyncio
async def test_enqueue_campaign_auto_route_calls_picker() -> None:
    """Auto-route strategy invokes the picker for each recipient."""
    tenant_id = TenantId(uuid.uuid4())
    template = _template_row(tenant_id=tenant_id, intent_tags=["marketing"])
    campaign = _campaign_row(
        tenant_id=tenant_id,
        template_id=template.id,
        mailbox_strategy=CampaignMailboxStrategy.AUTO_ROUTE.value,
        mailbox_credential_id=None,
        recipients=[
            {"email": "a@example.com"},
            {"email": "b@example.com"},
        ],
    )
    service, mocks = _make_send_service()
    mocks["campaigns"].get_for_tenant = AsyncMock(return_value=campaign)
    mocks["templates"].get_for_tenant = AsyncMock(return_value=template)

    chosen = _credential_dto(is_default=True)
    mocks["picker"].pick = AsyncMock(return_value=chosen)

    sends_captured: list[Send] = []
    queue_captured: list[Any] = []
    mocks["sends"].add = AsyncMock(side_effect=_capture_add(sends_captured))
    mocks["queue"].add = AsyncMock(side_effect=_capture_add(queue_captured))

    count = await service.enqueue_campaign(
        tenant_id, campaign.id, principal=_principal()
    )
    assert count == 2
    # Picker called once per recipient.
    assert mocks["picker"].pick.await_count == 2
    # Every send pinned to the chosen credential.
    for s in sends_captured:
        assert s.mailbox_credential_id == chosen.id
    # Picker was called with the template's intent_tag.
    first_call = mocks["picker"].pick.await_args_list[0]
    assert first_call.kwargs["intent_tag"] == "marketing"


@pytest.mark.asyncio
async def test_enqueue_campaign_writes_send_enqueued_audit_without_raw_email() -> None:
    tenant_id = TenantId(uuid.uuid4())
    template = _template_row(tenant_id=tenant_id)
    credential_id = uuid.uuid4()
    campaign = _campaign_row(
        tenant_id=tenant_id,
        template_id=template.id,
        mailbox_credential_id=credential_id,
        recipients=[{"email": "a@example.com"}],
    )
    service, mocks = _make_send_service()
    mocks["campaigns"].get_for_tenant = AsyncMock(return_value=campaign)
    mocks["templates"].get_for_tenant = AsyncMock(return_value=template)
    mocks["sends"].add = AsyncMock(side_effect=_capture_add([]))
    mocks["queue"].add = AsyncMock(side_effect=_capture_add([]))

    await service.enqueue_campaign(
        tenant_id, campaign.id, principal=_principal()
    )

    actions = [c.kwargs["action"] for c in mocks["audit"].record.await_args_list]
    assert AUDIT_SEND_ENQUEUED in actions

    # Audit must not contain the raw email — only a hash.
    extras = [c.kwargs["extra"] for c in mocks["audit"].record.await_args_list]
    for extra in extras:
        assert "a@example.com" not in str(extra)


@pytest.mark.asyncio
async def test_enqueue_campaign_unknown_campaign_raises() -> None:
    tenant_id = TenantId(uuid.uuid4())
    service, mocks = _make_send_service()
    mocks["campaigns"].get_for_tenant = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.enqueue_campaign(
            tenant_id, uuid.uuid4(), principal=_principal()
        )
