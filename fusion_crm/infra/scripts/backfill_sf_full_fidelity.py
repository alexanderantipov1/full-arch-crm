"""Salesforce full-fidelity history backfill (ENG-430).

Re-pull Salesforce objects through the DYNAMIC (full-fidelity) projection so
historical ``ingest.raw_event`` rows gain the now-captured wide field set. The
normal pull path skips unchanged rows (the ENG-381 capture change-guard); this
script deliberately FORCE re-captures every row in the window by calling
``IngestService.capture`` directly, appending a fresh wide raw_event per row.
Old narrow rows stay as immutable evidence; the new rows are the fuller copy.

Dry-run by DEFAULT — counts only. Pass ``--apply`` to actually write raw_events.
Scope (resolved for the mission): 2026 year-to-date. This is a deliberate,
potentially large operator action; run it intentionally, watch raw_event growth.

    set -a && . ./.env && set +a
    # preview one object, a few rows:
    PYTHONPATH=. .venv/bin/python infra/scripts/backfill_sf_full_fidelity.py \
        --object Lead --max-rows 5
    # real run for 2026-YTD, all objects:
    PYTHONPATH=. .venv/bin/python infra/scripts/backfill_sf_full_fidelity.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from uuid import UUID

from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.schemas import RawEventIn
from packages.ingest.service import IngestService
from packages.ingest.sf_account_service import _SF_ACCOUNT_COLUMNS
from packages.ingest.sf_case_service import _SF_CASE_COLUMNS
from packages.ingest.sf_contact_service import _SF_CONTACT_COLUMNS
from packages.ingest.sf_event_service import _SF_EVENT_COLUMNS
from packages.ingest.sf_lead_service import _SF_LEAD_PROJECTION
from packages.ingest.sf_opportunity_history_service import (
    _SF_OPPORTUNITY_HISTORY_COLUMNS,
)
from packages.ingest.sf_opportunity_service import _SF_OPPORTUNITY_COLUMNS
from packages.ingest.sf_schema_sync import SF_FULL_FIDELITY_OBJECTS, SfSchemaSync
from packages.ingest.sf_task_service import _SF_TASK_COLUMNS
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.tokens import SfTokens
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

_TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))

# SF object → the canonical raw_event ``event_type`` it is captured under, so
# the widened evidence shares the same key family as the original pull.
# Per-object static projection, so the dynamic projection preserves relationship
# fields (Owner.Name, CreatedBy.Name) that a describe-only field set cannot
# express — otherwise the backfill would drop the creator/owner names.
_STATIC_PROJECTION: dict[str, str] = {
    "Lead": _SF_LEAD_PROJECTION,
    "Contact": _SF_CONTACT_COLUMNS,
    "Account": _SF_ACCOUNT_COLUMNS,
    "Opportunity": _SF_OPPORTUNITY_COLUMNS,
    "Event": _SF_EVENT_COLUMNS,
    "Task": _SF_TASK_COLUMNS,
    "Case": _SF_CASE_COLUMNS,
    "OpportunityHistory": _SF_OPPORTUNITY_HISTORY_COLUMNS,
}

_EVENT_TYPE: dict[str, str] = {
    "Lead": "lead.pull",
    "Contact": "salesforce.contact.upsert",
    "Account": "salesforce.account.upsert",
    "Opportunity": "salesforce.opportunity.upsert",
    "Event": "salesforce.event.upsert",
    "Task": "salesforce.task.upsert",
    "Case": "salesforce.case.upsert",
    "OpportunityHistory": "salesforce.opportunity_history.upsert",
}


def _soql_literal(created_date: str) -> str:
    """Normalize an SF ``CreatedDate`` (``...+0000``) to a SOQL ``...Z`` literal."""
    text = created_date.replace("+0000", "Z")
    if "." in text:  # drop milliseconds: 2026-06-14T18:12:27.000Z -> ...27Z
        head, _, tail = text.partition(".")
        text = head + ("Z" if tail.endswith("Z") else "")
    return text


async def _backfill_object(
    client: SfClient,
    ingest: IngestService,
    obj: str,
    *,
    since: str,
    batch: int,
    apply: bool,
    max_rows: int,
) -> tuple[int, int]:
    schema = SfSchemaSync(
        ingest,
        client,
        object_name=obj,
        static_projection=_STATIC_PROJECTION.get(obj, ""),
    )
    projection = await schema.projection(_TENANT_ID)
    cursor = since
    seen = 0
    captured = 0
    while True:
        soql = (
            f"SELECT {projection} FROM {obj} WHERE CreatedDate >= {cursor} "
            f"ORDER BY CreatedDate ASC LIMIT {batch}"
        )
        result = await client.soql(soql)
        records = result.get("records") or []
        if not records:
            break
        for rec in records:
            seen += 1
            if apply:
                await ingest.capture(
                    _TENANT_ID,
                    RawEventIn(
                        source="salesforce",
                        event_type=_EVENT_TYPE[obj],
                        external_id=str(rec.get("Id")) if rec.get("Id") else None,
                        received_at=datetime.now(UTC),
                        payload=rec,
                    ),
                )
                captured += 1
            if max_rows and seen >= max_rows:
                return seen, captured
        last_created = records[-1].get("CreatedDate")
        if len(records) < batch or not isinstance(last_created, str):
            break
        cursor = _soql_literal(last_created)
    return seen, captured


async def main() -> int:
    parser = argparse.ArgumentParser(description="SF full-fidelity history backfill")
    parser.add_argument("--since", default="2026-01-01T00:00:00Z")
    parser.add_argument("--object", default="all", help="one SF object or 'all'")
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument(
        "--max-rows", type=int, default=0, help="cap rows per object (0 = no cap)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="actually capture (default dry-run)"
    )
    args = parser.parse_args()

    objects = (
        list(SF_FULL_FIDELITY_OBJECTS)
        if args.object == "all"
        else [args.object]
    )
    if any(o not in _EVENT_TYPE for o in objects):
        print(f"FAIL: unknown object; choose from {list(_EVENT_TYPE)}")
        return 2

    async with async_session() as session:
        cred = IntegrationCredentialService(session)
        try:
            oauth = await cred.read_for(_TENANT_ID, "salesforce", "oauth_token")
        except NoCredentialError:
            print("FAIL: no salesforce oauth_token credential")
            return 2
        try:
            api_key = await cred.read_for(_TENANT_ID, "salesforce", "api_key")
        except NoCredentialError:
            api_key = None

        async def _persist(_tokens: SfTokens) -> None:
            pass

        client = SfClient.from_credential(
            oauth, on_refresh=_persist, api_key_payload=api_key
        )
        ingest = IngestService(session)
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[{mode}] since={args.since} objects={objects}")
        try:
            for obj in objects:
                seen, captured = await _backfill_object(
                    client,
                    ingest,
                    obj,
                    since=args.since,
                    batch=args.batch,
                    apply=args.apply,
                    max_rows=args.max_rows,
                )
                print(f"{obj:<20} seen={seen:>7} captured={captured:>7}")
        finally:
            await client.close()
        # Commit happens via async_session on clean exit (only matters with --apply).
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
