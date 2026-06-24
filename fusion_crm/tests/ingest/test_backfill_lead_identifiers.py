"""ENG-542 — service tests for the lead-person identifier backfill.

``IngestService.backfill_lead_person_identifiers`` reads lead-person hint
phone/email values and attaches them as ``identity.person_identifier`` rows
through the collision-safe ``IdentityService.attach_identifier`` primitive. The
contract we lock in:

* idempotent + collision-safe — tallies ``added`` / ``exists`` / ``collision``
  / ``invalid`` outcomes from the identity primitive;
* ``dry_run`` reports candidate counts and writes NOTHING;
* an ``added`` outcome writes exactly one append-only audit row per identifier
  when a principal is supplied; ``collision`` / ``exists`` write none.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.service import IngestService

_TENANT_ID = TenantId(uuid.uuid4())


def _service(
    candidates: list[tuple[uuid.UUID, str | None, str | None]],
    *,
    attach_results: list[str] | None = None,
) -> tuple[IngestService, MagicMock]:
    """Build an IngestService with mock repo + identity. Returns the service
    and the identity mock (for attach-call assertions)."""
    svc = IngestService(MagicMock())
    repo = MagicMock()
    repo.lead_person_identifier_hints = AsyncMock(return_value=candidates)
    identity = MagicMock()
    identity.attach_identifier = AsyncMock(side_effect=attach_results)
    svc._repo = repo  # type: ignore[attr-defined]
    svc._identity = identity  # type: ignore[attr-defined]
    return svc, identity


def _principal() -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.SYSTEM}),
        context={},
    )


@pytest.mark.asyncio
async def test_backfill_dry_run_reports_counts_and_writes_nothing() -> None:
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    svc, identity = _service(
        [
            (p1, "+19167307719", "a@x.com"),
            (p1, "+19167307719", None),  # same person, second hint
            (p2, None, "b@x.com"),
        ]
    )
    out = await svc.backfill_lead_person_identifiers(_TENANT_ID, dry_run=True)
    assert out == {"persons": 2, "candidates": 4}
    identity.attach_identifier.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_tallies_outcomes_without_principal() -> None:
    p1 = uuid.uuid4()
    svc, _ = _service(
        [(p1, "+19167307719", "shared@x.com")],
        attach_results=["added", "collision"],
    )
    out = await svc.backfill_lead_person_identifiers(_TENANT_ID)
    assert out["persons"] == 1
    assert out["added"] == 1
    assert out["collision"] == 1
    assert out["exists"] == 0


@pytest.mark.asyncio
async def test_backfill_audits_only_added_rows() -> None:
    p1 = uuid.uuid4()
    svc, _ = _service(
        [(p1, "+19167307719", "shared@x.com")],
        attach_results=["added", "collision"],
    )
    audit_instance: Any = MagicMock()
    audit_instance.record = AsyncMock()
    with patch(
        "packages.ingest.service.AuditService", return_value=audit_instance
    ) as audit_cls:
        out = await svc.backfill_lead_person_identifiers(
            _TENANT_ID, principal=_principal()
        )
    assert out["added"] == 1
    audit_cls.assert_called_once()
    # Exactly one audit row — for the single ``added`` identifier, not the
    # ``collision``.
    audit_instance.record.assert_awaited_once()
    kwargs = audit_instance.record.await_args.kwargs
    assert kwargs["action"] == "identity.identifier.backfill"
    assert kwargs["extra"] == {"kind": "phone", "source": "salesforce_lead_hint"}
