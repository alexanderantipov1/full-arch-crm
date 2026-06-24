"""Pydantic DTOs for the outreach domain.

Per ADR-0004 the templates / campaigns / sends / suppression entities
have stable, externally visible shapes. The DTOs here are also the
unit the API and worker pass between layers — never the ORM model
directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Literal types — kept in sync with ``models.TEMPLATE_*`` tuples.
TemplateBodyFormatLiteral = Literal["markdown", "html", "mjml"]
TemplateCategoryLiteral = Literal[
    "marketing",
    "clinical",
    "transactional",
    "operational",
]
TemplateStatusLiteral = Literal["draft", "active", "archived"]

CampaignStatusLiteral = Literal[
    "draft",
    "queued",
    "sending",
    "sent",
    "failed",
    "cancelled",
]
CampaignMailboxStrategyLiteral = Literal["explicit", "auto_route"]

SendStatusLiteral = Literal[
    "queued",
    "sent",
    "bounced",
    "failed",
    "unsubscribed",
    "opened",
]

SuppressionReasonLiteral = Literal[
    "operator",
    "one_click",
    "bounce_hard",
    "complaint",
]

OutboundQueueStatusLiteral = Literal["pending", "locked", "succeeded", "failed"]


# --- Template -------------------------------------------------------------


class TemplateIn(BaseModel):
    """Input for creating a template.

    The service applies ``tracking_enabled`` policy — clinical /
    transactional / operational categories cannot enable tracking, and
    the default for ``marketing`` is also false unless explicitly opted
    in. The DTO accepts whatever the operator submits; the service
    rejects non-compliant combinations.
    """

    name: str = Field(..., min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    subject_template: str = Field(..., min_length=1)
    body_template: str = Field(..., min_length=1)
    body_format: TemplateBodyFormatLiteral = "markdown"
    category: TemplateCategoryLiteral = "marketing"
    tracking_enabled: bool = False
    intent_tags: list[str] = Field(default_factory=list)
    created_by_actor_id: UUID | None = None


class TemplateUpdate(BaseModel):
    """Patch input for updating a template.

    All fields are optional; the service applies the partial update,
    bumps ``version`` if any field actually changed, and re-validates
    the tracking-enabled gate. Use ``None`` to keep an existing value.
    """

    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    subject_template: str | None = Field(default=None, min_length=1)
    body_template: str | None = Field(default=None, min_length=1)
    body_format: TemplateBodyFormatLiteral | None = None
    category: TemplateCategoryLiteral | None = None
    tracking_enabled: bool | None = None
    intent_tags: list[str] | None = None
    status: TemplateStatusLiteral | None = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    subject_template: str
    body_template: str
    body_format: TemplateBodyFormatLiteral
    category: TemplateCategoryLiteral
    tracking_enabled: bool
    intent_tags: list[str]
    version: int
    status: TemplateStatusLiteral
    created_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Campaign -------------------------------------------------------------


class CampaignIn(BaseModel):
    """Input for creating a campaign row.

    The full enqueue + send pipeline lives in ENG-132; ENG-133's
    ``CampaignService.create_campaign`` only persists the row.

    ``recipient_query`` is a query DSL whose shape is owned by
    ENG-132 (the worker that interprets it). The DTO only constrains
    it to be a JSON object; further validation happens at preview /
    enqueue time.
    """

    template_id: UUID
    name: str = Field(..., min_length=1, max_length=240)
    recipient_query: dict[str, object] = Field(default_factory=dict)
    mailbox_credential_id: UUID | None = None
    mailbox_strategy: CampaignMailboxStrategyLiteral = "explicit"
    scheduled_for: datetime | None = None
    created_by_actor_id: UUID | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    template_id: UUID
    name: str
    recipient_query: dict[str, object]
    mailbox_credential_id: UUID | None
    mailbox_strategy: CampaignMailboxStrategyLiteral
    scheduled_for: datetime | None
    sent_count: int
    opened_count: int
    bounced_count: int
    unsubscribed_count: int
    status: CampaignStatusLiteral
    created_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Send -----------------------------------------------------------------


class SendOut(BaseModel):
    """Send-row projection.

    ``campaign_id`` is optional as of ENG-132 — transactional sends
    (``SendService.enqueue_single``) write a send row directly without
    a campaign. Campaign sends always populate the column.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    campaign_id: UUID | None
    person_uid: UUID | None
    recipient_email: str
    message_id: str | None
    mailbox_credential_id: UUID
    status: SendStatusLiteral
    sent_at: datetime | None
    error_text: str | None
    created_at: datetime
    updated_at: datetime


# --- Suppression ----------------------------------------------------------


class SuppressionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    recipient_email_normalised: str
    reason: SuppressionReasonLiteral
    source_send_id: UUID | None
    created_at: datetime


# --- Render output --------------------------------------------------------


class RenderedEmail(BaseModel):
    """Output of ``render_template``.

    The send service fills in the ``List-Unsubscribe`` URL with the
    real ``send_id`` token at enqueue time. The renderer returns the
    header line with a placeholder so the rendered shape is complete
    and previewable in operator tooling.
    """

    subject: str
    body_html: str
    body_text: str
    list_unsubscribe_header: str | None = None


class ValidationIssue(BaseModel):
    """One issue surfaced by ``TemplateService.validate``.

    ``code`` is a stable taxonomy used by the UI to render hints:

    - ``unknown_merge_field`` — placeholder is not on the allowlist
    - ``empty_subject``       — Mustache subject renders to empty
    - ``forbidden_body_format`` — body_format=html (Stage 1 only)
    - ``mjml_unavailable``    — body_format=mjml without engine support
    """

    code: str
    message: str
    location: str  # "subject" | "body"
    field: str | None = None


# --- Person preview (for campaign recipient preview) ---------------------


class PersonPreviewOut(BaseModel):
    """Sparse projection of a person used in the campaign UI preview.

    Deliberately a tiny surface — no PHI, no clinical fields, no notes.
    """

    person_uid: UUID
    display_name: str | None
    primary_email: str | None
