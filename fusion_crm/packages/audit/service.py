"""AuditService — convenience constructors for audit entries.

Used directly by:
  * ``PhiService`` (every PHI access)
  * the tools layer (every agent tool call)
  * the API audit middleware (every authenticated request)
  * the integrations layer (OAuth lifecycle + sync run summaries)

The ``tenant_id`` for each row is sourced from ``Principal.tenant_id`` —
:meth:`Principal.require_tenant` raises if the principal has no tenant
context, which surfaces a wiring bug (a route forgot to depend on
``get_principal_with_tenant``) loudly rather than silently writing an
audit row in the wrong tenant.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.security import Principal
from packages.core.types import PersonUID

from .models import AccessLog
from .repository import AuditRepository

OAuthEvent = Literal["connect", "refresh", "revoke", "error"]
SyncRunOutcome = Literal["success", "partial", "failure", "skipped_credential"]
CatalogReviewAction = Literal["approve", "edit", "reject", "unresolved"]

_CATALOG_REVIEW_ACTIONS: dict[CatalogReviewAction, str] = {
    "approve": "semantic_catalog.review.approve",
    "edit": "semantic_catalog.review.edit",
    "reject": "semantic_catalog.review.reject",
    "unresolved": "semantic_catalog.review.unresolved",
}
_REDACTED = "[redacted]"
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "birth",
        "dob",
        "email",
        "name",
        "note",
        "password",
        "payload",
        "phone",
        "raw",
        "secret",
        "ssn",
        "token",
    }
)


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AuditRepository(session)

    async def record_phi_access(
        self,
        *,
        principal: Principal,
        person_uid: PersonUID,
        action: str,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AccessLog:
        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=person_uid,
            action=action,
            resource="phi",
            reason=reason,
            extra=extra or {},
        )
        return await self._repo.add(entry)

    async def record_tool_call(
        self,
        *,
        principal: Principal,
        tool_name: str,
        person_uid: PersonUID | None = None,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AccessLog:
        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=person_uid,
            action=f"tool.{tool_name}",
            resource="tool",
            reason=reason,
            extra=extra or {},
        )
        return await self._repo.add(entry)

    async def record(
        self,
        *,
        principal: Principal,
        action: str,
        resource: str | None = None,
        person_uid: PersonUID | None = None,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AccessLog:
        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=person_uid,
            action=action,
            resource=resource,
            reason=reason,
            extra=extra or {},
        )
        return await self._repo.add(entry)

    async def log_oauth_event(
        self,
        *,
        principal: Principal,
        provider: str,
        event: OAuthEvent,
        account_id: UUID | None = None,
        outcome: SyncRunOutcome | None = None,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AccessLog:
        """Record an OAuth lifecycle event for an integration account.

        ``provider`` is the provider key (``"salesforce"``, ``"carestack"``,
        ...). ``account_id`` references ``integrations.account.id``; we keep
        it as a plain UUID rather than importing the integrations model to
        preserve domain separation. ``extra`` is merged on top of the
        derived fields, so callers can attach provider-specific context
        without losing the structured ones.
        """
        payload: dict[str, object] = {"provider": provider}
        if account_id is not None:
            payload["account_id"] = str(account_id)
        if outcome is not None:
            payload["outcome"] = outcome
        if extra:
            payload.update(extra)

        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=None,
            action=f"oauth.{event}",
            resource="integration.account",
            reason=reason,
            extra=payload,
        )
        return await self._repo.add(entry)

    async def log_sync_run_summary(
        self,
        *,
        principal: Principal,
        provider: str,
        sync_run_id: UUID,
        outcome: SyncRunOutcome,
        entity_kind: str | None = None,
        item_count: int | None = None,
        error_count: int | None = None,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> AccessLog:
        """Record completion of a provider sync run.

        Written once per ``integrations.sync_run`` row, when the run
        terminates (``outcome`` ∈ {success, partial, failure}). The summary
        is the audit-side mirror of the operational sync_run row — the
        sync_run row stores live execution state, this row is the
        append-only accountability record.
        """
        payload: dict[str, object] = {
            "provider": provider,
            "sync_run_id": str(sync_run_id),
            "outcome": outcome,
        }
        if entity_kind is not None:
            payload["entity_kind"] = entity_kind
        if item_count is not None:
            payload["item_count"] = item_count
        if error_count is not None:
            payload["error_count"] = error_count
        if extra:
            payload.update(extra)

        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=None,
            action="integrations.sync_run.complete",
            resource="integration.sync_run",
            reason=reason,
            extra=payload,
        )
        return await self._repo.add(entry)

    async def log_catalog_review_action(
        self,
        *,
        principal: Principal,
        review_action: CatalogReviewAction,
        proposal_id: UUID | str,
        reason: str,
        catalog_version_id: UUID | str | None = None,
        previous_catalog_version_id: UUID | str | None = None,
        target_status: str | None = None,
        changed_fields: Sequence[str] | None = None,
        affected_analytics: Sequence[str] | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> AccessLog:
        """Record a semantic catalog proposal review decision.

        The row intentionally stores IDs and review metadata only. Raw source
        values, provider payloads, secrets, reviewer notes, and PII-like fields
        are redacted from ``extra`` before the append-only audit row is built.
        """
        payload: dict[str, object] = {
            "proposal_id": str(proposal_id),
            "review_action": review_action,
        }
        if catalog_version_id is not None:
            payload["catalog_version_id"] = str(catalog_version_id)
        if previous_catalog_version_id is not None:
            payload["previous_catalog_version_id"] = str(previous_catalog_version_id)
        if target_status is not None:
            payload["target_status"] = target_status
        if changed_fields:
            payload["changed_fields"] = list(changed_fields)
        if affected_analytics:
            payload["affected_analytics"] = list(affected_analytics)
        if extra:
            payload.update(_redact_sensitive_audit_extra(extra))

        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=None,
            action=_CATALOG_REVIEW_ACTIONS[review_action],
            resource="semantic_catalog.proposal",
            reason=reason,
            extra=payload,
        )
        return await self._repo.add(entry)

    async def log_catalog_version_change(
        self,
        *,
        principal: Principal,
        catalog_version_id: UUID | str,
        previous_catalog_version_id: UUID | str | None,
        metric_id: str,
        change_summary: str,
        reason: str,
        changed_fields: Sequence[str] | None = None,
        affected_analytics: Sequence[str] | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> AccessLog:
        """Record why an approved catalog version changed a metric.

        This gives the future catalog-version storage service a stable audit
        side channel while ENG-314/ENG-315 storage contracts are still landing.
        """
        payload: dict[str, object] = {
            "catalog_version_id": str(catalog_version_id),
            "metric_id": metric_id,
            "change_summary": change_summary,
            "change_reason": reason,
        }
        if previous_catalog_version_id is not None:
            payload["previous_catalog_version_id"] = str(previous_catalog_version_id)
        if changed_fields:
            payload["changed_fields"] = list(changed_fields)
        if affected_analytics:
            payload["affected_analytics"] = list(affected_analytics)
        if extra:
            payload.update(_redact_sensitive_audit_extra(extra))

        entry = AccessLog(
            tenant_id=principal.require_tenant(),
            principal_id=principal.id,
            principal_email=principal.email,
            person_uid=None,
            action="semantic_catalog.version.change",
            resource="semantic_catalog.version",
            reason=reason,
            extra=payload,
        )
        return await self._repo.add(entry)


def explain_catalog_metric_change(version_history: Mapping[str, object]) -> str:
    """Return a concise human-readable explanation for metric drift."""
    metric_id = _string_or_unknown(version_history.get("metric_id"), "metric")
    catalog_version_id = _string_or_unknown(
        version_history.get("catalog_version_id"), "unknown version"
    )
    previous_catalog_version_id = version_history.get("previous_catalog_version_id")
    change_summary = _string_or_unknown(
        version_history.get("change_summary"), "Catalog definition changed"
    )
    change_reason = _string_or_unknown(
        version_history.get("change_reason") or version_history.get("reason"),
        "No reason recorded",
    )
    changed_fields = version_history.get("changed_fields")

    version_part = (
        f"{previous_catalog_version_id} -> {catalog_version_id}"
        if previous_catalog_version_id
        else catalog_version_id
    )
    fields_part = ""
    if isinstance(changed_fields, Sequence) and not isinstance(changed_fields, str):
        fields = [str(field) for field in changed_fields if field]
        if fields:
            fields_part = f" Changed fields: {', '.join(fields)}."

    return (
        f"{metric_id} changed in catalog version {version_part}: "
        f"{change_summary}. Reason: {change_reason}.{fields_part}"
    )


def _redact_sensitive_audit_extra(extra: Mapping[str, object]) -> dict[str, object]:
    return {key: _redact_value(key, value) for key, value in extra.items()}


def _redact_value(key: str, value: object) -> object:
    if _is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {
            str(child_key): _redact_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_redact_value(key, item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalised = key.lower()
    return any(part in normalised for part in _SENSITIVE_KEY_PARTS)


def _string_or_unknown(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
