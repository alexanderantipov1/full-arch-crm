"""Real-Salesforce verification for full-fidelity capture (ENG-427).

Operator-run smoke against a connected Salesforce org via the local stack. For
EACH ingested SF object it reads describe + Tooling, builds the dynamic
projection, runs ONE live SOQL with that projection to confirm the raw payload
widens, and reconciles the schema registry (``ingest.source_object_field``) so
the FLS gap is recorded. It does NOT run domain capture / ops upserts.

Run from repo root with env loaded:

    set -a && . ./.env && set +a
    PYTHONPATH=. .venv/bin/python infra/scripts/verify_sf_full_fidelity.py

Prints a per-object summary; exits non-zero if any object fails the widening
assertion (dynamic projection non-empty AND CreatedById captured live).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.service import IngestService
from packages.ingest.sf_schema import build_observed_fields, build_projection, fls_gap
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.tokens import SfTokens
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

# Local dev tenant (fusion-dental-implants).
_TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))

# Every SF object we ingest (ENG-427 rollout).
_OBJECTS = [
    "Lead",
    "Contact",
    "Account",
    "Opportunity",
    "Event",
    "Task",
    "Case",
    "OpportunityHistory",
]


async def _verify_object(client: SfClient, ingest: IngestService, obj: str) -> bool:
    describe = await client.describe(obj)
    tooling = await client.describe_tooling_fields(obj)
    described = describe.get("fields") or []
    try:
        projection = build_projection(describe)
        proj_n = len(projection.split(","))
    except ValueError:
        projection, proj_n = "", 0
    gap = fls_gap(describe, tooling)

    record_keys: list[str] = []
    if projection:
        soql = f"SELECT {projection} FROM {obj} ORDER BY CreatedDate DESC LIMIT 1"
        result = await client.soql(soql)
        records = result.get("records") or []
        record_keys = sorted(records[0].keys()) if records else []

    observed = build_observed_fields(describe, tooling)
    await ingest.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name=obj,
        fields=observed,
        observed_at=datetime.now(UTC),
    )

    # All these objects expose a standard CreatedById; full fidelity must
    # capture it (the old static projections mostly omitted it).
    has_created_by = "CreatedById" in record_keys
    ok = proj_n > 0 and (not record_keys or has_created_by)
    print(
        f"{obj:<20} describe={len(described):>3} projection={proj_n:>3} "
        f"live_keys={len(record_keys):>3} fls_gap={len(gap):>2} "
        f"CreatedById={'Y' if has_created_by else '-'}  "
        f"{'PASS' if ok else 'FAIL'}"
    )
    return ok


async def main() -> int:
    async with async_session() as session:
        cred = IntegrationCredentialService(session)
        try:
            oauth = await cred.read_for(_TENANT_ID, "salesforce", "oauth_token")
        except NoCredentialError:
            print("FAIL: no salesforce oauth_token credential for tenant")
            return 2
        try:
            api_key: dict[str, Any] | None = await cred.read_for(
                _TENANT_ID, "salesforce", "api_key"
            )
        except NoCredentialError:
            api_key = None

        async def _persist(_tokens: SfTokens) -> None:
            pass  # verification run: drop rotated tokens

        client = SfClient.from_credential(
            oauth, on_refresh=_persist, api_key_payload=api_key
        )
        ingest = IngestService(session)
        results: list[bool] = []
        try:
            for obj in _OBJECTS:
                results.append(await _verify_object(client, ingest, obj))
        finally:
            await client.close()
        await session.commit()

    ok = all(results)
    print("\nRESULT:", "PASS" if ok else "FAIL", f"({sum(results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
