"""Service-level tests for ops — D3 / ENG-4 additions.

Focus: ``record_account`` validation + idempotency, ``upsert_lead``
change-detection contract (insert / no-op / changed).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ops.models import Account, Lead
from packages.ops.service import OpsService, UpsertLeadResult

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service() -> tuple[OpsService, MagicMock]:
    session = MagicMock()
    service = OpsService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_lead_read_model_quality_evidence_reports_coverage_metrics() -> None:
    service, repo = _make_service()
    repo.aggregate_lead_read_model_quality = AsyncMock(
        return_value={
            "total_lead_count": 10,
            "identity_linked_lead_count": 10,
            "source_attributed_lead_count": 7,
            "unmatched_lead_count": 3,
            "location_assigned_center_mismatch_count": 1,
        }
    )

    result = await service.get_lead_read_model_quality_evidence(
        _TENANT_ID,
        read_model_id="lead_conversion",
        location_match=["El Dorado Hills"],
        location_id=uuid.uuid4(),
    )

    metrics_payload = result["metrics"]
    assert isinstance(metrics_payload, list)
    metrics = {
        str(metric["id"]): metric
        for metric in metrics_payload
        if isinstance(metric, dict)
    }
    assert metrics["identity_linkage_coverage"]["value"] == 1.0
    assert metrics["source_attribution_coverage"]["value"] == 0.7
    assert metrics["source_attribution_coverage"]["status"] == "caveat"
    assert metrics["unmatched_lead_count"]["value"] == 3
    assert metrics["location_assigned_center_mismatch_count"]["value"] == 1
    refs = result["refs"]
    assert isinstance(refs, list)
    assert "lead.person_uid" in refs
    assert result["blockers"] == []
    assert result["caveats"]


@pytest.mark.asyncio
async def test_lead_read_model_quality_evidence_omits_unresolved_location_metric() -> None:
    service, repo = _make_service()
    repo.aggregate_lead_read_model_quality = AsyncMock(
        return_value={
            "total_lead_count": 5,
            "identity_linked_lead_count": 5,
            "source_attributed_lead_count": 5,
            "unmatched_lead_count": 0,
            "location_assigned_center_mismatch_count": 0,
        }
    )

    result = await service.get_lead_read_model_quality_evidence(
        _TENANT_ID,
        read_model_id="lead_conversion",
        location_id=uuid.uuid4(),
    )

    metrics_payload = result["metrics"]
    assert isinstance(metrics_payload, list)
    metric_ids = [
        str(metric["id"]) for metric in metrics_payload if isinstance(metric, dict)
    ]
    assert "location_assigned_center_mismatch_count" not in metric_ids
    refs = result["refs"]
    assert isinstance(refs, list)
    assert "consultation.location_id" in refs
    assert "lead.assigned_center" not in refs


# --- record_account validation ---


@pytest.mark.asyncio
async def test_record_account_rejects_unknown_provider() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError) as excinfo:
        await service.record_account(
            _TENANT_ID,
            provider="zendesk",  # not in ACCOUNT_PROVIDERS
            source_id="1",
            name="x",
        )
    assert "unknown provider" in str(excinfo.value)


@pytest.mark.asyncio
async def test_record_account_rejects_empty_source_id() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.record_account(
            _TENANT_ID, provider="salesforce", source_id="", name="x"
        )


@pytest.mark.asyncio
async def test_record_account_rejects_empty_name() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.record_account(
            _TENANT_ID, provider="salesforce", source_id="001", name=""
        )


# --- record_account idempotency ---


@pytest.mark.asyncio
async def test_record_account_returns_existing_on_second_call() -> None:
    service, repo = _make_service()
    existing = Account(
        tenant_id=_TENANT_ID,
        provider="salesforce",
        source_id="0010001",
        name="Acme Co",
    )
    existing.id = uuid.uuid4()
    repo.find_account = AsyncMock(return_value=existing)
    repo.add_account = AsyncMock()

    result = await service.record_account(
        _TENANT_ID,
        provider="salesforce",
        source_id="0010001",
        name="Acme Co",
    )

    assert result is existing
    repo.add_account.assert_not_called()


@pytest.mark.asyncio
async def test_record_account_inserts_when_missing() -> None:
    service, repo = _make_service()
    repo.find_account = AsyncMock(return_value=None)

    captured: dict[str, Account] = {}

    async def _capture(account: Account) -> Account:
        captured["account"] = account
        return account

    repo.add_account = AsyncMock(side_effect=_capture)

    result = await service.record_account(
        _TENANT_ID,
        provider="salesforce",
        source_id="0010099",
        name="New Account",
        raw={"BillingCity": "Brooklyn"},
    )

    assert result is captured["account"]
    assert captured["account"].provider == "salesforce"
    assert captured["account"].source_id == "0010099"
    assert captured["account"].name == "New Account"
    assert captured["account"].raw == {"BillingCity": "Brooklyn"}
    assert captured["account"].tenant_id == _TENANT_ID


@pytest.mark.asyncio
async def test_record_account_refreshes_name_on_drift() -> None:
    """If a SF Account was renamed since last pull, refresh on idempotent call."""
    service, repo = _make_service()
    existing = Account(
        tenant_id=_TENANT_ID,
        provider="salesforce",
        source_id="0010001",
        name="Old Name",
    )
    existing.id = uuid.uuid4()
    repo.find_account = AsyncMock(return_value=existing)

    result = await service.record_account(
        _TENANT_ID,
        provider="salesforce",
        source_id="0010001",
        name="New Name",
    )

    assert result is existing
    assert existing.name == "New Name"


# --- upsert_lead change-detection ---


@pytest.mark.asyncio
async def test_upsert_lead_inserts_when_no_existing() -> None:
    service, repo = _make_service()
    person_uid = uuid.uuid4()
    repo.find_lead_by_person = AsyncMock(return_value=None)

    captured: dict[str, Lead] = {}

    async def _capture(lead: Lead) -> Lead:
        captured["lead"] = lead
        return lead

    repo.add_lead = AsyncMock(side_effect=_capture)

    result = await service.upsert_lead(
        _TENANT_ID,
        person_uid=person_uid,
        raw={"Status": "Open - Not Contacted", "LeadSource": "Web"},
    )

    assert isinstance(result, UpsertLeadResult)
    assert result.was_created is True
    assert result.was_changed is True
    assert result.lead is captured["lead"]
    assert result.lead.person_uid == person_uid
    assert result.lead.tenant_id == _TENANT_ID
    assert result.lead.extra["lead_status"] == "Open - Not Contacted"
    assert result.lead.extra["lead_source"] == "Web"


@pytest.mark.asyncio
async def test_upsert_lead_no_op_when_unchanged() -> None:
    """Re-pull with identical Status/LeadSource: was_changed=False, no row dirty."""
    service, repo = _make_service()
    existing = Lead(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        source="Web",
        extra={"lead_status": "Working - Contacted", "lead_source": "Web"},
    )
    existing.id = uuid.uuid4()
    repo.find_lead_by_person = AsyncMock(return_value=existing)
    repo.add_lead = AsyncMock()

    result = await service.upsert_lead(
        _TENANT_ID,
        person_uid=existing.person_uid,
        raw={"Status": "Working - Contacted", "LeadSource": "Web"},
    )

    assert result.was_created is False
    assert result.was_changed is False
    assert result.lead is existing
    repo.add_lead.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_lead_change_on_status_drift() -> None:
    """Re-pull with new Status: was_changed=True, was_created=False."""
    service, repo = _make_service()
    existing = Lead(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        source="Web",
        extra={"lead_status": "Open - Not Contacted", "lead_source": "Web"},
    )
    existing.id = uuid.uuid4()
    repo.find_lead_by_person = AsyncMock(return_value=existing)

    result = await service.upsert_lead(
        _TENANT_ID,
        person_uid=existing.person_uid,
        raw={"Status": "Working - Contacted", "LeadSource": "Web"},
    )

    assert result.was_created is False
    assert result.was_changed is True
    assert existing.extra["lead_status"] == "Working - Contacted"


@pytest.mark.asyncio
async def test_upsert_lead_change_on_source_drift() -> None:
    """Re-pull with new LeadSource: was_changed=True, source field also updated."""
    service, repo = _make_service()
    existing = Lead(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        source="Web",
        extra={"lead_status": "Open - Not Contacted", "lead_source": "Web"},
    )
    existing.id = uuid.uuid4()
    repo.find_lead_by_person = AsyncMock(return_value=existing)

    result = await service.upsert_lead(
        _TENANT_ID,
        person_uid=existing.person_uid,
        raw={"Status": "Open - Not Contacted", "LeadSource": "Phone Inquiry"},
    )

    assert result.was_changed is True
    assert existing.source == "Phone Inquiry"
    assert existing.extra["lead_source"] == "Phone Inquiry"


@pytest.mark.asyncio
async def test_upsert_lead_handles_none_status_gracefully() -> None:
    """SF rows occasionally arrive without ``Status`` set — store None on both
    sides and treat re-pull with None as no-op.
    """
    service, repo = _make_service()
    repo.find_lead_by_person = AsyncMock(return_value=None)

    captured: dict[str, Any] = {}

    async def _capture(lead: Lead) -> Lead:
        captured["lead"] = lead
        return lead

    repo.add_lead = AsyncMock(side_effect=_capture)

    result = await service.upsert_lead(
        _TENANT_ID, person_uid=uuid.uuid4(), raw={}
    )

    assert result.was_created is True
    assert captured["lead"].extra["lead_status"] is None
    assert captured["lead"].extra["lead_source"] is None


@pytest.mark.asyncio
async def test_upsert_lead_does_not_duplicate_raw_payload() -> None:
    """``Lead.extra`` must NOT carry the full raw row — that lives in
    ingest.raw_event. We only mirror the watched fields.
    """
    service, repo = _make_service()
    repo.find_lead_by_person = AsyncMock(return_value=None)

    captured: dict[str, Any] = {}

    async def _capture(lead: Lead) -> Lead:
        captured["lead"] = lead
        return lead

    repo.add_lead = AsyncMock(side_effect=_capture)

    big_raw = {
        "Id": "00Q5j000001abcd",
        "FirstName": "John",
        "LastName": "Smith",
        "Email": "john@example.com",
        "Status": "Open - Not Contacted",
        "LeadSource": "Web",
    }
    await service.upsert_lead(_TENANT_ID, person_uid=uuid.uuid4(), raw=big_raw)

    extra = captured["lead"].extra
    assert "FirstName" not in extra  # PII not duplicated
    assert "Email" not in extra
    assert "Id" not in extra  # raw lives in ingest.raw_event
    assert set(extra.keys()) == {"lead_status", "lead_source"}


@pytest.mark.asyncio
async def test_get_lead_source_profile_returns_aggregate_buckets() -> None:
    service, repo = _make_service()
    repo.count_leads_by_source = AsyncMock(
        return_value={"Google Ads": 3, "Website": 2}
    )

    result = await service.get_lead_source_profile(_TENANT_ID, limit=5)

    assert result.total_leads == 5
    assert [bucket.key for bucket in result.sources] == ["Google Ads", "Website"]
    repo.count_leads_by_source.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_conversion_funnel_analytics_uses_safe_counts() -> None:
    service, repo = _make_service()
    repo.count_leads_by_status = AsyncMock(
        return_value={"new": 4, "booked": 2, "lost": 1}
    )
    repo.count_consultations_by_status = AsyncMock(
        return_value={"scheduled": 2, "completed": 1}
    )

    result = await service.get_conversion_funnel_analytics(_TENANT_ID)

    assert result.pipeline_total == 6
    assert result.consultations_total == 3
    assert result.completed_consultations == 1


@pytest.mark.asyncio
async def test_get_paid_leads_analytics_returns_classifier_terms() -> None:
    service, repo = _make_service()
    repo.count_paid_leads_by_source = AsyncMock(return_value={"Google Ads": 7})

    result = await service.get_paid_leads_analytics(_TENANT_ID)

    assert result.total_paid_leads == 7
    assert result.sources[0].key == "Google Ads"
    assert "google" in result.classification_terms


@pytest.mark.asyncio
async def test_get_consultation_followup_analytics_combines_workload_counts() -> None:
    service, repo = _make_service()
    repo.count_consultations_by_status = AsyncMock(return_value={"scheduled": 3})
    repo.open_followup_count_for_tenant = AsyncMock(return_value=4)
    repo.overdue_followup_count_for_tenant = AsyncMock(return_value=2)

    result = await service.get_consultation_followup_analytics(
        _TENANT_ID,
        now=datetime.now(tz=UTC),
    )

    assert result.consultation_status[0].key == "scheduled"
    assert result.open_followups == 4
    assert result.overdue_followups == 2


# --- ENG-391 lead-source explorer ---


@pytest.mark.asyncio
async def test_get_lead_source_tree_builds_hierarchy_and_rolls_up() -> None:
    service, repo = _make_service()
    repo.count_lead_funnel_by_source_tree = AsyncMock(
        return_value=[
            ("Google Ads", "cpc", "implants-q2", 10),
            ("Google Ads", "cpc", "veneers-q2", 5),
            ("Google Ads", "unknown", "unknown", 2),
            ("unknown", "unknown", "unknown", 40),
        ]
    )
    repo.count_consultation_funnel_by_source_tree = AsyncMock(
        return_value=[
            ("Google Ads", "cpc", "implants-q2", "scheduled", 4),
            ("Google Ads", "cpc", "implants-q2", "completed", 3),
            ("Google Ads", "cpc", "veneers-q2", "completed", 1),
            ("unknown", "unknown", "unknown", "scheduled", 6),
        ]
    )

    result = await service.get_lead_source_tree(_TENANT_ID)

    assert result.total_leads == 57
    assert result.consults_scheduled == 10
    assert result.consults_attended == 4

    # Sibling order is leads-descending at every level. ENG-394: the top
    # level is the virtual channel — "Google Ads" groups under "google".
    assert [node.label for node in result.sources] == ["unknown", "google"]

    google = result.sources[1]
    assert google.level == "channel"
    assert google.leads == 17
    assert google.consults_scheduled == 4
    assert google.consults_attended == 4

    source_node = google.children[0]
    assert source_node.label == "Google Ads"
    assert source_node.level == "source"

    cpc = source_node.children[0]
    assert cpc.label == "cpc"
    assert cpc.level == "medium"
    assert cpc.leads == 15
    assert [c.label for c in cpc.children] == ["implants-q2", "veneers-q2"]
    implants = cpc.children[0]
    assert implants.key == "google/Google Ads/cpc/implants-q2"
    assert implants.level == "campaign"
    assert (implants.leads, implants.consults_scheduled, implants.consults_attended) == (
        10,
        4,
        3,
    )

    # Consultation query only asks for the two funnel statuses.
    statuses = repo.count_consultation_funnel_by_source_tree.await_args.kwargs["statuses"]
    assert statuses == ["scheduled", "completed"]


@pytest.mark.asyncio
async def test_get_lead_source_tree_counts_consults_for_lead_less_nodes() -> None:
    """A node can carry consultations even when search/period leaves 0 leads."""
    service, repo = _make_service()
    repo.count_lead_funnel_by_source_tree = AsyncMock(return_value=[])
    repo.count_consultation_funnel_by_source_tree = AsyncMock(
        return_value=[("Referral", "unknown", "unknown", "completed", 2)]
    )

    result = await service.get_lead_source_tree(_TENANT_ID)

    assert result.total_leads == 0
    assert result.consults_attended == 2
    assert result.sources[0].label == "Referral"


@pytest.mark.asyncio
async def test_list_leads_for_source_node_projects_attribution_allowlist() -> None:
    service, repo = _make_service()
    lead = Lead(
        person_uid=uuid.uuid4(),
        source=None,
        status="new",
        notes="patient mentioned allergy",  # must never surface
        extra={
            "lead_source": "Google Ads",
            "utm_medium": "cpc",
            "utm_campaign": "implants-q2",
            "sf_created_at": "2026-05-01T10:30:00.000+0000",
            "gclid": "abc123",
            "unexpected_key": "should not pass",
        },
    )
    lead.id = uuid.uuid4()
    lead.created_at = datetime(2026, 5, 2, tzinfo=UTC)
    repo.list_leads_for_source_node = AsyncMock(return_value=(1, [lead]))
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=lead.person_uid,
                display_name="Jane Implant",
                identifiers=[
                    SimpleNamespace(kind="email", value="jane@example.com"),
                    SimpleNamespace(kind="phone", value="+19165550100"),
                ],
            )
        ]
    )

    result = await service.list_leads_for_source_node(
        _TENANT_ID,
        source="google ads",
        collected_by_person={lead.person_uid: 2500.0},
    )

    assert result.total == 1
    item = result.items[0]
    assert item.source_label == "google ads"
    assert item.display_name == "Jane Implant"
    assert item.email == "jane@example.com"
    assert item.phone == "+19165550100"
    assert item.collected_amount == 2500.0
    assert item.utm_medium == "cpc"
    assert item.utm_campaign == "implants-q2"
    assert item.provider_created_at == datetime(2026, 5, 1, 10, 30, tzinfo=UTC)
    assert item.attribution["gclid"] == "abc123"
    assert "unexpected_key" not in item.attribution
    assert "notes" not in item.attribution


@pytest.mark.asyncio
async def test_list_leads_for_source_node_falls_back_to_created_at() -> None:
    service, repo = _make_service()
    lead = Lead(person_uid=uuid.uuid4(), source="Website", status="new", extra={})
    lead.id = uuid.uuid4()
    lead.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    repo.list_leads_for_source_node = AsyncMock(return_value=(1, [lead]))
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.list_by_ids = AsyncMock(return_value=[])

    result = await service.list_leads_for_source_node(_TENANT_ID, source="website")

    item = result.items[0]
    assert item.source_label == "website"
    assert item.display_name is None
    assert item.email is None
    assert item.phone is None
    assert item.collected_amount == 0.0
    assert item.utm_medium is None
    assert item.utm_campaign is None
    assert item.provider_created_at == item.created_at


@pytest.mark.asyncio
async def test_get_lead_source_tree_attributes_collected_cash() -> None:
    service, repo = _make_service()
    payer = uuid.uuid4()
    other_payer = uuid.uuid4()
    repo.count_lead_funnel_by_source_tree = AsyncMock(
        return_value=[
            ("Google Ads", "cpc", "implants-q2", 10),
            ("Referral", "unknown", "unknown", 3),
        ]
    )
    repo.count_consultation_funnel_by_source_tree = AsyncMock(return_value=[])
    repo.map_persons_to_source_nodes = AsyncMock(
        return_value=[
            ("Google Ads", "cpc", "implants-q2", payer),
            ("Referral", "unknown", "unknown", other_payer),
        ]
    )

    result = await service.get_lead_source_tree(
        _TENANT_ID,
        collected_by_person={payer: 12500.0, other_payer: 300.5},
    )

    assert result.collected_amount == 12800.5
    google = next(n for n in result.sources if n.label == "google")
    assert google.collected_amount == 12500.0
    campaign_node = google.children[0].children[0].children[0]
    assert campaign_node.collected_amount == 12500.0
    referral = next(n for n in result.sources if n.label == "Referral")
    assert referral.collected_amount == 300.5
    # Only the persons that actually have cash are mapped.
    mapped = repo.map_persons_to_source_nodes.await_args.kwargs["person_uids"]
    assert set(mapped) == {payer, other_payer}


@pytest.mark.asyncio
async def test_get_lead_source_tree_skips_person_mapping_without_cash() -> None:
    service, repo = _make_service()
    repo.count_lead_funnel_by_source_tree = AsyncMock(
        return_value=[("Website", "unknown", "unknown", 1)]
    )
    repo.count_consultation_funnel_by_source_tree = AsyncMock(return_value=[])
    repo.map_persons_to_source_nodes = AsyncMock()

    result = await service.get_lead_source_tree(_TENANT_ID, collected_by_person={})

    assert result.collected_amount == 0.0
    repo.map_persons_to_source_nodes.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_leads_flags_location_mismatch() -> None:
    service, repo = _make_service()
    stale = Lead(
        person_uid=uuid.uuid4(),
        source=None,
        status="new",
        extra={"lead_source": "Google Ads", "assigned_center": "Roseville"},
    )
    stale.id = uuid.uuid4()
    stale.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    native = Lead(
        person_uid=uuid.uuid4(),
        source=None,
        status="new",
        # NBSP variant must still count as matching (no false red flag).
        extra={"lead_source": "Google Ads", "assigned_center": "El Dorado Hills"},
    )
    native.id = uuid.uuid4()
    native.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    repo.list_leads_for_source_node = AsyncMock(return_value=(2, [stale, native]))
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.list_by_ids = AsyncMock(return_value=[])

    result = await service.list_leads_for_source_node(
        _TENANT_ID,
        source="google ads",
        location_match=["FUSION-EDH", "Fusion Dental Implants", "El Dorado Hills"],
        location_id=uuid.uuid4(),
    )

    by_center = {item.assigned_center: item for item in result.items}
    assert by_center["Roseville"].location_mismatch is True
    assert by_center["El Dorado Hills"].location_mismatch is False


@pytest.mark.asyncio
async def test_list_leads_no_mismatch_without_location_filter() -> None:
    service, repo = _make_service()
    lead = Lead(
        person_uid=uuid.uuid4(),
        source=None,
        status="new",
        extra={"lead_source": "Google Ads", "assigned_center": "Roseville"},
    )
    lead.id = uuid.uuid4()
    lead.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    repo.list_leads_for_source_node = AsyncMock(return_value=(1, [lead]))
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.list_by_ids = AsyncMock(return_value=[])

    result = await service.list_leads_for_source_node(_TENANT_ID, source="google ads")

    assert result.items[0].location_mismatch is False
