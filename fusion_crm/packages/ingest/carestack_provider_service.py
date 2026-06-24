"""CareStack provider directory ingest (ENG-308).

CareStack's ``/api/v1.0/providers`` endpoint returns a flat,
unpaginated JSON array of providers for the account. This service:

* calls the endpoint once,
* drops entries without a usable integer ``id``,
* upserts into ``ingest.carestack_provider`` in batches via
  :meth:`IngestRepository.upsert_providers`,
* commits per ``commit_every`` so a large response does not wrap the
  whole transaction.

Provider data is operational (clinician name, type, active flag) —
NOT PHI. We still keep the upsert idempotent so a re-run never produces
duplicates.

The backfill script (``infra/scripts/backfill_providers.py``) is the
only caller today. The scheduled CareStack pull may add a daily refresh
later; the service contract does not change.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository
from packages.ingest.schemas import ProviderImportOut

log = get_logger("ingest.carestack_provider")

_DEFAULT_MAX_PROVIDERS = 2000
_DEFAULT_COMMIT_EVERY = 50


class CareStackProvidersClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the provider ingest."""

    async def list_providers(self) -> list[dict[str, Any]]: ...


class CareStackProviderIngestService:
    """Sweep the CareStack provider directory once and persist it."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackProvidersClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._repo = IngestRepository(session)

    async def import_providers(
        self,
        tenant_id: TenantId,
        *,
        commit_every: int = _DEFAULT_COMMIT_EVERY,
        commit: Callable[[], Awaitable[None]] | None = None,
        max_providers: int = _DEFAULT_MAX_PROVIDERS,
    ) -> ProviderImportOut:
        """Fetch + upsert the CareStack provider directory.

        Args:
            tenant_id: Per-tenant scope (every row carries this).
            commit_every: Flush the DB unit-of-work every N rows. ``0``
                disables mid-run commits (one final flush only).
            commit: Caller-supplied commit callable. Defaults to
                ``session.commit`` so the backfill script can hook a
                spy in tests.
            max_providers: Cap on the number of rows we ever process in
                one invocation. Defends against a misbehaving CareStack
                account returning an unbounded array.

        Returns:
            :class:`ProviderImportOut` with ``imported``, ``total_seen``,
            ``error_count``.
        """
        commit_fn = commit if commit is not None else self._session.commit

        providers = await self._carestack.list_providers()
        if not providers:
            return ProviderImportOut(imported=0, total_seen=0, error_count=0)

        capped: list[dict[str, Any]] = []
        for entry in providers:
            if len(capped) >= max_providers:
                break
            # The repository drops entries without a usable integer id;
            # mirror the rule here so total_seen counts what we WILL
            # attempt to write, not what CareStack returned.
            raw_id = entry.get("id") if isinstance(entry, dict) else None
            if raw_id is None:
                continue
            try:
                int(raw_id)
            except (TypeError, ValueError):
                continue
            capped.append(entry)

        if not capped:
            return ProviderImportOut(imported=0, total_seen=0, error_count=0)

        batch_size = max(1, commit_every) if commit_every > 0 else len(capped)
        imported_total = 0
        error_count = 0
        for start in range(0, len(capped), batch_size):
            batch = capped[start : start + batch_size]
            try:
                written = await self._repo.upsert_providers(tenant_id, batch)
            except Exception as exc:
                # `except Exception` per packages/CLAUDE.md — never
                # `except BaseException`. Failure isolation: log it,
                # advance to the next batch.
                error_count += 1
                log.warning(
                    "carestack.providers.batch_failed",
                    tenant_id=str(tenant_id),
                    batch_start=start,
                    batch_size=len(batch),
                    error=str(exc)[:200],
                )
                continue
            imported_total += written
            if commit_every > 0:
                await commit_fn()

        # Final commit for the trailing batch when commit_every disabled
        # OR when the last batch didn't cleanly land on the commit boundary.
        if commit_every <= 0 and imported_total > 0:
            await commit_fn()

        log.info(
            "carestack.providers.imported",
            tenant_id=str(tenant_id),
            imported=imported_total,
            total_seen=len(capped),
            errors=error_count,
        )
        return ProviderImportOut(
            imported=imported_total,
            total_seen=len(capped),
            error_count=error_count,
        )
