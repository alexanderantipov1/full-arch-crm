"""Throttled CareStack payment-summary backfill (ENG-305).

Targeted, background-only sweep: resolves every linked CareStack patient
for one tenant and refreshes their authoritative balance by snapshotting
``GET /billing/payment-summary/{patientId}``. The dashboard's
authoritative Outstanding / AR-risk numbers and the per-person
Billed/Adjustments/Paid/Balance figures live on these snapshots — the
in-tick rolling sweep walks 50 patients per cron tick, which is too slow
to seed the full tenant (1803 linked patients at the time of writing).

This script is operator-triggered. It is NOT wired to an HTTP endpoint —
Next's 30s proxy timeout has burned us before on long-running ingest
operations. Run it from a workstation or a Cloud Run Job; let it finish.

CLI:

    python3 infra/scripts/backfill_payment_summary.py \\
        --tenant-id <uuid> \\
        [--max-patients 2000] \\
        [--sleep-seconds 0.5] \\
        [--commit-every 50] \\
        [--dry-run] \\
        [--only-with-payments]

``--only-with-payments`` (ENG-307) narrows the patient_id pool to
CareStack patients with at least one payment-related accounting
raw_event on the tenant. Use it for the real backfill against the
prod tenant where only ~1803 of 55,677 linked patients have any
payment activity and the default first_seen_at-ordered resolver
misses most of them under ``--max-patients 2000``.

Exit codes:
    0  success (including dry-run + "no usable patient_ids")
    2  CareStack credential missing for the tenant
    1  uncaught exception (logged before propagation by ``run``)

Operational guard-rails:

* Throttle defaults to 0.5 s between patients. CareStack throttled this
  account for ~24h once before — the backfill must stay gentle.
* Retry/backoff for 429 + 5xx is the existing
  :func:`CareStackPaymentSummaryIngestService._fetch_summary_with_backoff`
  policy; this script never re-implements it.
* Commits every ``--commit-every`` patients (default 50) so a 1000-row
  surge does not wrap the whole run in one transaction.
* Logs only ``patient_id`` and counts — never names, DOB, balances, or
  clinical content.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.carestack_payment_summary_service import (
    CareStackPaymentSummaryIngestService,
)
from packages.ingest.repository import IngestRepository
from packages.integrations.carestack import CareStackClient
from packages.integrations.service import IntegrationService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)


# ``packages.db.session`` builds the engine at import time via
# :func:`Settings`. Importing it eagerly would prevent ``--help`` from
# running without a configured environment, and would force every unit
# test to set ``SECRET_KEY`` / ``DATABASE_URL`` / ``REDIS_URL`` just to
# load this module. Resolve at call time instead.
def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()

log = get_logger("infra.backfill_payment_summary")

_DEFAULT_MAX_PATIENTS = 2000
_DEFAULT_SLEEP_SECONDS = 0.5
_DEFAULT_COMMIT_EVERY = 50
_TRIGGER = "backfill_script"
_OBJECT_SCOPE = "payment_summary"

# ENG-307: canonical CareStack payment-related transactionCode set. Must
# stay aligned with ``_PAYMENT_CODE_TO_KIND`` + ``_REFUND_TRANSACTION_CODES``
# in ``packages/ingest/carestack_accounting_transaction_service.py`` —
# those constants are intentionally module-private (leading underscore)
# in the service module, so we re-declare the canonical set here and a
# unit test (``test_payment_transaction_codes_match_accounting_service_classifier``)
# verifies the two stay in sync. Used by the ``--only-with-payments``
# filtered resolver to scope the backfill to patients with ANY payment
# activity:
#
#   * Cash IN — ``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS``
#   * Allocation legs — ``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``
#   * Explicit delete — ``PATIENTPAYMENTSDELETE``
#   * Refunds — ``REFUND`` / ``PATIENTREFUND`` / ``INSURANCEREFUND``
PAYMENT_TRANSACTION_CODES: tuple[str, ...] = (
    "INSPAYMENTAPPLIED",
    "INSURANCEPAYMENTS",
    "INSURANCEREFUND",
    "PATIENTPAYMENTS",
    "PATIENTPAYMENTSDELETE",
    "PATIENTREFUND",
    "PATPAYMENTAPPLIED",
    "REFUND",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Throttled CareStack payment-summary backfill for one tenant."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--max-patients",
        type=int,
        default=_DEFAULT_MAX_PATIENTS,
        help=(
            "Defensive ceiling on the number of patient_ids resolved off "
            "identity.source_link (default 2000)."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=_DEFAULT_SLEEP_SECONDS,
        help=(
            "Between-patient throttle (default 0.5s). CareStack will rate-"
            "limit this account if the sweep is too aggressive."
        ),
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=_DEFAULT_COMMIT_EVERY,
        help=(
            "Flush the DB unit-of-work every N patients (default 50). "
            "Prevents a single giant transaction across the whole sweep."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Resolve the patient_id set and print it, but do NOT call "
            "CareStack or write to the database."
        ),
    )
    parser.add_argument(
        "--only-with-payments",
        action="store_true",
        help=(
            "ENG-307: restrict the patient_id pool to CareStack patients "
            "with at least one payment-related accounting raw_event on "
            "the tenant. On prod we have ~55,677 linked patients but "
            "only ~1803 with payment activity; the default resolver's "
            "first_seen_at DESC ordering misses most of the active set "
            "under --max-patients 2000. With this flag, the throttled "
            "sweep covers the ~1803 has-payments patients in ~15 min "
            "instead of paying CareStack for 2000 mostly-cold lookups."
        ),
    )
    return parser.parse_args(argv)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:backfill_payment_summary"},
    )


async def main(
    args: argparse.Namespace,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    session_factory: Callable[[], Any] | None = None,
    client_factory: Callable[[dict[str, object]], Any] | None = None,
) -> int:
    """Run the backfill once. Returns a CLI exit code.

    Test hooks:
        * ``session_factory`` — replaces :func:`async_session` so the run
          can hit a fully-mocked unit-of-work.
        * ``client_factory`` — replaces
          :meth:`CareStackClient.from_credential` so the test never
          touches the real CareStack HTTP surface.
        * ``sleep`` — injected into the underlying sweep so throttle +
          backoff complete instantly.

    Real-world callers (CLI / Cloud Run Job) leave all three at their
    defaults and let ``async_session`` open a real connection.
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
                "backfill.payment_summary.skipped_credential",
                tenant_id=str(tenant_id),
            )
            return 2

        if args.only_with_payments:
            ingest_repo = IngestRepository(session)
            links = await ingest_repo.list_carestack_patients_with_payment_activity(
                tenant_id,
                payment_codes=PAYMENT_TRANSACTION_CODES,
                limit=args.max_patients,
            )
            selector = "has_payments"
        else:
            identity_repo = IdentityRepository(session)
            links = await identity_repo.list_source_links_for_dashboard(
                tenant_id,
                source_system="carestack",
                source_kind="patient",
                limit=args.max_patients,
            )
            selector = "all_linked"
        patient_ids: list[str] = [
            str(link.source_id)
            for link in links
            if link.source_id is not None and str(link.source_id).strip()
        ]

        log.info(
            "backfill.payment_summary.resolved",
            tenant_id=str(tenant_id),
            selector=selector,
            patient_count=len(patient_ids),
        )

        if args.dry_run:
            log.info(
                "backfill.payment_summary.dry_run",
                tenant_id=str(tenant_id),
                selector=selector,
                patient_count=len(patient_ids),
            )
            # Stdout listing for the operator. patient_id is a stable
            # non-PII reference; printing names or balances would be a
            # PHI leak.
            for patient_id in patient_ids:
                sys.stdout.write(f"{patient_id}\n")
            return 0

        if not patient_ids:
            log.info(
                "backfill.payment_summary.no_patients",
                tenant_id=str(tenant_id),
                selector=selector,
            )
            return 0

        cs_client = (client_factory or CareStackClient.from_credential)(payload)
        integration = IntegrationService(session)
        principal = _principal(tenant_id)
        svc = CareStackPaymentSummaryIngestService(
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
                imported = await svc.import_payment_summary_for_patients(
                    tenant_id,
                    patient_ids,
                    sleep_seconds=args.sleep_seconds,
                    commit_every=args.commit_every,
                    sleep=sleep,
                    commit=session.commit,
                )
                await integration.close_provider_sync_run(
                    tenant_id,
                    sync_run_id=run.id,
                    principal=principal,
                    provider="carestack",
                    object_scope=_OBJECT_SCOPE,
                    status="succeeded",
                    records_total=imported.patient_count,
                    records_succeeded=imported.snapshot_count,
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
            "backfill.payment_summary.done",
            tenant_id=str(tenant_id),
            selector=selector,
            patients=imported.patient_count,
            snapshots=imported.snapshot_count,
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
