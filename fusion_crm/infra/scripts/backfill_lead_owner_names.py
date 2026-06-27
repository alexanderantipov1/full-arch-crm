"""One-off enrichment of ``Lead.extra.owner_name`` from Salesforce Users (ENG-408).

The PM Payments Owner column needs the human owner name, but until ENG-408
the SF lead projection captured only ``OwnerId`` — and the idempotent
backfill (``pull_all_since`` skips rows whose ``LastModifiedDate`` is
already captured, ENG-381) never re-runs the lead upsert for unchanged
leads, so a plain ``--entities sf_leads`` rerun cannot enrich the ~63k
existing rows. Historical raw payloads do not carry ``Owner.Name`` either
(the projection predates it).

This script closes the gap directly: collect the DISTINCT ``owner_id``
values from ``ops.lead.extra`` (tens of ids — the sales team), resolve
them with ONE SOQL ``SELECT Id, Name FROM User`` per chunk, then bulk-set
``extra.owner_name`` per owner. New pulls already mirror ``Owner.Name``
(ENG-408 projection), so this is a one-time repair; re-running is
idempotent (only rows whose stored name differs are touched) and also
refreshes names after SF-side renames.

CLI:

    python3 infra/scripts/backfill_lead_owner_names.py            # dry-run
    python3 infra/scripts/backfill_lead_owner_names.py --apply    # update

Dry-run is the DEFAULT and prints per-owner update candidates without
touching data. ``--apply`` updates one owner at a time with a commit per
owner, so an interrupted run loses nothing and resumes safely.

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception

PHI safety: leads are marketing rows and SF owners are staff, not
patients; logs still carry only owner ids and counts — never names or
payload content.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.integrations.salesforce.client import SfClient
from packages.integrations.salesforce.tokens import SfTokens
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("infra.backfill_lead_owner_names")

# SF record ids are 15/18-char alphanumerics; anything else never reaches
# the SOQL literal below.
_SF_ID_RE = re.compile(r"^[a-zA-Z0-9]{15,18}$")
_SOQL_CHUNK = 200


async def _get_sf_client(
    cred_svc: IntegrationCredentialService, tenant_id: TenantId
) -> SfClient | None:
    """Mirror of the backfill job's credential dance (token-refresh no-op)."""
    try:
        oauth_payload = await cred_svc.read_for(tenant_id, "salesforce", "oauth_token")
    except (NoCredentialError, PlatformError):
        return None
    try:
        api_key_payload: dict[str, object] | None = await cred_svc.read_for(
            tenant_id, "salesforce", "api_key"
        )
    except (NoCredentialError, PlatformError):
        api_key_payload = None

    async def _noop_refresh(_tokens: SfTokens) -> None:
        pass

    return SfClient.from_credential(
        oauth_payload, on_refresh=_noop_refresh, api_key_payload=api_key_payload
    )


async def _distinct_owner_ids(session: AsyncSession, tenant_id: TenantId) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT DISTINCT extra->>'owner_id' AS owner_id"
            "  FROM ops.lead"
            " WHERE tenant_id = :tenant_id"
            "   AND extra->>'owner_id' IS NOT NULL"
        ),
        {"tenant_id": str(tenant_id)},
    )
    return [r.owner_id for r in rows if _SF_ID_RE.match(r.owner_id or "")]


async def _resolve_owner_names(
    sf: SfClient, owner_ids: list[str]
) -> dict[str, str]:
    """Resolve owner ids to display names.

    SF lead ownership is polymorphic: ``005…`` ids are Users, ``00G…`` ids
    are Groups (queues — e.g. round-robin intake queues own ~half the lead
    book here). One ``SELECT Id, Name`` per object kind per ≤200-id chunk.
    """
    by_object: dict[str, list[str]] = {"User": [], "Group": []}
    for oid in owner_ids:
        by_object["Group" if oid.startswith("00G") else "User"].append(oid)

    names: dict[str, str] = {}
    for sobject, ids in by_object.items():
        for start in range(0, len(ids), _SOQL_CHUNK):
            chunk = ids[start : start + _SOQL_CHUNK]
            in_list = ", ".join(f"'{oid}'" for oid in chunk)
            result = await sf.soql(
                f"SELECT Id, Name FROM {sobject} WHERE Id IN ({in_list})"
            )
            for record in result["records"]:
                rid, name = record.get("Id"), record.get("Name")
                if isinstance(rid, str) and isinstance(name, str) and name:
                    names[rid] = name
    return names


async def _count_pending(
    session: AsyncSession, tenant_id: TenantId, owner_id: str, name: str
) -> int:
    row = await session.execute(
        text(
            "SELECT count(*) FROM ops.lead"
            " WHERE tenant_id = :tenant_id"
            "   AND extra->>'owner_id' = :owner_id"
            "   AND extra->>'owner_name' IS DISTINCT FROM :name"
        ),
        {"tenant_id": str(tenant_id), "owner_id": owner_id, "name": name},
    )
    return int(row.scalar_one())


async def _apply_owner(
    session: AsyncSession, tenant_id: TenantId, owner_id: str, name: str
) -> int:
    result: Any = await session.execute(
        text(
            "UPDATE ops.lead"
            "   SET extra = jsonb_set(extra, '{owner_name}', to_jsonb(CAST(:name AS text)))"
            " WHERE tenant_id = :tenant_id"
            "   AND extra->>'owner_id' = :owner_id"
            "   AND extra->>'owner_name' IS DISTINCT FROM :name"
        ),
        {"tenant_id": str(tenant_id), "owner_id": owner_id, "name": name},
    )
    return int(result.rowcount or 0)


def _make_session() -> Any:
    # Resolved at call time so ``--help`` and unit tests do not need a
    # configured environment (same pattern as cleanup_raw_event_duplicates).
    from packages.db.session import async_session

    return async_session()


async def run(args: argparse.Namespace) -> int:
    configure_logging()
    async with _make_session() as session:
        tenant_rows = await session.execute(text("SELECT id FROM tenant.tenant"))
        tenant_ids = [TenantId(r.id) for r in tenant_rows]

    total_updated = 0
    for tenant_id in tenant_ids:
        async with _make_session() as session:
            owner_ids = await _distinct_owner_ids(session, tenant_id)
            if not owner_ids:
                log.info(
                    "backfill_owner_names.no_owners", tenant_id=str(tenant_id)
                )
                continue

            cred_svc = IntegrationCredentialService(session)
            sf = await _get_sf_client(cred_svc, tenant_id)
            if sf is None:
                log.info(
                    "backfill_owner_names.skipped_credential",
                    tenant_id=str(tenant_id),
                )
                continue
            try:
                names = await _resolve_owner_names(sf, owner_ids)
            finally:
                await sf.close()

            unresolved = sorted(set(owner_ids) - set(names))
            log.info(
                "backfill_owner_names.resolved",
                tenant_id=str(tenant_id),
                owners=len(owner_ids),
                resolved=len(names),
                unresolved=len(unresolved),
            )
            if unresolved:
                # Deleted/inaccessible SF users keep their raw id in the
                # Owner column (the API falls back to owner_id).
                log.info(
                    "backfill_owner_names.unresolved_ids",
                    tenant_id=str(tenant_id),
                    owner_ids=unresolved,
                )

            for owner_id, name in sorted(names.items()):
                if args.apply:
                    updated = await _apply_owner(session, tenant_id, owner_id, name)
                    await session.commit()
                else:
                    updated = await _count_pending(session, tenant_id, owner_id, name)
                total_updated += updated
                log.info(
                    "backfill_owner_names.owner_done",
                    tenant_id=str(tenant_id),
                    owner_id=owner_id,
                    rows=updated,
                    applied=args.apply,
                )

    log.info(
        "backfill_owner_names.complete",
        rows=total_updated,
        applied=args.apply,
    )
    if not args.apply:
        print(f"\nDry-run: {total_updated} lead rows would be updated.")
        print("Re-run with --apply to write. Commits per owner; resume-safe.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich ops.lead extra.owner_name from Salesforce Users."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the resolved names (default: dry-run report only).",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001
        log.error("backfill_owner_names.failed", error=str(exc)[:300])
        return 1


if __name__ == "__main__":
    sys.exit(main())
