"""Salesforce Account ingest service (ENG-382).

Accounts are the organisation/patient container of the converted SF
funnel. This clinic's org creates one Account per converted lead, so an
Account links to a person through the lead that recorded its
``ConvertedAccountId``. Capturing accounts:

1. populates ``ops.account`` (existing model, previously 0 rows);
2. writes an ``identity.source_link`` with ``source_kind="account"``,
   which makes the Opportunity service's designed Account → person
   resolution path real (it probed the ``account`` source kind from
   day one — "future-proofing" now cashed in).

No timeline event: an account is person CONTEXT, not a person action;
the conversion moment itself is told by the opportunity/contact events.

Born watermark-first per ENG-381: incremental ``LastModifiedDate``
cursor + capture change-guard.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.identity.service import IdentityService
from packages.ingest.schemas import RawEventIn, SchemaDiffOut, SfAccountImportOut
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.ops.service import OpsService

logger = logging.getLogger(__name__)


class SfAccountClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Account ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


_SF_ACCOUNT_EVENT_TYPE = "salesforce.account.upsert"
# Static fallback projection (ENG-427); normal pulls use the dynamic projection.
_SF_ACCOUNT_COLUMNS = (
    "Id, Name, Phone, Type, OwnerId, CreatedDate, LastModifiedDate"
)
# Ascending order is load-bearing for the watermark cursor (ENG-381).
_SF_ACCOUNT_SOQL = (
    "SELECT {projection} FROM Account "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)


class SfAccountIngestService:
    """Pull SF Accounts, capture raw, project ops.account, link persons."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfAccountClientProtocol,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._ops = OpsService(session)

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Account",
            static_projection=_SF_ACCOUNT_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_accounts(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 200,
    ) -> SfAccountImportOut:
        """Pull Accounts modified since the watermark (``days`` fallback)."""
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365", details={"days": days}
            )
        if limit < 1 or limit > 500:
            raise ValidationError(
                "limit must be between 1 and 500", details={"limit": limit}
            )

        watermark = await self._ingest.max_payload_watermark(
            tenant_id,
            event_type=_SF_ACCOUNT_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        body = await self._sf.soql(
            _SF_ACCOUNT_SOQL.format(
                projection=await self._projection(tenant_id),
                since=since,
                limit=limit,
            )
        )
        records: list[dict[str, Any]] = body.get("records", []) or []

        candidate_ids = [
            account_id
            for record in records
            if (account_id := _record_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_ACCOUNT_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        linked_count = 0
        for record in records:
            account_id = _record_id(record)
            name = record.get("Name")
            if account_id is None or not isinstance(name, str) or not name.strip():
                skipped_count += 1
                continue
            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(account_id) == stamp:
                unchanged_count += 1
                continue
            linked = await self._capture_account(
                tenant_id, record, account_id, name.strip()
            )
            imported_count += 1
            if linked:
                linked_count += 1

        return SfAccountImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
            linked_count=linked_count,
        )

    async def _capture_account(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        account_id: str,
        name: str,
    ) -> bool:
        """Capture raw + ops projection + best-effort person link.

        Returns True when an identity source link was written (or already
        existed) for the account.
        """
        await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_ACCOUNT_EVENT_TYPE,
                external_id=account_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        await self._ops.record_account(
            tenant_id,
            provider="salesforce",
            source_id=account_id,
            name=name,
        )

        person_uid = await self._ops.find_lead_person_by_converted_account(
            tenant_id, account_id
        )
        if person_uid is None:
            logger.info(
                "salesforce.account.no_person_link",
                extra={"account_id": account_id, "tenant_id": str(tenant_id)},
            )
            return False

        await self._identity.add_source_link(
            tenant_id,
            person_uid=person_uid,
            source_system="salesforce",
            source_kind="account",
            source_id=account_id,
        )
        return True


def _record_id(record: dict[str, Any]) -> str | None:
    raw = record.get("Id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None
