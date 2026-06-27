"""IntegrationService — public surface for the integrations domain.

Skeleton with the operations needed by:

* ``apps/api/routers/integrations/*`` — connect / disconnect / status
* ``apps/worker/jobs/*`` — sync run lifecycle, CDC cursor
* Provider subpackages (``packages/integrations/<provider>/``)

Provider-specific details (PKCE flow, REST clients, sync loops) live in the
subpackages and call back into this service.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument (ENG-128). The wiring layer resolves the tenant from
``Principal.tenant_id`` and forwards it.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import NotFoundError
from packages.core.security import Principal
from packages.core.types import TenantId

from .models import (
    GLOBAL_COMPANY_UID,
    CDCCursor,
    IntegrationAccount,
    SyncRun,
)
from .repository import IntegrationsRepository
from .schemas import (
    AccountStatus,
    IntegrationAccountIn,
    SyncRunIn,
    SyncRunUpdate,
)

ProviderSyncStatus = Literal[
    "succeeded", "partial", "failed", "skipped_credential"
]

_ERROR_REDACTIONS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(access[_-]?token=)[^,\s]+", re.IGNORECASE),
    re.compile(r"(refresh[_-]?token=)[^,\s]+", re.IGNORECASE),
    re.compile(r"(client[_-]?secret=)[^,\s]+", re.IGNORECASE),
    re.compile(r"(password=)[^,\s]+", re.IGNORECASE),
    re.compile(r"(authorization:\s*bearer\s+)[^,\s]+", re.IGNORECASE),
)


class IntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IntegrationsRepository(session)
        self._audit = AuditService(session)

    # --- account lifecycle ---

    async def upsert_account(
        self, tenant_id: TenantId, payload: IntegrationAccountIn
    ) -> IntegrationAccount:
        """Create or update an account for ``(provider, company_uid)``.

        Idempotent. Caller (boundary) commits.
        """
        company_uid = payload.company_uid or GLOBAL_COMPANY_UID
        existing = await self._repo.find_account(
            tenant_id, payload.provider, company_uid
        )

        if existing is None:
            account = IntegrationAccount(
                tenant_id=tenant_id,
                provider=payload.provider,
                company_uid=company_uid,
                status=payload.status,
                access_token=payload.access_token,
                refresh_token=payload.refresh_token,
                token_expires_at=payload.token_expires_at,
                scopes=list(payload.scopes),
                meta=dict(payload.meta),
            )
            return await self._repo.add_account(account)

        existing.status = payload.status
        if payload.access_token is not None:
            existing.access_token = payload.access_token
        if payload.refresh_token is not None:
            existing.refresh_token = payload.refresh_token
        existing.token_expires_at = payload.token_expires_at
        existing.scopes = list(payload.scopes)
        # Merge ``meta`` rather than replace so callers can patch one key.
        merged = dict(existing.meta or {})
        merged.update(payload.meta)
        existing.meta = merged
        return existing

    async def disconnect(
        self, tenant_id: TenantId, account_id: UUID
    ) -> IntegrationAccount:
        """Mark account ``disconnected`` and clear tokens. Audit at boundary."""
        account = await self._repo.get_account(tenant_id, account_id)
        if account is None:
            raise NotFoundError("integration_account not found", details={"id": str(account_id)})
        account.status = "disconnected"
        account.access_token = None
        account.refresh_token = None
        account.token_expires_at = None
        return account

    async def get_account(
        self, tenant_id: TenantId, account_id: UUID
    ) -> IntegrationAccount:
        account = await self._repo.get_account(tenant_id, account_id)
        if account is None:
            raise NotFoundError("integration_account not found", details={"id": str(account_id)})
        return account

    async def get_account_by_provider(
        self,
        tenant_id: TenantId,
        provider: str,
        company_uid: UUID | None = None,
    ) -> IntegrationAccount | None:
        return await self._repo.find_account(
            tenant_id, provider, company_uid or GLOBAL_COMPANY_UID
        )

    # --- sync runs ---

    async def open_sync_run(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        payload: SyncRunIn,
    ) -> SyncRun:
        run = SyncRun(
            tenant_id=tenant_id,
            account_id=account_id,
            sf_object=payload.sf_object,
            direction=payload.direction,
            status="running",
            meta=dict(payload.meta),
        )
        return await self._repo.add_sync_run(run)

    async def open_provider_sync_run(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        object_scope: str,
        trigger: str,
        account_status: AccountStatus = "connected",
        meta: dict[str, object] | None = None,
    ) -> SyncRun:
        """Open a provider-level inbound sync run.

        Runtime credentials for Salesforce and CareStack live in
        ``tenant.integration_credential``. ``integration_account`` is kept as
        the historical parent row for ``sync_run`` only; no credential payload
        is copied into this domain.
        """
        account = await self.upsert_account(
            tenant_id,
            IntegrationAccountIn(
                provider=provider,
                company_uid=GLOBAL_COMPANY_UID,
                status=account_status,
                meta={"credential_source": "tenant.integration_credential"},
            ),
        )
        run_meta: dict[str, object] = {
            "provider": provider,
            "object_scope": object_scope,
            "trigger": trigger,
        }
        if meta:
            run_meta.update(meta)
        return await self.open_sync_run(
            tenant_id,
            account.id,
            SyncRunIn(
                sf_object=object_scope,
                direction="inbound",
                meta=run_meta,
            ),
        )

    async def close_sync_run(
        self,
        tenant_id: TenantId,
        sync_run_id: UUID,
        update: SyncRunUpdate,
    ) -> SyncRun:
        run = await self._repo.get_sync_run(tenant_id, sync_run_id)
        if run is None:
            raise NotFoundError("sync_run not found", details={"id": str(sync_run_id)})
        run.status = update.status
        if update.records_total is not None:
            run.records_total = update.records_total
        if update.records_succeeded is not None:
            run.records_succeeded = update.records_succeeded
        if update.records_failed is not None:
            run.records_failed = update.records_failed
        if update.error is not None:
            run.error = update.error
        if update.meta is not None:
            merged = dict(run.meta or {})
            merged.update(update.meta)
            run.meta = merged
        run.finished_at = (
            datetime.now(tz=run.started_at.tzinfo)
            if run.started_at.tzinfo
            else datetime.utcnow()
        )
        return run

    async def close_provider_sync_run(
        self,
        tenant_id: TenantId,
        *,
        sync_run_id: UUID,
        principal: Principal,
        provider: str,
        object_scope: str,
        status: ProviderSyncStatus,
        records_total: int,
        records_succeeded: int,
        records_failed: int,
        error: BaseException | str | None = None,
        meta: dict[str, object] | None = None,
    ) -> SyncRun:
        """Close a provider sync run and write the audit summary row."""
        error_summary = summarize_sync_error(error)
        run = await self.close_sync_run(
            tenant_id,
            sync_run_id,
            SyncRunUpdate(
                status=status,
                records_total=records_total,
                records_succeeded=records_succeeded,
                records_failed=records_failed,
                error=error_summary,
                meta=meta,
            ),
        )
        await self._audit.log_sync_run_summary(
            principal=principal,
            provider=provider,
            sync_run_id=sync_run_id,
            outcome=_audit_outcome(status),
            entity_kind=object_scope,
            item_count=records_total,
            error_count=records_failed,
            reason=error_summary,
            extra={"status": status},
        )
        return run

    async def list_recent_runs(
        self, tenant_id: TenantId, account_id: UUID, limit: int = 20
    ) -> list[SyncRun]:
        return await self._repo.list_recent_runs(
            tenant_id, account_id, limit=limit
        )

    async def list_latest_runs_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        provider: str | None = None,
        limit: int = 20,
    ) -> list[tuple[SyncRun, str]]:
        """Return latest sync runs with provider labels for dashboards."""
        return await self._repo.list_latest_runs_for_tenant(
            tenant_id,
            provider=provider,
            limit=limit,
        )

    # --- CDC cursor ---

    async def bump_cdc_cursor(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        channel: str,
        replay_id: int,
    ) -> CDCCursor:
        existing = await self._repo.find_cursor(tenant_id, account_id, channel)
        if existing is None:
            cursor = CDCCursor(
                tenant_id=tenant_id,
                account_id=account_id,
                channel=channel,
                replay_id=replay_id,
            )
            return await self._repo.add_cursor(cursor)
        existing.replay_id = replay_id
        return existing


def summarize_sync_error(error: BaseException | str | None) -> str | None:
    """Return a short, credential-safe provider error summary."""
    if error is None:
        return None
    if isinstance(error, BaseException):
        raw = f"{error.__class__.__name__}: {error}"
    else:
        raw = error
    first_line = raw.splitlines()[0].strip()
    for pattern in _ERROR_REDACTIONS:
        first_line = pattern.sub(r"\1[redacted]", first_line)
    return first_line[:240] if first_line else None


def _audit_outcome(status: ProviderSyncStatus) -> Literal[
    "success", "partial", "failure", "skipped_credential"
]:
    if status == "succeeded":
        return "success"
    if status == "partial":
        return "partial"
    if status == "skipped_credential":
        return "skipped_credential"
    return "failure"
