"""Reusable full-fidelity schema sync + dynamic projection for one SF object.

Block B of the Full-Fidelity Ingestion Framework (ENG-427). Every Salesforce
ingest service (Lead, Contact, Account, Opportunity, Event, Task, Case,
OpportunityHistory) shares the same need: refresh the schema registry from
``describe`` + Tooling and build the SOQL projection dynamically. This helper
holds that logic once so the per-object services only declare their object name
and static fallback.

The client is duck-typed (``soql`` + ``describe`` + ``describe_tooling_fields``)
to respect the ingest -> integrations import rule, exactly like the per-service
``*ClientProtocol`` definitions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from packages.core.logging import get_logger
from packages.core.types import TenantId

from .schemas import SchemaDiffOut
from .service import IngestService
from .sf_schema import build_observed_fields, fls_gap, selectable_fields

_log = get_logger("ingest.sf_schema")

# Every Salesforce object captured under the full-fidelity framework (ENG-427),
# by API name. The schema-refresh job (ENG-428) iterates these to keep the
# registry current and absorb newly-added fields. Keep in sync with the SF
# ingest services and ``_SF_OBJECT_SCOPE`` in the scheduled-pull job.
SF_FULL_FIDELITY_OBJECTS: tuple[str, ...] = (
    "Lead",
    "Contact",
    "Account",
    "Opportunity",
    "Event",
    "Task",
    "Case",
    "OpportunityHistory",
)


def _relationship_fields(static_projection: str) -> list[str]:
    """Relationship-traversal fields (e.g. ``Owner.Name``) from a static SELECT.

    A describe-driven projection captures the object's own scalar fields,
    including all ``*Id`` foreign keys, but NOT relationship traversals like
    ``Owner.Name`` / ``CreatedBy.Name`` — those are not fields on the object.
    Services that relied on such an expansion (ENG-408 owner-name enrichment)
    would regress, so we preserve them by carrying any dotted field from the
    static projection into the dynamic one.
    """
    return [
        field
        for raw in static_projection.split(",")
        if "." in (field := raw.strip())
    ]


class SfSchemaClientProtocol(Protocol):
    """Minimum SF client surface the schema sync needs."""

    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


class SfSchemaSync:
    """Full-fidelity schema registry sync + dynamic projection for one object."""

    def __init__(
        self,
        ingest: IngestService,
        sf_client: SfSchemaClientProtocol,
        *,
        object_name: str,
        static_projection: str = "",
    ) -> None:
        self._ingest = ingest
        self._sf = sf_client
        self._object_name = object_name
        self._static = static_projection

    async def sync(self, tenant_id: TenantId) -> tuple[SchemaDiffOut, list[str]]:
        """Reconcile describe + Tooling into the registry; return (diff, fls_gap)."""
        describe = await self._sf.describe(self._object_name)
        tooling = await self._sf.describe_tooling_fields(self._object_name)
        observed = build_observed_fields(describe, tooling)
        diff = await self._ingest.sync_object_schema(
            tenant_id,
            provider="salesforce",
            object_name=self._object_name,
            fields=observed,
            observed_at=datetime.now(UTC),
        )
        gap = fls_gap(describe, tooling)
        if gap:
            _log.info(
                "sf.schema.fls_gap",
                object_name=self._object_name,
                count=len(gap),
                fields=gap[:50],
            )
        return diff, gap

    async def projection(self, tenant_id: TenantId) -> str:
        """SOQL field list: registry first, then live describe, then static.

        Relationship-traversal fields from the static projection (e.g.
        ``Owner.Name``) are always appended — a describe-driven field set
        cannot express them, and dropping them would regress owner-name
        enrichment (ENG-408).
        """
        rows = await self._ingest.get_object_schema(
            tenant_id, provider="salesforce", object_name=self._object_name
        )
        base = [
            row.field_name
            for row in rows
            if row.readable and bool(row.meta.get("selectable", True))
        ]
        if not base:
            try:
                describe = await self._sf.describe(self._object_name)
                base = selectable_fields(describe)
            except Exception as exc:
                # Per packages/CLAUDE.md: ``except Exception`` only. Describe is
                # best-effort widening; the static projection keeps pulls working
                # (it already carries the relationship fields).
                _log.warning(
                    "sf.schema.describe_failed_fallback_static",
                    object_name=self._object_name,
                    error=str(exc)[:200],
                )
                return self._static
            if not base:
                return self._static

        seen = {field.lower() for field in base}
        extras = [
            field
            for field in _relationship_fields(self._static)
            if field.lower() not in seen
        ]
        return ", ".join(base + extras)
