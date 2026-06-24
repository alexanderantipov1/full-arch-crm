"""Throttled CareStack provider directory backfill (ENG-308).

Operator-triggered, background-only sweep that calls
``GET /api/v1.0/providers`` once for the tenant and upserts every
provider into ``ingest.carestack_provider`` so the person card can
resolve ``defaultProviderId`` into a readable "Dr First Last".

The CareStack endpoint returns a flat unpaginated JSON array; the
script applies a defensive ``--max-providers`` cap so a misbehaving
account never produces an unbounded upsert. ``--commit-every`` flushes
the unit-of-work every N rows so a 1000-row response does not wrap the
whole sweep in one transaction.

This script is **NOT** wired to any HTTP endpoint — Next's 30s proxy
timeout has burned us before on long-running ingest operations. Run it
from a workstation or a Cloud Run Job; let it finish.

CLI::

    python3 infra/scripts/backfill_providers.py \\
        [--tenant-id <uuid>] \\
        [--max-providers 2000] \\
        [--sleep-seconds 0.5] \\
        [--commit-every 50] \\
        [--dry-run]

``--tenant-id`` is optional: omit it to use the default tenant
(``Settings.tenant_default_slug``) — the single-tenant Cloud Run Job
(``fusion-job-provider-backfill``, ENG-510) relies on this.

Exit codes:
    0  success (including dry-run)
    2  CareStack credential missing for the tenant
    1  uncaught exception (logged before propagation by ``run``)

Operational guard-rails:

* Throttle defaults to 0.5 s between batches. CareStack throttled this
  account for ~24h once before — be gentle.
* Logs only ``provider_id`` integers + counts — no clinician names in
  the structured log lines (the operator can read names from the DB).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.carestack_provider_service import (
    CareStackProviderIngestService,
)
from packages.integrations.carestack import CareStackClient
from packages.integrations.service import IntegrationService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.service import TenantService


# Lazy session-factory resolution (mirrors backfill_payment_summary.py)
def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


log = get_logger("infra.backfill_providers")

_DEFAULT_MAX_PROVIDERS = 2000
_DEFAULT_SLEEP_SECONDS = 0.5
_DEFAULT_COMMIT_EVERY = 50
_TRIGGER = "backfill_script"
_OBJECT_SCOPE = "providers"
_SELECTOR = "providers"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Throttled CareStack provider directory backfill for one tenant."
        ),
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help=(
            "Tenant UUID. Omit to use the default tenant "
            "(Settings.tenant_default_slug) — convenient for the single-tenant "
            "Cloud Run Job."
        ),
    )
    parser.add_argument(
        "--max-providers",
        type=int,
        default=_DEFAULT_MAX_PROVIDERS,
        help=(
            "Defensive ceiling on the number of providers processed in one run "
            "(default 2000)."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=_DEFAULT_SLEEP_SECONDS,
        help=(
            "Between-batch throttle (default 0.5s). CareStack rate-limits "
            "aggressive sweeps."
        ),
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=_DEFAULT_COMMIT_EVERY,
        help=(
            "Flush the DB unit-of-work every N providers (default 50). "
            "Prevents a single giant transaction across the whole sweep."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Fetch the provider list and print the resolved ids to stdout, "
            "but do NOT call the upsert and do NOT open a sync_run."
        ),
    )
    return parser.parse_args(argv)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:backfill_providers"},
    )


async def main(
    args: argparse.Namespace,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    session_factory: Callable[[], Any] | None = None,
    client_factory: Callable[[dict[str, object]], Any] | None = None,
) -> int:
    """Run the providers backfill once. Returns a CLI exit code.

    Test hooks (same shape as ``backfill_payment_summary.main``):

    * ``session_factory`` — replaces :func:`async_session` so the run
      can hit a fully-mocked unit-of-work.
    * ``client_factory`` — replaces
      :meth:`CareStackClient.from_credential` so the test never touches
      the real CareStack HTTP surface.
    * ``sleep`` — recorded by tests asserting throttle wiring; left
      unused on the success path because :class:`CareStackProviderIngestService`
      does the per-batch commit + the natural pacing is single-fetch.
    """
    del sleep  # accepted for shape parity with backfill_payment_summary; the
    # provider endpoint is a single call so the throttle is a no-op here.
    explicit_tenant_id = (
        TenantId(UUID(args.tenant_id)) if args.tenant_id is not None else None
    )
    if session_factory is not None:
        session_cm = session_factory()
    else:
        session_cm = _default_session_factory()
    async with session_cm as session:
        # ENG-510: resolve the default tenant when --tenant-id is omitted so the
        # Cloud Run Job needs no env-specific UUID baked into its args.
        if explicit_tenant_id is not None:
            tenant_id = explicit_tenant_id
        else:
            tenant = await TenantService(session).get_by_slug(
                get_settings().tenant_default_slug
            )
            tenant_id = TenantId(tenant.id)
        cred_svc = IntegrationCredentialService(session)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "carestack", "password_grant"
            )
        except (NoCredentialError, PlatformError):
            log.info(
                "backfill.providers.skipped_credential",
                tenant_id=str(tenant_id),
                selector=_SELECTOR,
            )
            return 2

        if args.dry_run:
            # Build a temporary CareStack client just to read the directory.
            # Mirrors the payment-summary dry-run shape: no sync_run is opened
            # because there's nothing to journal.
            cs_client = (client_factory or CareStackClient.from_credential)(payload)
            try:
                providers = await cs_client.list_providers()
            finally:
                close = getattr(cs_client, "close", None)
                if callable(close):
                    maybe_awaitable = close()
                    if maybe_awaitable is not None and hasattr(
                        maybe_awaitable, "__await__"
                    ):
                        await maybe_awaitable

            # Apply the same cap the live path enforces so the operator's
            # dry-run view matches what the real run would actually write.
            capped: list[int] = []
            for entry in providers or []:
                if len(capped) >= args.max_providers:
                    break
                raw_id = entry.get("id") if isinstance(entry, dict) else None
                if raw_id is None:
                    continue
                try:
                    capped.append(int(raw_id))
                except (TypeError, ValueError):
                    continue

            log.info(
                "backfill.providers.dry_run",
                tenant_id=str(tenant_id),
                selector=_SELECTOR,
                provider_count=len(capped),
            )
            for provider_id in capped:
                sys.stdout.write(f"{provider_id}\n")
            return 0

        cs_client = (client_factory or CareStackClient.from_credential)(payload)
        integration = IntegrationService(session)
        principal = _principal(tenant_id)
        svc = CareStackProviderIngestService(
            session=session, carestack_client=cs_client
        )
        run = await integration.open_provider_sync_run(
            tenant_id,
            provider="carestack",
            object_scope=_OBJECT_SCOPE,
            trigger=_TRIGGER,
        )
        try:
            try:
                imported = await svc.import_providers(
                    tenant_id,
                    commit_every=args.commit_every,
                    commit=session.commit,
                    max_providers=args.max_providers,
                )
                await integration.close_provider_sync_run(
                    tenant_id,
                    sync_run_id=run.id,
                    principal=principal,
                    provider="carestack",
                    object_scope=_OBJECT_SCOPE,
                    status="succeeded",
                    records_total=imported.total_seen,
                    records_succeeded=imported.imported,
                    records_failed=imported.error_count,
                )
            except Exception as exc:  # noqa: BLE001 — sync_run accounting
                await integration.close_provider_sync_run(
                    tenant_id,
                    sync_run_id=run.id,
                    principal=principal,
                    provider="carestack",
                    object_scope=_OBJECT_SCOPE,
                    status="failed",
                    records_total=0,
                    records_succeeded=0,
                    records_failed=0,
                    error=str(exc)[:500],
                )
                raise
        finally:
            close = getattr(cs_client, "close", None)
            if callable(close):
                maybe_awaitable = close()
                if maybe_awaitable is not None and hasattr(
                    maybe_awaitable, "__await__"
                ):
                    await maybe_awaitable

        log.info(
            "backfill.providers.done",
            tenant_id=str(tenant_id),
            selector=_SELECTOR,
            providers=imported.total_seen,
            imported=imported.imported,
            errors=imported.error_count,
        )
        return 0


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the exit code instead of calling ``sys.exit``
    so wrapping callers (and tests) can use this directly."""
    configure_logging()
    args = parse_args(argv)
    return asyncio.run(main(args))


if __name__ == "__main__":
    sys.exit(run())
