"""Outreach services — public surface for templates, campaigns, suppression.

Per ``packages/CLAUDE.md`` outreach may import:

- ``packages.core``    — config, exceptions, logging, types, security
- ``packages.identity`` — read-only via ``IdentityService``
- ``packages.ops``     — read-only via ``OpsService``
- ``packages.audit``   — write-only via ``AuditService``

It does NOT import ``phi``, ``actor``, ``auth``, ``integrations``, or
the tenant ORM models. Tenant credential references stay as plain
UUIDs (``mailbox_credential_id``); the send pipeline (ENG-132) is
the one that joins them through ``IntegrationCredentialService``.

Audit policy: every state change AND every render writes an
``audit.access_log`` row. The render row carries ``template_id`` +
``person_uid`` + outcome, never the rendered subject / body.

Tenant isolation: every read goes through ``_for_tenant`` repository
methods; service entry points take ``tenant_id: TenantId`` and
forward it. A template from tenant A cannot be rendered for tenant B
because the lookup filter excludes the row.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import ConflictError, NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.service import IdentityService, normalise_email
from packages.ops.service import OpsService

from .models import (
    CAMPAIGN_MAILBOX_STRATEGIES,
    SUPPRESSION_REASONS,
    TEMPLATE_BODY_FORMATS,
    TEMPLATE_CATEGORIES,
    TEMPLATE_STATUSES,
    TRACKING_FORBIDDEN_CATEGORIES,
    Campaign,
    Suppression,
    Template,
    TemplateStatus,
)
from .render import (
    PersonRenderContext,
    render_with_trace,
)
from .repository import (
    CampaignRepository,
    SuppressionRepository,
    TemplateRepository,
)
from .schemas import (
    CampaignIn,
    CampaignOut,
    PersonPreviewOut,
    RenderedEmail,
    SuppressionOut,
    TemplateIn,
    TemplateOut,
    TemplateUpdate,
    ValidationIssue,
)

log = get_logger("outreach.service")


# Audit action codes (per ENG-133 spec).
AUDIT_TEMPLATE_CREATE = "outreach.template.create"
AUDIT_TEMPLATE_UPDATE = "outreach.template.update"
AUDIT_TEMPLATE_ARCHIVE = "outreach.template.archive"
AUDIT_TEMPLATE_RENDER = "outreach.template.render"
AUDIT_TEMPLATE_MERGE_FIELD_UNKNOWN = "outreach.template.merge_field_unknown"
AUDIT_CAMPAIGN_CREATE = "outreach.campaign.create"
AUDIT_SUPPRESSION_ADD = "outreach.suppression.add"
AUDIT_SUPPRESSION_REMOVE = "outreach.suppression.remove"

# ENG-134 — tracking surface audit codes.
AUDIT_EMAIL_OPENED = "outreach.email.opened"
AUDIT_EMAIL_UNSUBSCRIBED = "outreach.email.unsubscribed"
AUDIT_EMAIL_BOUNCED = "outreach.email.bounced"


class TemplateService:
    """Public surface for outreach templates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TemplateRepository(session)
        self._audit = AuditService(session)
        self._identity = IdentityService(session)
        self._ops = OpsService(session)

    # --- Reads ---

    async def get_template(
        self, tenant_id: TenantId, template_id: UUID
    ) -> Template:
        template = await self._repo.get_for_tenant(tenant_id, template_id)
        if template is None:
            raise NotFoundError(
                "template not found",
                details={
                    "tenant_id": str(tenant_id),
                    "template_id": str(template_id),
                },
            )
        return template

    async def list_templates(
        self,
        tenant_id: TenantId,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Template]:
        if status is not None and status not in TEMPLATE_STATUSES:
            raise ValidationError(
                "unknown template status",
                details={"status": status, "allowed": list(TEMPLATE_STATUSES)},
            )
        return await self._repo.list_for_tenant(
            tenant_id, status=status, limit=limit
        )

    # --- Writes ---

    async def create_template(
        self,
        tenant_id: TenantId,
        payload: TemplateIn,
        *,
        principal: Principal,
    ) -> TemplateOut:
        """Create a new template under ``tenant_id``.

        Enforces:
        - ``body_format`` ∈ {markdown, mjml} (html rejected in Stage 1)
        - tracking_enabled gate (forbidden for clinical / transactional /
          operational categories)
        - ``(tenant_id, name)`` uniqueness — ConflictError on dupe.
        """
        self._validate_body_format(payload.body_format)
        self._validate_category_and_tracking(
            payload.category, payload.tracking_enabled
        )

        existing = await self._repo.find_by_name(tenant_id, payload.name)
        if existing is not None:
            raise ConflictError(
                "template name already in use for this tenant",
                details={
                    "tenant_id": str(tenant_id),
                    "name": payload.name,
                    "template_id": str(existing.id),
                },
            )

        template = Template(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            subject_template=payload.subject_template,
            body_template=payload.body_template,
            body_format=payload.body_format,
            category=payload.category,
            tracking_enabled=payload.tracking_enabled,
            intent_tags=list(payload.intent_tags),
            version=1,
            status=TemplateStatus.DRAFT.value,
            created_by_actor_id=payload.created_by_actor_id,
        )
        await self._repo.add(template)
        await self._audit.record(
            principal=principal,
            action=AUDIT_TEMPLATE_CREATE,
            resource="outreach.template",
            extra={
                "tenant_id": str(tenant_id),
                "template_id": str(template.id),
                "category": template.category,
                "body_format": template.body_format,
                "tracking_enabled": template.tracking_enabled,
            },
        )
        return TemplateOut.model_validate(template)

    async def update_template(
        self,
        tenant_id: TenantId,
        template_id: UUID,
        payload: TemplateUpdate,
        *,
        principal: Principal,
    ) -> TemplateOut:
        """Apply a partial update; bumps ``version`` on any actual change.

        Per ENG-133 we do not track full version history (each update
        overwrites the row); the version counter signals to outside
        observers that a change has occurred. Future stages may snapshot
        prior versions into ``outreach.template_history``.
        """
        template = await self.get_template(tenant_id, template_id)

        new_body_format = payload.body_format or template.body_format
        new_category = payload.category or template.category
        new_tracking = (
            payload.tracking_enabled
            if payload.tracking_enabled is not None
            else template.tracking_enabled
        )
        self._validate_body_format(new_body_format)
        self._validate_category_and_tracking(new_category, new_tracking)

        if payload.status is not None and payload.status not in TEMPLATE_STATUSES:
            raise ValidationError(
                "unknown template status",
                details={
                    "status": payload.status,
                    "allowed": list(TEMPLATE_STATUSES),
                },
            )

        if payload.name is not None and payload.name != template.name:
            collision = await self._repo.find_by_name(tenant_id, payload.name)
            if collision is not None and collision.id != template.id:
                raise ConflictError(
                    "template name already in use for this tenant",
                    details={
                        "tenant_id": str(tenant_id),
                        "name": payload.name,
                    },
                )

        changed = False
        if payload.name is not None and payload.name != template.name:
            template.name = payload.name
            changed = True
        if (
            payload.description is not None
            and payload.description != template.description
        ):
            template.description = payload.description
            changed = True
        if (
            payload.subject_template is not None
            and payload.subject_template != template.subject_template
        ):
            template.subject_template = payload.subject_template
            changed = True
        if (
            payload.body_template is not None
            and payload.body_template != template.body_template
        ):
            template.body_template = payload.body_template
            changed = True
        if (
            payload.body_format is not None
            and payload.body_format != template.body_format
        ):
            template.body_format = payload.body_format
            changed = True
        if payload.category is not None and payload.category != template.category:
            template.category = payload.category
            changed = True
        if (
            payload.tracking_enabled is not None
            and payload.tracking_enabled != template.tracking_enabled
        ):
            template.tracking_enabled = payload.tracking_enabled
            changed = True
        if (
            payload.intent_tags is not None
            and list(payload.intent_tags) != list(template.intent_tags)
        ):
            template.intent_tags = list(payload.intent_tags)
            changed = True
        if payload.status is not None and payload.status != template.status:
            template.status = payload.status
            changed = True

        if changed:
            template.version = template.version + 1

        await self._audit.record(
            principal=principal,
            action=AUDIT_TEMPLATE_UPDATE,
            resource="outreach.template",
            extra={
                "tenant_id": str(tenant_id),
                "template_id": str(template.id),
                "version": template.version,
                "changed": changed,
            },
        )
        return TemplateOut.model_validate(template)

    async def delete_template(
        self,
        tenant_id: TenantId,
        template_id: UUID,
        *,
        principal: Principal,
    ) -> TemplateOut:
        """Soft-delete: flip ``status`` to ``archived`` (no row removal)."""
        template = await self.get_template(tenant_id, template_id)
        if template.status != TemplateStatus.ARCHIVED.value:
            template.status = TemplateStatus.ARCHIVED.value
            template.version = template.version + 1
        await self._audit.record(
            principal=principal,
            action=AUDIT_TEMPLATE_ARCHIVE,
            resource="outreach.template",
            extra={
                "tenant_id": str(tenant_id),
                "template_id": str(template.id),
            },
        )
        return TemplateOut.model_validate(template)

    # --- Render + validate ---

    async def render(
        self,
        tenant_id: TenantId,
        template_id: UUID,
        person_uid: PersonUID,
        *,
        principal: Principal,
    ) -> RenderedEmail:
        """Render ``template_id`` against ``person_uid``.

        Composes the ``PersonRenderContext`` from ``IdentityService`` +
        ``OpsService`` reads (PHI-free), runs the renderer, then writes
        a ``outreach.template.render`` audit row plus one
        ``outreach.template.merge_field_unknown`` row per unknown
        placeholder. The rendered body / subject are NEVER logged.
        """
        template = await self.get_template(tenant_id, template_id)
        context = await self._build_render_context(tenant_id, person_uid)
        rendered, trace = render_with_trace(
            TemplateOut.model_validate(template), context
        )

        await self._audit.record(
            principal=principal,
            action=AUDIT_TEMPLATE_RENDER,
            resource="outreach.template",
            person_uid=person_uid,
            extra={
                "tenant_id": str(tenant_id),
                "template_id": str(template_id),
                "version": template.version,
                "category": template.category,
                "body_format": template.body_format,
                "empty_subject": trace.empty_subject,
                "unknown_field_count": len(trace.unknown_fields),
            },
        )
        for unknown in trace.unknown_fields:
            await self._audit.record(
                principal=principal,
                action=AUDIT_TEMPLATE_MERGE_FIELD_UNKNOWN,
                resource="outreach.template",
                person_uid=person_uid,
                extra={
                    "tenant_id": str(tenant_id),
                    "template_id": str(template_id),
                    "field": unknown,
                },
            )
        return rendered

    async def validate(
        self,
        tenant_id: TenantId,
        template_id: UUID,
    ) -> list[ValidationIssue]:
        """Dry-run validation for the operator UI.

        Renders the template against a synthetic context, surfaces
        unknown merge fields and obvious template defects (empty
        subject, forbidden body format). No audit row written —
        validate is informational and may be called repeatedly while
        the operator types.
        """
        template = await self.get_template(tenant_id, template_id)
        issues: list[ValidationIssue] = []

        if template.body_format == "html":
            issues.append(
                ValidationIssue(
                    code="forbidden_body_format",
                    message="body_format='html' is forbidden in Stage 1",
                    location="body",
                )
            )
            return issues

        if template.body_format == "mjml":
            # Surface this as a soft signal rather than a hard error —
            # the renderer falls back to the inline-CSS HTML envelope.
            try:  # pragma: no cover — environment guard
                import mjml  # type: ignore[import-not-found]  # noqa: F401
            except Exception:  # noqa: BLE001
                issues.append(
                    ValidationIssue(
                        code="mjml_unavailable",
                        message=(
                            "mjml-python is not installed; the renderer will "
                            "fall back to an inline-CSS HTML envelope."
                        ),
                        location="body",
                    )
                )

        synthetic = _synthetic_render_context()
        rendered, trace = render_with_trace(
            TemplateOut.model_validate(template), synthetic
        )
        if trace.empty_subject or not rendered.subject.strip():
            issues.append(
                ValidationIssue(
                    code="empty_subject",
                    message=(
                        "Subject renders to an empty string against the "
                        "synthetic preview context."
                    ),
                    location="subject",
                )
            )
        for unknown in trace.unknown_fields:
            issues.append(
                ValidationIssue(
                    code="unknown_merge_field",
                    message=(
                        f"Placeholder '{unknown}' is not on the merge-field "
                        "allowlist; it will render as empty."
                    ),
                    location=(
                        "subject"
                        if unknown in template.subject_template
                        else "body"
                    ),
                    field=unknown,
                )
            )
        return issues

    # --- Private helpers ---

    @staticmethod
    def _validate_body_format(body_format: str) -> None:
        if body_format not in TEMPLATE_BODY_FORMATS:
            raise ValidationError(
                "unknown body_format",
                details={
                    "body_format": body_format,
                    "allowed": list(TEMPLATE_BODY_FORMATS),
                },
            )
        if body_format == "html":
            raise ValidationError(
                "body_format='html' is forbidden in Stage 1 outreach templates",
                details={"body_format": body_format},
            )

    @staticmethod
    def _validate_category_and_tracking(
        category: str,
        tracking_enabled: bool,
    ) -> None:
        if category not in TEMPLATE_CATEGORIES:
            raise ValidationError(
                "unknown category",
                details={
                    "category": category,
                    "allowed": list(TEMPLATE_CATEGORIES),
                },
            )
        if tracking_enabled and category in TRACKING_FORBIDDEN_CATEGORIES:
            raise ValidationError(
                "tracking_enabled is forbidden for this category",
                details={
                    "category": category,
                    "tracking_enabled": tracking_enabled,
                    "forbidden": sorted(TRACKING_FORBIDDEN_CATEGORIES),
                },
            )

    async def _build_render_context(
        self,
        tenant_id: TenantId,
        person_uid: PersonUID,
    ) -> PersonRenderContext:
        """Compose a PersonRenderContext from identity + ops reads.

        PHI is never read here. Identity carries display + given/family
        names; ops carries the most recent lead status / source. The
        appointment / location / tenant fields are left null in
        Stage 1 — the campaign-time enricher (ENG-132) fills them in
        when ENG-134 ships the appointment view.
        """
        person = await self._identity.get_person(person_uid)
        snapshot = await self._ops.snapshot(person_uid)

        return PersonRenderContext(
            patient_first_name=person.given_name,
            patient_last_name=person.family_name,
            patient_full_name=person.display_name,
            lead_status=(
                snapshot.last_lead_status.value
                if snapshot.last_lead_status is not None
                else None
            ),
            lead_source=None,
            appointment_date=None,
            appointment_time=None,
            appointment_location_name=None,
            location_name=None,
            location_address=None,
            location_phone=None,
            tenant_name=None,
        )


# --- Campaign service (minimal; full pipeline lives in ENG-132) ----------


class CampaignService:
    """Public surface for outreach campaigns (Stage 1 minimal).

    Only what the templates feature needs:
    - ``create_campaign`` — persists the row
    - ``preview_recipient_query`` — returns the first N matches for
      the operator UI preview pane
    - ``get_campaign`` / ``list_campaigns`` — basic reads

    The send pipeline (queue enqueue, dispatcher, NDR parser, tracking
    pixel, unsubscribe handler) lives in ENG-132.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CampaignRepository(session)
        self._template_repo = TemplateRepository(session)
        self._audit = AuditService(session)
        self._identity = IdentityService(session)

    async def get_campaign(
        self, tenant_id: TenantId, campaign_id: UUID
    ) -> Campaign:
        campaign = await self._repo.get_for_tenant(tenant_id, campaign_id)
        if campaign is None:
            raise NotFoundError(
                "campaign not found",
                details={
                    "tenant_id": str(tenant_id),
                    "campaign_id": str(campaign_id),
                },
            )
        return campaign

    async def list_campaigns(
        self,
        tenant_id: TenantId,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Campaign]:
        return await self._repo.list_for_tenant(
            tenant_id, status=status, limit=limit
        )

    async def create_campaign(
        self,
        tenant_id: TenantId,
        payload: CampaignIn,
        *,
        principal: Principal,
    ) -> CampaignOut:
        if payload.mailbox_strategy not in CAMPAIGN_MAILBOX_STRATEGIES:
            raise ValidationError(
                "unknown mailbox_strategy",
                details={
                    "mailbox_strategy": payload.mailbox_strategy,
                    "allowed": list(CAMPAIGN_MAILBOX_STRATEGIES),
                },
            )
        if (
            payload.mailbox_strategy == "explicit"
            and payload.mailbox_credential_id is None
        ):
            raise ValidationError(
                "mailbox_credential_id is required when "
                "mailbox_strategy='explicit'",
                details={"mailbox_strategy": payload.mailbox_strategy},
            )

        # Ensure the template belongs to this tenant before referencing it.
        template = await self._template_repo.get_for_tenant(
            tenant_id, payload.template_id
        )
        if template is None:
            raise NotFoundError(
                "template not found for tenant",
                details={
                    "tenant_id": str(tenant_id),
                    "template_id": str(payload.template_id),
                },
            )

        campaign = Campaign(
            tenant_id=tenant_id,
            template_id=template.id,
            name=payload.name,
            recipient_query=dict(payload.recipient_query),
            mailbox_credential_id=payload.mailbox_credential_id,
            mailbox_strategy=payload.mailbox_strategy,
            scheduled_for=payload.scheduled_for,
            created_by_actor_id=payload.created_by_actor_id,
        )
        await self._repo.add(campaign)
        await self._audit.record(
            principal=principal,
            action=AUDIT_CAMPAIGN_CREATE,
            resource="outreach.campaign",
            extra={
                "tenant_id": str(tenant_id),
                "campaign_id": str(campaign.id),
                "template_id": str(template.id),
                "mailbox_strategy": campaign.mailbox_strategy,
                "scheduled": campaign.scheduled_for is not None,
            },
        )
        return CampaignOut.model_validate(campaign)

    async def preview_recipient_query(
        self,
        tenant_id: TenantId,
        query: dict[str, Any],
        *,
        limit: int = 10,
    ) -> list[PersonPreviewOut]:
        """Return the first N matches for the operator preview pane.

        Stage 1 query DSL is intentionally minimal — ENG-132 owns the
        full grammar. We only support a flat ``filter`` map with
        identifier-based lookups (``email``) and return the resolved
        person, if any. Unknown filter keys are ignored (forwards-
        compatible with the future grammar).
        """
        results: list[PersonPreviewOut] = []
        if not isinstance(query, dict):
            raise ValidationError(
                "recipient_query must be a JSON object",
                details={"got": type(query).__name__},
            )
        filt = query.get("filter") or {}
        if not isinstance(filt, dict):
            raise ValidationError(
                "recipient_query.filter must be a JSON object",
                details={"got": type(filt).__name__},
            )

        emails = filt.get("emails")
        if isinstance(emails, list):
            for email in emails[:limit]:
                if not isinstance(email, str):
                    continue
                try:
                    person = await self._identity.resolve_by_email(email)
                except ValidationError:
                    continue
                if person is None:
                    continue
                # Pick a primary email from the identifiers list.
                primary_email = next(
                    (
                        i.value
                        for i in person.identifiers
                        if i.kind == "email"
                    ),
                    None,
                )
                results.append(
                    PersonPreviewOut(
                        person_uid=person.id,
                        display_name=person.display_name,
                        primary_email=primary_email,
                    )
                )

        return results[:limit]


# --- Suppression service -------------------------------------------------


class SuppressionService:
    """Per-tenant suppression list (ADR-0004 §"Unsubscribe").

    The send pipeline (ENG-132) calls ``is_suppressed`` before
    enqueuing. The tracking + bounce handlers (ENG-134) call
    ``add_suppression`` to record one-click / bounce / complaint
    events. Operators may manually add or remove entries through the
    UI; both write audit.

    ENG-134 surface additions:

    - ``add_suppression`` is idempotent on the primary key — a re-
      submission with the same email returns the existing row
      without writing a duplicate audit entry.
    - ``list_for_tenant`` exposes a paginated read for the operator
      settings UI (ENG-135) and for the unsubscribe form's
      confirmation page.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SuppressionRepository(session)
        self._audit = AuditService(session)

    async def add_suppression(
        self,
        tenant_id: TenantId,
        email: str,
        reason: str,
        *,
        principal: Principal,
        source_send_id: UUID | None = None,
    ) -> SuppressionOut:
        if reason not in SUPPRESSION_REASONS:
            raise ValidationError(
                "unknown suppression reason",
                details={
                    "reason": reason,
                    "allowed": list(SUPPRESSION_REASONS),
                },
            )
        normalised = normalise_email(email)
        existing = await self._repo.get(tenant_id, normalised)
        if existing is not None:
            # Idempotent: caller may retry the unsubscribe / bounce
            # path without inflating the audit trail with duplicates.
            return SuppressionOut.model_validate(existing)

        row = Suppression(
            tenant_id=tenant_id,
            recipient_email_normalised=normalised,
            reason=reason,
            source_send_id=source_send_id,
        )
        await self._repo.add(row)
        await self._audit.record(
            principal=principal,
            action=AUDIT_SUPPRESSION_ADD,
            resource="outreach.suppression",
            extra={
                "tenant_id": str(tenant_id),
                "reason": reason,
                "has_source_send_id": source_send_id is not None,
            },
        )
        return SuppressionOut.model_validate(row)

    async def is_suppressed(
        self, tenant_id: TenantId, email_normalised: str
    ) -> bool:
        """Return True if ``(tenant_id, email_normalised)`` is suppressed.

        ``email_normalised`` MUST already be lowercased / trimmed (the
        caller is the send service, which normalises once at enqueue).
        """
        row = await self._repo.get(tenant_id, email_normalised)
        return row is not None

    async def remove_suppression(
        self,
        tenant_id: TenantId,
        email: str,
        *,
        principal: Principal,
    ) -> bool:
        normalised = normalise_email(email)
        deleted = await self._repo.delete_for(tenant_id, normalised)
        if deleted:
            await self._audit.record(
                principal=principal,
                action=AUDIT_SUPPRESSION_REMOVE,
                resource="outreach.suppression",
                extra={"tenant_id": str(tenant_id)},
            )
        return deleted

    async def list_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SuppressionOut]:
        """Paginated list of suppressions for the operator settings UI.

        ENG-135 uses this to populate the "Suppressions" table; ENG-134
        ships it so the unsubscribe / bounce signals are visible end-
        to-end as soon as they land. No audit (reads only).
        """
        rows = await self._repo.list_for_tenant(
            tenant_id, limit=limit, offset=offset
        )
        return [SuppressionOut.model_validate(r) for r in rows]


# --- Helpers -------------------------------------------------------------


def _synthetic_render_context() -> PersonRenderContext:
    """A populated context used by ``TemplateService.validate``.

    Every allowlist field is filled so the renderer cannot accidentally
    flag a known field as missing during validation. Real renders use
    a context built from real data; this is preview-only.
    """
    from datetime import date as _date
    from datetime import time as _time

    return PersonRenderContext(
        patient_first_name="Sample",
        patient_last_name="Person",
        patient_full_name="Sample Person",
        lead_status="qualified",
        lead_source="Web",
        appointment_date=_date(2026, 6, 1),
        appointment_time=_time(9, 30),
        appointment_location_name="Galleria Office",
        location_name="Galleria Office",
        location_address="123 Main St, Houston, TX",
        location_phone="555-555-0100",
        tenant_name="Galleria Dental",
    )


# Public surface re-exports for callers that want to import service-level
# names without reaching into the schemas / models modules.
__all__ = [
    "AUDIT_CAMPAIGN_CREATE",
    "AUDIT_EMAIL_BOUNCED",
    "AUDIT_EMAIL_OPENED",
    "AUDIT_EMAIL_UNSUBSCRIBED",
    "AUDIT_SUPPRESSION_ADD",
    "AUDIT_SUPPRESSION_REMOVE",
    "AUDIT_TEMPLATE_ARCHIVE",
    "AUDIT_TEMPLATE_CREATE",
    "AUDIT_TEMPLATE_MERGE_FIELD_UNKNOWN",
    "AUDIT_TEMPLATE_RENDER",
    "AUDIT_TEMPLATE_UPDATE",
    "CampaignService",
    "PersonRenderContext",
    "SuppressionService",
    "TemplateService",
]
