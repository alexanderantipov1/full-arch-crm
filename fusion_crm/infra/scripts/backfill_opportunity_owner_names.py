"""Backfill ``ops.opportunity.extra.owner_name`` from Salesforce (ENG-414).

The scheduled SF Opportunity pull (ENG-414 wiring) captures
``Owner.Name`` going forward, but existing rows landed before the
projection was extended and have only ``extra->>'owner_id'``. This
script closes the gap with ONE SOQL per object kind and a bulk
``jsonb_set`` per owner.

Mirrors the ENG-408 lead-owner backfill shape (referenced in
the orchestration prompt):

1. Read the distinct ``extra->>'owner_id'`` values from
   ``ops.opportunity`` for one tenant.
2. Bucket by SF prefix — ``005…`` (User) vs ``00G…`` (Group / Queue).
3. Issue ONE SOQL ``SELECT Id, Name FROM <object> WHERE Id IN (…)``
   per bucket — the SF API rejects more than ~1000 ids per ``IN``
   clause, so chunk if necessary (the dental clinic's TC roster
   fits in one query today; chunking is a defensive cap).
4. For each ``(owner_id, name)`` pair, ``OpsService.set_opportunity_
   owner_name`` writes idempotently — only rows whose stored
   ``owner_name`` differs are touched.

Dry-run by default. ``--apply`` commits per owner.

CLI::

    python3 infra/scripts/backfill_opportunity_owner_names.py \\
        --tenant-id <uuid> \\
        [--apply] \\
        [--batch 200]

Exit codes:
    0  success (including dry-run)
    2  Salesforce credential missing for the tenant
    1  uncaught exception

Hard rules (from CLAUDE.md):

- Read-only SF pull. No writes to Salesforce, ever.
- Names are not PHI, but the structured log lines only carry the SF
  id + counts, never the resolved display name.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.integrations.salesforce import SfClient
from packages.ops.service import OpsService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("infra.backfill_opportunity_owner_names")

_DEFAULT_BATCH = 200
_SF_USER_PREFIX = "005"
_SF_GROUP_PREFIX = "00G"


class _SfClientProtocol(Protocol):
    async def soql(self, query: str) -> dict[str, Any]: ...


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill ops.opportunity.extra.owner_name from Salesforce "
            "User/Group records. Dry-run by default."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply changes (commit each owner after its jsonb_set update). "
            "Without this flag, the script runs read-only and prints the "
            "resolved (owner_id, name) pairs without writing."
        ),
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=_DEFAULT_BATCH,
        help=(
            "Max owner ids per SOQL IN-list (default 200). The SF cap is "
            "~1000 but staying under 200 keeps the request size safe."
        ),
    )
    return parser.parse_args(argv)


def _bucket_owner_ids(owner_ids: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(user_ids, group_ids)`` filtered by SF object prefix."""
    users: list[str] = []
    groups: list[str] = []
    for owner_id in owner_ids:
        if owner_id.startswith(_SF_USER_PREFIX):
            users.append(owner_id)
        elif owner_id.startswith(_SF_GROUP_PREFIX):
            groups.append(owner_id)
    return users, groups


def _chunk(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _soql_in_list(ids: list[str]) -> str:
    """Quote a list of SF ids for a SOQL IN clause.

    SF ids are 15/18 char alphanumeric tokens (already prefix-validated)
    so single-quoting is enough; we additionally strip anything that
    isn't alphanumeric as a belt-and-braces defence against malformed
    input.
    """
    safe = [
        "'" + "".join(c for c in i if c.isalnum()) + "'"
        for i in ids
    ]
    return "(" + ", ".join(safe) + ")"


async def _resolve_names(
    client: _SfClientProtocol, ids: list[str], *, sobject: str, batch: int
) -> dict[str, str]:
    """Run one or more ``SELECT Id, Name FROM <sobject>`` queries."""
    resolved: dict[str, str] = {}
    for chunk in _chunk(ids, batch):
        soql = (
            f"SELECT Id, Name FROM {sobject} WHERE Id IN {_soql_in_list(chunk)}"
        )
        body = await client.soql(soql)
        for record in body.get("records", []) or []:
            sf_id = record.get("Id")
            name = record.get("Name")
            if isinstance(sf_id, str) and isinstance(name, str):
                resolved[sf_id] = name.strip()
    return resolved


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Any] | None = None,
    client_factory: Callable[[dict[str, Any]], _SfClientProtocol] | None = None,
) -> int:
    """Run the opportunity-owner backfill once. Returns a CLI exit code."""
    tenant_id = TenantId(UUID(args.tenant_id))
    session_cm = (session_factory or _default_session_factory)()
    async with session_cm as session:
        cred_svc = IntegrationCredentialService(session)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "salesforce", "oauth_token"
            )
        except (NoCredentialError, PlatformError):
            log.info(
                "backfill.opportunity_owner.skipped_credential",
                tenant_id=str(tenant_id),
            )
            return 2

        async def _persist_refresh(tokens_payload: dict[str, Any]) -> None:
            # Reuse the runtime contract: refreshed tokens land back in the
            # same credential row. The IntegrationCredentialService API
            # matches the production SfClient wiring (see CLAUDE.md).
            await cred_svc.upsert(
                tenant_id,
                provider_kind="salesforce",
                credential_kind="oauth_token",
                payload=tokens_payload,
            )

        if client_factory is not None:
            client = client_factory(payload)
        else:
            client = SfClient.from_credential(
                payload,
                on_refresh=_persist_refresh,  # type: ignore[arg-type]
            )

        ops = OpsService(session)
        owner_ids = await ops.list_distinct_opportunity_owner_ids(tenant_id)
        if not owner_ids:
            log.info(
                "backfill.opportunity_owner.empty",
                tenant_id=str(tenant_id),
            )
            return 0

        users, groups = _bucket_owner_ids(owner_ids)
        log.info(
            "backfill.opportunity_owner.distinct",
            tenant_id=str(tenant_id),
            total=len(owner_ids),
            users=len(users),
            groups=len(groups),
            other=len(owner_ids) - len(users) - len(groups),
        )

        resolved: dict[str, str] = {}
        if users:
            resolved.update(
                await _resolve_names(client, users, sobject="User", batch=args.batch)
            )
        if groups:
            resolved.update(
                await _resolve_names(
                    client, groups, sobject="Group", batch=args.batch
                )
            )

        if not args.apply:
            for owner_id, name in sorted(resolved.items()):
                # Name is operational metadata, not PHI; safe to write to
                # stdout for the operator running the dry-run.
                sys.stdout.write(f"{owner_id}\t{name}\n")
            log.info(
                "backfill.opportunity_owner.dry_run",
                tenant_id=str(tenant_id),
                resolved=len(resolved),
                unresolved=len(owner_ids) - len(resolved),
            )
            return 0

        touched_total = 0
        for owner_id, name in resolved.items():
            touched = await ops.set_opportunity_owner_name(
                tenant_id, owner_id=owner_id, owner_name=name
            )
            await session.commit()
            touched_total += touched
            log.info(
                "backfill.opportunity_owner.applied",
                tenant_id=str(tenant_id),
                owner_id=owner_id,
                rows=touched,
            )

        log.info(
            "backfill.opportunity_owner.done",
            tenant_id=str(tenant_id),
            resolved=len(resolved),
            unresolved=len(owner_ids) - len(resolved),
            rows=touched_total,
        )
        return 0


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the exit code instead of calling
    ``sys.exit`` so wrapping callers (and tests) can use this directly."""
    configure_logging()
    args = parse_args(argv)
    try:
        return asyncio.run(main(args))
    except Exception:  # noqa: BLE001 - top-level CLI boundary
        log.exception("backfill.opportunity_owner.crashed")
        return 1


if __name__ == "__main__":
    sys.exit(run())
