"""CareStack procedure-code (CDT) catalog backfill (ENG-420 / ENG-538).

Operator-triggered, background-only sweep that populates
``catalog.procedure_code`` by resolving each needed ``procedureCodeId``
through the CareStack **by-id** endpoint
(``GET /api/v1.0/procedure-codes/{id}``) and upserting it. The catalog is
workspace-wide reference data — see ``packages/catalog/CLAUDE.md``.

ENG-538: the flat ``GET /api/v1.0/procedure-codes`` LIST endpoint is BROKEN
on the real account (it returns only a handful of junk "Other" codes, never
the CDT codes that treatment procedures reference), so by-id is the primary
source. The work-list is the distinct set of ``procedureCodeId`` values
observed in captured ``carestack.treatment_procedure.upsert`` raw_events —
enumerated through ``IngestService`` (the ``catalog`` domain may not read
``ingest``). New/changed codes are surfaced as drift.

This script is **NOT** wired to any HTTP endpoint — Next's 30s proxy
timeout has burned us before on long-running ingest operations. Run it
from a workstation or a Cloud Run Job; let it finish.

CLI::

    # dry-run is the default — enumerate + print the work-list ids only
    python3 infra/scripts/backfill_procedure_codes.py --tenant-id <uuid>

    # apply mode — resolve each id by-id and upsert
    python3 infra/scripts/backfill_procedure_codes.py \\
        --tenant-id <uuid> \\
        --apply \\
        [--max-codes 20000] \\
        [--sleep-seconds 0.1]

Exit codes:
    0  success (including dry-run)
    2  CareStack credential missing for the tenant
    1  uncaught exception (logged before propagation)

Operational guard-rails:

* Default is dry-run; you must pass ``--apply`` to write.
* Tenant credentials load via ``IntegrationCredentialService``; the
  script does not touch ``.env``.
* The CareStack call is read-only (GET only). We NEVER POST / PUT / DELETE
  to ``/procedure-codes``.
* Structured logs contain ids + counts only — no PHI (codes are
  reference data anyway, but the discipline is the same).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any
from uuid import UUID

from packages.catalog.service import CatalogService
from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.ingest.service import IngestService
from packages.integrations.carestack import CareStackClient
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("infra.backfill_procedure_codes")

_DEFAULT_MAX_CODES = 20_000
_DEFAULT_SLEEP_SECONDS = 0.1
_SELECTOR = "procedure_codes"


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "CareStack procedure-code (CDT) catalog backfill for one tenant."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually upsert. Without this flag the script runs in "
            "dry-run mode (fetch + print ids only, no DB writes)."
        ),
    )
    parser.add_argument(
        "--max-codes",
        type=int,
        default=_DEFAULT_MAX_CODES,
        help=(
            "Defensive ceiling on the number of distinct procedure-code "
            "ids resolved in one run (default 20000). The real work-list "
            "is a few hundred ids; the cap exists to bound a runaway "
            "enumeration."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=_DEFAULT_SLEEP_SECONDS,
        help=(
            "Throttle between by-id CareStack calls (default 0.1s) to stay "
            "well under the rate limit. The script owns the unit of work — a "
            "single COMMIT lands at the end of a successful run; on any "
            "exception the transaction is rolled back."
        ),
    )
    return parser.parse_args(argv)


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Any | None = None,
    client_factory: Any | None = None,
) -> int:
    """Run the procedure-code backfill once.

    Test hooks:

    * ``session_factory`` — replaces :func:`async_session` so the run
      can hit a fully-mocked unit-of-work.
    * ``client_factory`` — replaces
      :meth:`CareStackClient.from_credential` so the test never touches
      the real CareStack HTTP surface.
    """
    tenant_id = TenantId(UUID(args.tenant_id))
    if session_factory is not None:
        session_cm = session_factory()
    else:
        session_cm = _default_session_factory()
    async with session_cm as session:
        cred_svc = IntegrationCredentialService(session)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "carestack", "password_grant"
            )
        except (NoCredentialError, PlatformError):
            log.info(
                "backfill.procedure_codes.skipped_credential",
                tenant_id=str(tenant_id),
                selector=_SELECTOR,
            )
            return 2

        cs_client = (client_factory or CareStackClient.from_credential)(payload)
        try:
            # Work-list: distinct procedureCodeId ids observed in captured
            # treatment-procedure raw_events (ENG-538). ``catalog`` may not
            # read ``ingest``, so the boundary enumerates here.
            code_ids = await IngestService(
                session
            ).distinct_treatment_procedure_code_ids(tenant_id)
            if args.max_codes >= 0:
                code_ids = code_ids[: args.max_codes]

            if not args.apply:
                # Dry-run: print the resolved work-list ids only — no
                # CareStack calls, no DB writes.
                log.info(
                    "backfill.procedure_codes.dry_run",
                    tenant_id=str(tenant_id),
                    selector=_SELECTOR,
                    code_count=len(code_ids),
                )
                for code_id in code_ids:
                    sys.stdout.write(f"{code_id}\n")
                return 0

            svc = CatalogService(session)
            try:
                outcome = await svc.sync_procedure_codes_by_id(
                    cs_client,
                    code_ids,
                    sleep_seconds=args.sleep_seconds,
                )
            except Exception:
                # The service flushes but never commits/rolls back; the
                # script owns the unit of work, so roll the partial
                # upsert back here before re-raising up to ``run``.
                await session.rollback()
                raise
            # Success: commit the catalog upserts before we exit the
            # session context manager.
            await session.commit()
        finally:
            close = getattr(cs_client, "close", None)
            if callable(close):
                maybe_awaitable = close()
                if maybe_awaitable is not None and hasattr(
                    maybe_awaitable, "__await__"
                ):
                    await maybe_awaitable

        log.info(
            "backfill.procedure_codes.done",
            tenant_id=str(tenant_id),
            selector=_SELECTOR,
            requested=outcome.requested,
            resolved=outcome.resolved,
            unresolved=len(outcome.unresolved),
            imported=outcome.imported,
            new_codes=len(outcome.new_codes),
            changed=len(outcome.changed),
        )
        return 0


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the exit code instead of calling
    ``sys.exit`` so wrapping callers (and tests) can use this directly.
    """
    configure_logging()
    args = parse_args(argv)
    return asyncio.run(main(args))


if __name__ == "__main__":
    sys.exit(run())
