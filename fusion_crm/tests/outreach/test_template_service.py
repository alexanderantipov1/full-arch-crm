"""Service-level tests for outreach templates (ENG-133).

Focus: tracking gate, version-bump on update, validation surface,
and tenant-isolation behaviour at the service entry point.

The service depends on identity + ops + audit. We mock the
session-bound collaborators so these tests can run without a live
Postgres — repository behaviours that genuinely require Postgres
(unique constraints, check constraints) are covered by the migration
+ integration suite, not here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.outreach.models import Template, TemplateStatus
from packages.outreach.schemas import TemplateIn, TemplateUpdate
from packages.outreach.service import (
    AUDIT_TEMPLATE_ARCHIVE,
    AUDIT_TEMPLATE_CREATE,
    AUDIT_TEMPLATE_UPDATE,
    TemplateService,
)


def _principal() -> Principal:
    return Principal(id=uuid.uuid4(), email="op@example.com")


def _make_template_row(
    *,
    tenant_id: uuid.UUID,
    name: str = "Welcome",
    body: str = "Hi {{patient.first_name}}",
    body_format: str = "markdown",
    category: str = "marketing",
    tracking_enabled: bool = False,
    status: str = "draft",
    version: int = 1,
) -> Template:
    template = Template(
        tenant_id=tenant_id,
        name=name,
        description=None,
        subject_template="Hello {{patient.first_name}}",
        body_template=body,
        body_format=body_format,
        category=category,
        tracking_enabled=tracking_enabled,
        intent_tags=[],
        version=version,
        status=status,
        created_by_actor_id=None,
    )
    template.id = uuid.uuid4()
    template.created_at = datetime(2026, 5, 10, 12, 0, 0)
    template.updated_at = datetime(2026, 5, 10, 12, 0, 0)
    return template


def _persist_template_row(template: Template) -> Template:
    """Simulate fields populated by the ORM during repository persistence."""
    template.id = template.id or uuid.uuid4()
    template.created_at = template.created_at or datetime(2026, 5, 10, 12, 0, 0)
    template.updated_at = template.updated_at or datetime(2026, 5, 10, 12, 0, 0)
    return template


def _make_service() -> tuple[TemplateService, MagicMock, MagicMock]:
    session = MagicMock()
    service = TemplateService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._ops = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo, service._audit  # type: ignore[attr-defined]


# --- Create + tracking gate ----------------------------------------------


@pytest.mark.asyncio
async def test_create_template_marketing_can_enable_tracking() -> None:
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.find_by_name = AsyncMock(return_value=None)

    captured: dict[str, Any] = {}

    async def _capture(template: Template) -> Template:
        persisted = _persist_template_row(template)
        captured["template"] = persisted
        return persisted

    repo.add = AsyncMock(side_effect=_capture)

    payload = TemplateIn(
        name="Welcome",
        subject_template="Hi {{patient.first_name}}",
        body_template="Hello {{patient.first_name}}",
        body_format="markdown",
        category="marketing",
        tracking_enabled=True,
    )
    result = await service.create_template(tenant_id, payload, principal=_principal())
    assert result.tracking_enabled is True
    assert captured["template"].category == "marketing"
    audit.record.assert_awaited()
    call_kwargs = audit.record.call_args.kwargs
    assert call_kwargs["action"] == AUDIT_TEMPLATE_CREATE


@pytest.mark.asyncio
async def test_create_template_clinical_default_tracking_off() -> None:
    """Clinical category MUST have tracking_enabled=False (default)."""
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.find_by_name = AsyncMock(return_value=None)
    repo.add = AsyncMock(side_effect=_persist_template_row)

    payload = TemplateIn(
        name="Recall",
        subject_template="Time for your check-up",
        body_template="Hi {{patient.first_name}}",
        body_format="markdown",
        category="clinical",
        # default tracking_enabled=False — accepted
    )
    result = await service.create_template(tenant_id, payload, principal=_principal())
    assert result.category == "clinical"
    assert result.tracking_enabled is False


@pytest.mark.asyncio
async def test_create_template_clinical_with_tracking_rejected() -> None:
    """Clinical + tracking_enabled=True → ValidationError."""
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.find_by_name = AsyncMock(return_value=None)

    payload = TemplateIn(
        name="Recall",
        subject_template="Hi",
        body_template="Hi",
        body_format="markdown",
        category="clinical",
        tracking_enabled=True,
    )
    with pytest.raises(ValidationError) as excinfo:
        await service.create_template(tenant_id, payload, principal=_principal())
    assert "tracking_enabled" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_template_html_body_format_rejected() -> None:
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.find_by_name = AsyncMock(return_value=None)

    payload = TemplateIn(
        name="Promo",
        subject_template="Hi",
        body_template="<h1>Hi</h1>",
        body_format="html",
        category="marketing",
    )
    with pytest.raises(ValidationError):
        await service.create_template(tenant_id, payload, principal=_principal())


# --- Update bumps version on actual change -------------------------------


@pytest.mark.asyncio
async def test_update_template_bumps_version_when_body_changes() -> None:
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id, version=3)
    repo.get_for_tenant = AsyncMock(return_value=template)
    repo.find_by_name = AsyncMock(return_value=None)

    payload = TemplateUpdate(body_template="Updated body {{patient.first_name}}")
    result = await service.update_template(tenant_id, template.id, payload, principal=_principal())
    assert result.version == 4
    audit.record.assert_awaited()
    call_kwargs = audit.record.call_args.kwargs
    assert call_kwargs["action"] == AUDIT_TEMPLATE_UPDATE
    assert call_kwargs["extra"]["changed"] is True


@pytest.mark.asyncio
async def test_update_template_no_changes_keeps_version() -> None:
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id, version=2)
    repo.get_for_tenant = AsyncMock(return_value=template)

    # Empty patch — service should not bump version.
    payload = TemplateUpdate()
    result = await service.update_template(tenant_id, template.id, payload, principal=_principal())
    assert result.version == 2
    call_kwargs = audit.record.call_args.kwargs
    assert call_kwargs["extra"]["changed"] is False


@pytest.mark.asyncio
async def test_update_template_rejects_clinical_with_tracking() -> None:
    """Updating to a clinical category while tracking is on must fail."""
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(
        tenant_id=tenant_id,
        category="marketing",
        tracking_enabled=True,
    )
    repo.get_for_tenant = AsyncMock(return_value=template)

    payload = TemplateUpdate(category="clinical")
    with pytest.raises(ValidationError):
        await service.update_template(tenant_id, template.id, payload, principal=_principal())


# --- Soft-delete via archive --------------------------------------------


@pytest.mark.asyncio
async def test_delete_template_archives_in_place() -> None:
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id, status="active", version=5)
    repo.get_for_tenant = AsyncMock(return_value=template)

    result = await service.delete_template(tenant_id, template.id, principal=_principal())
    assert result.status == TemplateStatus.ARCHIVED.value
    assert result.version == 6
    call_kwargs = audit.record.call_args.kwargs
    assert call_kwargs["action"] == AUDIT_TEMPLATE_ARCHIVE


# --- Validation surface --------------------------------------------------


@pytest.mark.asyncio
async def test_validate_surfaces_unknown_merge_field() -> None:
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(
        tenant_id=tenant_id,
        body="Hello {{patient.first_name}}; SSN={{ssn}}",
    )
    repo.get_for_tenant = AsyncMock(return_value=template)

    issues = await service.validate(tenant_id, template.id)
    codes = {issue.code for issue in issues}
    assert "unknown_merge_field" in codes
    fields = {issue.field for issue in issues if issue.code == "unknown_merge_field"}
    assert "ssn" in fields


@pytest.mark.asyncio
async def test_validate_flags_html_format_as_forbidden() -> None:
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id, body_format="html")
    repo.get_for_tenant = AsyncMock(return_value=template)

    issues = await service.validate(tenant_id, template.id)
    codes = [issue.code for issue in issues]
    assert "forbidden_body_format" in codes


@pytest.mark.asyncio
async def test_validate_flags_empty_subject() -> None:
    service, repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id)
    template.subject_template = "{{ssn}}"  # entirely unknown → empty after render
    repo.get_for_tenant = AsyncMock(return_value=template)

    issues = await service.validate(tenant_id, template.id)
    codes = {issue.code for issue in issues}
    assert "empty_subject" in codes


# --- Tenant isolation ----------------------------------------------------


@pytest.mark.asyncio
async def test_get_template_returns_not_found_for_wrong_tenant() -> None:
    """A template owned by tenant A is not visible to tenant B's service call.

    The repository ``get_for_tenant`` filters on tenant_id, so a wrong-
    tenant lookup returns None and the service raises NotFoundError —
    no information leaks about the existence of the row.
    """
    service, repo, _ = _make_service()
    tenant_b = TenantId(uuid.uuid4())
    template_id = uuid.uuid4()
    repo.get_for_tenant = AsyncMock(return_value=None)  # filter excludes it

    with pytest.raises(NotFoundError) as excinfo:
        await service.get_template(tenant_b, template_id)

    assert "template not found" in str(excinfo.value)
    repo.get_for_tenant.assert_awaited_once_with(tenant_b, template_id)


@pytest.mark.asyncio
async def test_render_uses_tenant_scoped_lookup() -> None:
    """``render`` MUST go through ``get_for_tenant`` — never an unscoped fetch."""
    service, repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    template = _make_template_row(tenant_id=tenant_id)
    repo.get_for_tenant = AsyncMock(return_value=template)

    # Stub identity + ops reads to produce a usable context without DB.
    person = MagicMock()
    person.id = uuid.uuid4()
    person.given_name = "Frank"
    person.family_name = "Lee"
    person.display_name = "Frank Lee"
    identity = service._identity  # type: ignore[attr-defined]
    identity.get_person = AsyncMock(return_value=person)  # type: ignore[method-assign]
    snapshot = MagicMock()
    snapshot.last_lead_status = None
    ops = service._ops  # type: ignore[attr-defined]
    ops.snapshot = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]

    rendered = await service.render(
        tenant_id,
        template.id,
        person.id,
        principal=_principal(),
    )
    assert "Frank" in rendered.subject
    repo.get_for_tenant.assert_awaited_once_with(tenant_id, template.id)
    # Render audit row was written.
    actions = [c.kwargs["action"] for c in audit.record.await_args_list]
    assert "outreach.template.render" in actions
