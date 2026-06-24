"""Top-level pytest fixtures for the Fusion CRM platform test suite.

Currently houses the ``two_tenant_db`` fixture used by
``tests/integration/test_tenant_isolation.py``. That fixture is the
schema-wide cross-tenant data-leak safety net required by ADR-0003
§"Isolation model".

## Phase A vs Phase B

This branch (ENG-127) lands BEFORE ENG-123 (the schema migration that
adds ``tenant_id`` columns to every domain table and creates the
``tenant.*`` schema). Without those columns, we cannot seed real
per-tenant rows or run live cross-tenant assertions.

What this file ships in Phase A:

- The ``two_tenant_db`` fixture and ``TwoTenantContext`` dataclass
  (defined in ``tests/_tenant_helpers.py``) — the structural
  contract — so dependent test files import cleanly and
  ``pytest --collect-only`` does not error out.
- A capability flag ``TENANT_SCHEMA_AVAILABLE`` that downstream
  tests use to ``pytest.skip`` themselves when the schema is not
  ready. Today the flag is ``False`` on this branch; once ENG-123
  merges to main and we rebase onto it, the flag becomes ``True``
  and the fixture's body wires up real ORM seeding.

Do NOT add fake / mock-tenant assertions in Phase A. The whole point
of the safety net is that it asserts the real DB shape — anything
weaker hides the bug it exists to catch.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from _tenant_helpers import TENANT_SCHEMA_AVAILABLE, TwoTenantContext
from sqlalchemy import text


@pytest.fixture
async def two_tenant_db() -> AsyncIterator[TwoTenantContext]:
    """Two-tenant DB fixture for cross-tenant isolation testing.

    ## Contract (Phase B target)

    1. Creates two ``tenant.tenant`` rows (slugs ``tenant-a`` /
       ``tenant-b``).
    2. Seeds one row per tenant in each tenant-scoped read target used
       by the live sweep: tenant config/location/credential,
       identity, actor, auth, interaction, audit, ingest,
       integrations, ops, outreach, and phi. Per-row values are
       clearly distinguishable (``name="Person A"`` vs
       ``name="Person B"``) so any leak is obvious in a test failure.
    3. Yields ``TwoTenantContext(session, tenant_a_id, tenant_b_id,
       seeded_ids)``.
    4. On teardown, rolls back the session — keeps the suite
       hermetic without DDL noise. (Real-DB fixture style: see
       ``packages/db/session.py`` ``async_session()`` for the
       rollback pattern this mirrors.)

    On Phase A branches (no tenant schema / no tenant-scoped identity
    columns), yields the structural contract with ``session=None`` so
    collection stays clean and Phase B tests can skip explicitly.
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    if not TENANT_SCHEMA_AVAILABLE:
        # Phase A — yield the structural contract without a real session.
        yield TwoTenantContext(
            session=None,
            tenant_a_id=tenant_a_id,
            tenant_b_id=tenant_b_id,
            seeded_ids={},
        )
        return

    from packages.actor.models import Actor, ActorIdentifier
    from packages.audit.models import AccessLog
    from packages.auth.models import ApiKey, Credential, Session
    from packages.db.session import SessionFactory, engine
    from packages.identity.models import (
        MatchCandidate,
        Person,
        PersonIdentifier,
        SourceLink,
        make_person_pair_key,
    )
    from packages.ingest.models import NormalizedPersonHint, RawEvent
    from packages.insight.models import SemanticCatalogProposal, SemanticCatalogVersion
    from packages.integrations.models import (
        GLOBAL_COMPANY_UID,
        CDCCursor,
        ExternalEntity,
        IntegrationAccount,
        ObjectMapping,
        SyncRun,
    )
    from packages.interaction.models import Event, EventResponsibility
    from packages.interaction.service import summary_for_event
    from packages.ops.models import (
        Account,
        FollowupTask,
        Lead,
        Opportunity,
        PersonLocationProfile,
    )
    from packages.ops.models import (
        Consultation as OpsConsultation,
    )
    from packages.outreach.models import Campaign, Send, Suppression, Template
    from packages.phi.models import Consultation, PatientProfile
    from packages.tenant.models import IntegrationCredential, Location, Setting, Tenant

    session = SessionFactory()
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:12]
    insight_catalog_tables_available = bool(
        await session.scalar(
            text(
                "SELECT to_regclass('insight.semantic_catalog_proposal') IS NOT NULL "
                "AND to_regclass('insight.semantic_catalog_version') IS NOT NULL"
            )
        )
    )

    def label(tenant_key: str) -> str:
        return "A" if tenant_key == "tenant_a" else "B"

    def email(tenant_key: str) -> str:
        return f"tenant-{label(tenant_key).lower()}-{suffix}@example.test"

    seeded_ids: dict[str, dict[str, uuid.UUID]] = {}

    def remember(name: str, tenant_key: str, value: uuid.UUID) -> None:
        seeded_ids.setdefault(name, {})[tenant_key] = value

    try:
        for tenant_key, tenant_id in (
            ("tenant_a", tenant_a_id),
            ("tenant_b", tenant_b_id),
        ):
            marker = label(tenant_key)
            tenant = Tenant(
                id=tenant_id,
                slug=f"tenant-{marker.lower()}-{suffix}",
                name=f"Tenant {marker}",
                primary_email=email(tenant_key),
            )
            session.add(tenant)
            remember("tenant", tenant_key, tenant.id)
            await session.flush()

            location = Location(
                tenant_id=tenant_id,
                name=f"Location {marker}",
                external_ref={"carestack_location_id": 9000 + (1 if marker == "A" else 2)},
            )
            setting = Setting(
                tenant_id=tenant_id,
                key="tenant-isolation-seed",
                value={"tenant": marker},
            )
            integration_credential = IntegrationCredential(
                tenant_id=tenant_id,
                provider_kind="carestack",
                credential_kind="api_key",
                display_name=f"Credential {marker}",
                payload={"token": f"seed-{marker}"},
                status="active",
            )
            session.add_all([location, setting, integration_credential])

            person = Person(
                tenant_id=tenant_id,
                given_name=f"Person {marker}",
                family_name="Seed",
                display_name=f"Person {marker} Seed",
            )
            other_person = Person(
                tenant_id=tenant_id,
                given_name=f"Candidate {marker}",
                family_name="Seed",
                display_name=f"Candidate {marker} Seed",
            )
            session.add_all([person, other_person])
            await session.flush()

            person_identifier = PersonIdentifier(
                tenant_id=tenant_id,
                person_id=person.id,
                kind="email",
                value=email(tenant_key),
            )
            phone_identifier = PersonIdentifier(
                tenant_id=tenant_id,
                person_id=person.id,
                kind="phone",
                value=f"+1555000{1 if marker == 'A' else 2:04d}",
            )
            source_link = SourceLink(
                tenant_id=tenant_id,
                person_uid=person.id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind="lead",
                source_id=f"sf-lead-{marker}-{suffix}",
                meta={"tenant": marker},
            )
            carestack_patient_source_link = SourceLink(
                tenant_id=tenant_id,
                person_uid=person.id,
                source_system="carestack",
                source_instance=f"carestack-{marker.lower()}-{suffix}",
                source_kind="patient",
                source_id=f"cs-patient-{marker}-{suffix}",
                meta={"tenant": marker},
            )
            match_candidate = MatchCandidate(
                tenant_id=tenant_id,
                hint_id=uuid.uuid4(),
                source_person_uid=other_person.id,
                candidate_person_uid=person.id,
                status="open",
                match_rule="email_name",
                confidence=Decimal("0.9000"),
                evidence={"seed": marker},
                conflicts={},
                person_pair_key=make_person_pair_key(other_person.id, person.id),
            )
            session.add_all(
                [
                    person_identifier,
                    phone_identifier,
                    source_link,
                    carestack_patient_source_link,
                    match_candidate,
                ]
            )

            lead = Lead(
                tenant_id=tenant_id,
                person_uid=person.id,
                source=f"seed-{marker}",
                extra={"tenant_isolation_key": marker},
            )
            account = Account(
                tenant_id=tenant_id,
                provider="salesforce",
                source_id=f"sf-account-{marker}-{suffix}",
                name=f"Account {marker}",
            )
            followup = FollowupTask(
                tenant_id=tenant_id,
                person_uid=person.id,
                title=f"Follow up {marker}",
            )
            actor = Actor(
                tenant_id=tenant_id,
                actor_type="human",
                name=f"Actor {marker}",
                email=email(tenant_key),
                person_uid=person.id,
            )
            raw_event = RawEvent(
                tenant_id=tenant_id,
                source="seed",
                event_type="tenant.seed",
                external_id=f"raw-{marker}-{suffix}",
                received_at=now,
                payload={"tenant": marker},
            )
            carestack_payment_raw_event = RawEvent(
                tenant_id=tenant_id,
                source="carestack",
                event_type="carestack.accounting_transaction.upsert",
                external_id=f"cs-payment-{marker}-{suffix}",
                received_at=now,
                payload={
                    "patientId": carestack_patient_source_link.source_id,
                    "transactionCode": "tenant-isolation-payment",
                    "transactionType": "debit",
                    "amount": "42.00",
                },
            )
            access_log = AccessLog(
                tenant_id=tenant_id,
                principal_id=actor.id,
                principal_email=email(tenant_key),
                person_uid=person.id,
                action="seed.tenant",
                resource="tenant-isolation",
                reason=f"seed-{marker}",
                extra={"tenant": marker},
            )
            patient_profile = PatientProfile(
                tenant_id=tenant_id,
                person_uid=person.id,
                date_of_birth=date(1990, 1, 1),
                allergies={},
            )
            consultation = Consultation(
                tenant_id=tenant_id,
                person_uid=person.id,
                occurred_at=now - timedelta(days=1),
                chief_complaint="Seed fixture only",
            )
            ops_consultation = OpsConsultation(
                tenant_id=tenant_id,
                person_uid=person.id,
                source_provider="carestack",
                source_instance=f"carestack-{marker.lower()}-{suffix}",
                external_id=f"ops-consultation-{marker}-{suffix}",
                scheduled_at=now + timedelta(days=1),
                location_id=location.id,
            )
            opportunity = Opportunity(
                tenant_id=tenant_id,
                person_uid=person.id,
                source_provider="salesforce",
                source_instance=f"salesforce-{marker.lower()}-{suffix}",
                external_id=f"sf-opportunity-{marker}-{suffix}",
                name=f"Opportunity {marker}",
                stage="open",
                amount=Decimal("1000.00"),
                provider_created_at=now - timedelta(days=2),
                extra={
                    "tenant": marker,
                    "owner_id": f"005{marker}{suffix}",
                },
            )
            person_location_profile = PersonLocationProfile(
                tenant_id=tenant_id,
                person_uid=person.id,
                location_id=location.id,
                relationship_kind="prospect",
                relationship_status="consult_scheduled",
                last_evidence_provider="carestack",
                last_evidence_source_instance=f"carestack-{marker.lower()}-{suffix}",
                last_evidence_external_id=f"profile-{marker}-{suffix}",
                last_evidence_at=now,
            )
            session.add_all(
                [
                    lead,
                    account,
                    followup,
                    actor,
                    raw_event,
                    carestack_payment_raw_event,
                    access_log,
                    patient_profile,
                    consultation,
                    ops_consultation,
                    opportunity,
                    person_location_profile,
                ]
            )
            await session.flush()

            actor_identifier = ActorIdentifier(
                tenant_id=tenant_id,
                actor_id=actor.id,
                kind="email",
                value=email(tenant_key),
            )
            credential = Credential(
                tenant_id=tenant_id,
                subject_type="actor",
                subject_id=actor.id,
                credential_kind="password",
                secret_hash=f"hash-{marker}-{suffix}",
            )
            auth_session = Session(
                tenant_id=tenant_id,
                subject_type="actor",
                subject_id=actor.id,
                token_hash=f"session-token-{marker}-{suffix}",
                expires_at=now + timedelta(days=1),
            )
            api_key = ApiKey(
                tenant_id=tenant_id,
                name=f"API key {marker}",
                actor_id=actor.id,
                token_hash=f"api-token-{marker}-{suffix}",
                token_prefix=f"fcrm_{marker.lower()}",
                scopes=["seed"],
                created_by_actor_id=actor.id,
            )
            normalized_hint = NormalizedPersonHint(
                tenant_id=tenant_id,
                raw_event_id=raw_event.id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind="lead",
                source_id=f"hint-{marker}-{suffix}",
                observed_at=now,
                email_normalized=email(tenant_key),
                phone_normalized=phone_identifier.value,
                person_uid=None,
                hint_hash=f"hint-hash-{marker}-{suffix}",
                quality_flags={},
                meta={"tenant": marker},
            )
            integration_account = IntegrationAccount(
                tenant_id=tenant_id,
                provider=f"salesforce-{marker.lower()}-{suffix}",
                company_uid=GLOBAL_COMPANY_UID,
                meta={"tenant": marker},
            )
            session.add_all(
                [
                    actor_identifier,
                    credential,
                    auth_session,
                    api_key,
                    normalized_hint,
                    integration_account,
                ]
            )
            await session.flush()

            event = Event(
                tenant_id=tenant_id,
                person_uid=person.id,
                kind="lead_created",
                source_provider="salesforce",
                source_event_id=raw_event.id,
                data_class="operational",
                source_kind="salesforce_lead",
                source_external_id=f"sf-lead-{marker}-{suffix}",
                projection_ref_type="ops_lead",
                projection_ref_id=lead.id,
                review_status="auto",
                occurred_at=now,
                summary=summary_for_event(
                    kind="lead_created",
                    source_provider="salesforce",
                    source_id=f"sf-lead-{marker}-{suffix}",
                ),
                payload={"tenant": marker},
                created_by_actor_id=actor.id,
            )
            object_mapping = ObjectMapping(
                tenant_id=tenant_id,
                account_id=integration_account.id,
                sf_object=f"Lead{marker}",
                our_target="ops.lead",
                field_map={"tenant": marker},
            )
            sync_run = SyncRun(
                tenant_id=tenant_id,
                account_id=integration_account.id,
                sf_object=f"Lead{marker}",
                direction="pull",
                status="success",
            )
            cdc_cursor = CDCCursor(
                tenant_id=tenant_id,
                account_id=integration_account.id,
                channel=f"/data/LeadChangeEvent{marker}",
                replay_id=1 if marker == "A" else 2,
            )
            external_entity = ExternalEntity(
                tenant_id=tenant_id,
                account_id=integration_account.id,
                object_type="Lead",
                external_id=f"external-{marker}-{suffix}",
                person_uid=person.id,
                payload={"tenant": marker},
            )
            session.add_all([event, object_mapping, sync_run, cdc_cursor, external_entity])
            await session.flush()

            event_responsibility = EventResponsibility(
                tenant_id=tenant_id,
                event_id=event.id,
                actor_id=actor.id,
                role="operational",
            )
            session.add(event_responsibility)
            await session.flush()

            semantic_catalog_proposal = None
            semantic_catalog_version = None
            if insight_catalog_tables_available:
                semantic_catalog_proposal = SemanticCatalogProposal(
                    tenant_id=tenant_id,
                    raw_value=f"Tenant {marker} raw source",
                    source_system="salesforce",
                    source_field="LeadSource",
                    suggested_term=f"tenant_{marker.lower()}/seed",
                    definition=f"Tenant {marker} semantic catalog proposal.",
                    synonyms=[f"tenant-{marker.lower()}"],
                    confidence=0.9,
                    reason=f"tenant-isolation-{marker}",
                    reviewer_note="seed",
                    affected_questions=[f"Q-{marker}"],
                    affected_read_models=[f"read-model-{marker}"],
                    status="approved",
                    reviewed_by_actor_id=actor.id,
                    reviewed_at=now,
                )
                session.add(semantic_catalog_proposal)
                await session.flush()

                semantic_catalog_version = SemanticCatalogVersion(
                    tenant_id=tenant_id,
                    term=semantic_catalog_proposal.suggested_term,
                    version=1,
                    review_status="approved",
                    definition=semantic_catalog_proposal.definition,
                    synonyms=list(semantic_catalog_proposal.synonyms),
                    allowed_data_sources=["salesforce"],
                    data_classes=["operational"],
                    allowed_outputs=["analytics"],
                    canonical_fields=["LeadSource"],
                    row_level_fields=[],
                    aggregate_metrics=[],
                    used_by=[],
                    source_references=[],
                    proposal_id=semantic_catalog_proposal.id,
                    previous_value=None,
                    new_value={"term": semantic_catalog_proposal.suggested_term},
                    reason=semantic_catalog_proposal.reason,
                    affected_questions=list(semantic_catalog_proposal.affected_questions),
                    affected_read_models=list(
                        semantic_catalog_proposal.affected_read_models
                    ),
                    affected_reports=[],
                    affected_dashboard_panels=[],
                    affected_chat_answers=[],
                    affected_agent_briefs=[],
                    approved_by_actor_id=actor.id,
                    approved_at=now,
                )
                session.add(semantic_catalog_version)
                await session.flush()

            template = Template(
                tenant_id=tenant_id,
                name=f"Template {marker} {suffix}",
                subject_template=f"Subject {marker}",
                body_template=f"Body {marker}",
                body_format="markdown",
                category="marketing",
                status="active",
                created_by_actor_id=actor.id,
            )
            session.add(template)
            await session.flush()

            campaign = Campaign(
                tenant_id=tenant_id,
                template_id=template.id,
                name=f"Campaign {marker} {suffix}",
                recipient_query={"tenant": marker},
                mailbox_credential_id=integration_credential.id,
                mailbox_strategy="explicit",
                created_by_actor_id=actor.id,
            )
            session.add(campaign)
            await session.flush()

            send = Send(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                person_uid=person.id,
                recipient_email=email(tenant_key),
                message_id=f"message-{marker}-{suffix}@example.test",
                mailbox_credential_id=integration_credential.id,
                status="sent",
                sent_at=now,
            )
            session.add(send)
            await session.flush()

            suppression = Suppression(
                tenant_id=tenant_id,
                recipient_email_normalised=email(tenant_key),
                reason="operator",
                source_send_id=send.id,
            )
            session.add(suppression)
            await session.flush()

            for name, value in {
                "tenant_location": location.id,
                "tenant_credential": integration_credential.id,
                "identity_person": person.id,
                "identity_other_person": other_person.id,
                "identity_identifier": person_identifier.id,
                "identity_phone_identifier": phone_identifier.id,
                "identity_source_link": source_link.id,
                "identity_carestack_patient_source_link": carestack_patient_source_link.id,
                "identity_match_candidate": match_candidate.id,
                "ops_lead": lead.id,
                "ops_account": account.id,
                "ops_consultation": ops_consultation.id,
                "ops_followup": followup.id,
                "ops_opportunity": opportunity.id,
                "ops_person_location_profile": person_location_profile.id,
                "actor": actor.id,
                "actor_identifier": actor_identifier.id,
                "auth_credential": credential.id,
                "auth_session": auth_session.id,
                "auth_api_key": api_key.id,
                "interaction_event": event.id,
                "audit_access_log": access_log.id,
                "ingest_raw_event": raw_event.id,
                "ingest_carestack_payment_raw_event": carestack_payment_raw_event.id,
                "ingest_normalized_hint": normalized_hint.id,
                "integrations_account": integration_account.id,
                "integrations_mapping": object_mapping.id,
                "integrations_sync_run": sync_run.id,
                "integrations_cdc_cursor": cdc_cursor.id,
                "integrations_external_entity": external_entity.id,
                "outreach_template": template.id,
                "outreach_campaign": campaign.id,
                "outreach_send": send.id,
                "phi_profile": patient_profile.id,
                "phi_consultation": consultation.id,
            }.items():
                remember(name, tenant_key, value)
            if semantic_catalog_proposal is not None:
                remember(
                    "insight_semantic_catalog_proposal",
                    tenant_key,
                    semantic_catalog_proposal.id,
                )
            if semantic_catalog_version is not None:
                remember(
                    "insight_semantic_catalog_version",
                    tenant_key,
                    semantic_catalog_version.id,
                )

        await session.flush()
        yield TwoTenantContext(
            session=session,
            tenant_a_id=tenant_a_id,
            tenant_b_id=tenant_b_id,
            seeded_ids=seeded_ids,
        )
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()
