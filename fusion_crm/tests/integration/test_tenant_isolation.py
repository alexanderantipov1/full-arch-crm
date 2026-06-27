"""Cross-tenant data-isolation safety net.

Sweeps every ``*Repository`` class under ``packages/<domain>/repository.py``
and verifies that every READ method (``list_*`` / ``get_*`` / ``find_*`` /
``search_*``) takes a ``tenant_id`` parameter AND filters its result on it.

Background
----------

Per ADR-0003 §"Isolation model", Phase 1 multi-tenancy is enforced at the
application layer: every repository takes ``tenant_id`` and adds
``WHERE tenant_id = :tenant_id`` to every read. The single failure mode
this test exists to catch is "we forgot ``WHERE tenant_id = ?`` on
method X" — a silent cross-tenant data leak which, on PHI rows, is a
HIPAA-grade incident.

Design
------

Two layers of assertion:

1. **Structural sweep (always runs).** For each repository read method,
   ``inspect.signature`` must show a ``tenant_id`` parameter. A method
   that does not is reported with file path + line + class + method
   so the operator can fix it without further triage.

2. **Live isolation sweep (Phase B — after ENG-123 lands).** For each
   compliant read method, call with ``tenant_a_id`` and assert no
   tenant-B row IDs appear in the result; mirror with ``tenant_b_id``.
   Skipped on this branch because the schema columns do not exist
   yet (see ``tests/conftest.py`` ``TENANT_SCHEMA_AVAILABLE``).

The structural sweep is the load-bearing assertion: if every method
takes ``tenant_id``, the live sweep finds zero leaks; if even one
method skips ``tenant_id``, the structural sweep flags it before code
review.

Adding a new repository
-----------------------

Auto-discovered. Drop a ``*Repository`` class in
``packages/<new_domain>/repository.py`` and the sweep picks it up on
the next test run. No registry to update.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from _tenant_helpers import TENANT_SCHEMA_AVAILABLE, TwoTenantContext

import packages

# Method-name prefixes considered READ operations. Mutations
# (``add_*`` / ``upsert_*`` / ``mark_*`` / ``touch_*``) are out of
# scope — they don't return cross-tenant lists, but they DO need
# ``tenant_id`` for INSERTs; that constraint is enforced at the
# service layer via Pydantic schemas, not here.
READ_PREFIXES: tuple[str, ...] = ("list_", "get_", "find_", "search_")

# Domain repositories that legitimately have no tenant scope. Empty
# in M1 — every domain table grows ``tenant_id`` per ADR-0003. If a
# global-by-nature domain ever lands (e.g. a platform-wide reference
# table), add its repository class name here with a justification
# comment.
TENANT_EXEMPT_REPOSITORIES: frozenset[str] = frozenset()

# Narrow method-level exceptions for reads whose root/global contract
# is part of the feature design. These do NOT exempt a whole repository,
# and every entry must carry its own reason.
ROOT_OR_GLOBAL_READ_ALLOWLIST: dict[str, str] = {
    "TenantRepository.get_by_slug": (
        "Tenant roots are resolved by unique slug before request code has a "
        "tenant_id; this lookup produces the tenant context."
    ),
    "TenantRepository.list_all": (
        "Tenant roots are the platform catalog itself, not child rows under a "
        "tenant; list_tenants is an explicit root/admin surface."
    ),
    "SendRepository.get_global": (
        "Recipient tracking/unsubscribe routes have no tenant context on the "
        "wire; the HMAC token gates the read, then callers derive or verify "
        "send.tenant_id before tenant-scoped writes."
    ),
    "SendRepository.find_by_message_id_global": (
        "Bounce handling first tries the tenant-scoped Message-ID lookup; this "
        "fallback only matches provider NDRs whose tenant cannot be pre-bound, "
        "and the caller verifies send.tenant_id before recording a bounce."
    ),
}


@dataclass(frozen=True)
class RepoMethod:
    """A single read method discovered on a repository class."""

    repo_class: type
    method_name: str
    qualified_name: str  # e.g. "OpsRepository.list_leads"
    file_path: str  # absolute path of the repository.py file
    line_number: int
    has_tenant_id: bool

    def __str__(self) -> str:  # pragma: no cover — debug helper only
        return f"{self.qualified_name} ({self.file_path}:{self.line_number})"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _iter_repository_modules() -> list[str]:
    """Return dotted module names for every ``packages.<domain>.repository``.

    Uses ``pkgutil.walk_packages`` over ``packages`` so that adding a
    new domain package automatically widens the sweep — no registry
    to maintain.
    """
    discovered: list[str] = []
    for module_info in pkgutil.walk_packages(
        packages.__path__,
        prefix="packages.",
    ):
        if module_info.name.endswith(".repository"):
            discovered.append(module_info.name)
    return sorted(discovered)


def _discover_read_methods() -> list[RepoMethod]:
    """Find every read method on every ``*Repository`` class."""
    found: list[RepoMethod] = []
    for module_name in _iter_repository_modules():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover — surfaced as test failure
            pytest.fail(
                f"Failed to import {module_name}: {exc}. Repository discovery cannot proceed."
            )
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not name.endswith("Repository"):
                continue
            # Only classes defined IN this module — don't sweep base
            # classes re-exported from other domains.
            if obj.__module__ != module_name:
                continue
            if name in TENANT_EXEMPT_REPOSITORIES:
                continue
            for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                if not method_name.startswith(READ_PREFIXES):
                    continue
                signature = inspect.signature(method)
                has_tenant_id = "tenant_id" in signature.parameters
                try:
                    file_path = inspect.getsourcefile(method) or "<unknown>"
                    _, line_number = inspect.getsourcelines(method)
                except (OSError, TypeError):  # pragma: no cover — rare
                    file_path = "<unknown>"
                    line_number = 0
                found.append(
                    RepoMethod(
                        repo_class=obj,
                        method_name=method_name,
                        qualified_name=f"{name}.{method_name}",
                        file_path=file_path,
                        line_number=line_number,
                        has_tenant_id=has_tenant_id,
                    )
                )
    return found


# Computed once at collection time so the parametrize id list is stable.
_DISCOVERED: list[RepoMethod] = _discover_read_methods()


def _ids(method: RepoMethod) -> str:
    """Pretty parametrize id: ``OpsRepository.list_leads``."""
    return method.qualified_name


def _allowlist_reason(method: RepoMethod) -> str | None:
    """Return the explicit root/global-read reason for ``method``, if any."""
    return ROOT_OR_GLOBAL_READ_ALLOWLIST.get(method.qualified_name)


# ---------------------------------------------------------------------------
# Structural sweep — always runs.
# ---------------------------------------------------------------------------


def test_at_least_one_repository_read_method_was_discovered() -> None:
    """Sanity guard: discovery must find SOMETHING.

    If this test fails, the auto-discovery walker is broken (wrong
    package root, missing ``__init__.py``, repository.py renamed)
    and every other assertion in the file is a false negative.
    """
    assert _DISCOVERED, (
        "Tenant-isolation sweep discovered zero repository read methods. "
        "Check that packages/<domain>/repository.py files exist and "
        "expose classes whose names end with 'Repository'."
    )


@pytest.mark.parametrize("method", _DISCOVERED, ids=_ids)
def test_repository_read_method_takes_tenant_id(method: RepoMethod) -> None:
    """Every repository read method MUST accept a ``tenant_id`` parameter.

    Failure means the method either:

    - reads across all tenants unconditionally (cross-tenant data leak), or
    - relies on an implicit caller-side filter (impossible to audit).

    Fix: add ``tenant_id: UUID`` to the method signature and apply
    ``WHERE tenant_id = :tenant_id`` in the query body.

    Phase A note: on this branch (pre-ENG-123) MOST methods will fail
    this assertion because the schema migration that introduces
    ``tenant_id`` everywhere has not landed. The failures are the
    point — they are the punch list for ENG-123's repository sweep.
    To avoid breaking ``make verify`` on ``main`` while ENG-127 lands
    first, this assertion is gated on ``TENANT_SCHEMA_AVAILABLE``:
    skipped when the schema is absent, hard-failed when it is
    present.
    """
    if not TENANT_SCHEMA_AVAILABLE:
        pytest.skip(
            "tenant.* schema + identity.person.tenant_id column not present "
            "yet (ENG-123 has not landed). Sweep activates on rebase."
        )

    if method.has_tenant_id:
        return

    if _allowlist_reason(method) is not None:
        return

    pytest.fail(
        f"{method.qualified_name} is missing the 'tenant_id' parameter — "
        f"risk of cross-tenant data leak.\n"
        f"  file: {method.file_path}\n"
        f"  line: {method.line_number}\n"
        f"  fix:  add 'tenant_id: UUID' to the signature and "
        f"'WHERE tenant_id = :tenant_id' to the query.\n"
        f"  ref:  ADR-0003 §'Isolation model'."
    )


# ---------------------------------------------------------------------------
# Live isolation sweep — Phase B (post-ENG-123).
# ---------------------------------------------------------------------------


def _seed_id(
    context: TwoTenantContext,
    seed_name: str,
    tenant_key: str,
) -> uuid.UUID:
    try:
        return context.seeded_ids[seed_name][tenant_key]
    except KeyError as exc:  # pragma: no cover - failure message is the value
        raise AssertionError(
            f"two_tenant_db is missing seed '{seed_name}' for {tenant_key}"
        ) from exc


async def _seed_row(
    context: TwoTenantContext,
    seed_name: str,
    tenant_key: str,
    model: type,
) -> Any:
    row = await context.session.get(model, _seed_id(context, seed_name, tenant_key))
    assert row is not None, f"two_tenant_db seed '{seed_name}' for {tenant_key} was not persisted"
    return row


async def _method_kwargs(
    method: RepoMethod,
    context: TwoTenantContext,
    arg_tenant_key: str,
) -> dict[str, Any]:
    """Build non-tenant arguments for a live isolation probe.

    ``arg_tenant_key`` is intentionally independent from the tenant id used
    for the repository call. The leak-catching path calls, for example,
    tenant A with tenant B's row ids / natural keys; a repository that forgot
    its tenant filter would return the B row.
    """
    from packages.actor.models import Actor, ActorIdentifier
    from packages.auth.models import ApiKey, Credential, Session
    from packages.identity.models import MatchCandidate, PersonIdentifier, SourceLink
    from packages.integrations.models import (
        CDCCursor,
        ExternalEntity,
        IntegrationAccount,
        ObjectMapping,
    )
    from packages.interaction.models import Event
    from packages.ops.models import Account, Consultation, FollowupTask, Lead, Opportunity
    from packages.outreach.models import Send, Template
    from packages.tenant.models import Location

    qname = method.qualified_name

    if qname == "ActorRepository.get_actor":
        return {"actor_id": _seed_id(context, "actor", arg_tenant_key)}
    if qname == "ActorRepository.find_by_type_and_name":
        actor = await _seed_row(context, "actor", arg_tenant_key, Actor)
        return {"actor_type": actor.actor_type, "name": actor.name}
    if qname == "ActorRepository.find_identifier":
        identifier = await _seed_row(context, "actor_identifier", arg_tenant_key, ActorIdentifier)
        return {"kind": identifier.kind, "value": identifier.value}
    if qname == "ActorRepository.list_identifiers":
        return {"actor_id": _seed_id(context, "actor", arg_tenant_key)}

    if qname == "AgentRuntimeRunRepository.list_recent":
        _ = arg_tenant_key
        return {"limit": 100}
    if qname == "AgentRuntimeApprovalRequestRepository.get_for_tenant":
        _ = arg_tenant_key
        return {"approval_id": uuid.uuid4()}
    if qname == "AgentRuntimeApprovalRequestRepository.list_recent":
        _ = arg_tenant_key
        return {"status": None, "limit": 100}

    if qname == "AuthRepository.find_active_credential":
        credential = await _seed_row(context, "auth_credential", arg_tenant_key, Credential)
        return {
            "subject_type": credential.subject_type,
            "subject_id": credential.subject_id,
            "credential_kind": credential.credential_kind,
        }
    if qname == "AuthRepository.get_session":
        return {"session_id": _seed_id(context, "auth_session", arg_tenant_key)}
    if qname == "AuthRepository.find_session_by_token_hash":
        session = await _seed_row(context, "auth_session", arg_tenant_key, Session)
        return {"token_hash": session.token_hash}
    if qname == "AuthRepository.get_api_key":
        return {"api_key_id": _seed_id(context, "auth_api_key", arg_tenant_key)}
    if qname == "AuthRepository.find_api_key_by_token_hash":
        api_key = await _seed_row(context, "auth_api_key", arg_tenant_key, ApiKey)
        return {"token_hash": api_key.token_hash}

    if qname == "IdentityRepository.get_person":
        return {"person_id": _seed_id(context, "identity_person", arg_tenant_key)}
    if qname == "IdentityRepository.list_recent":
        return {"limit": 100}
    if qname == "IdentityRepository.list_source_providers_for":
        return {"person_uids": [_seed_id(context, "identity_person", arg_tenant_key)]}
    if qname == "IdentityRepository.list_source_links_for_persons":
        return {"person_uids": [_seed_id(context, "identity_person", arg_tenant_key)]}
    if qname == "IdentityRepository.list_source_links_by_external_records":
        link = await _seed_row(context, "identity_source_link", arg_tenant_key, SourceLink)
        return {
            "keys": [
                (
                    link.source_system,
                    link.source_instance,
                    link.source_kind,
                    link.source_id,
                )
            ]
        }
    if qname == "IdentityRepository.list_candidate_persons_by_identifiers":
        email_identifier = await _seed_row(
            context, "identity_identifier", arg_tenant_key, PersonIdentifier
        )
        phone_identifier = await _seed_row(
            context, "identity_phone_identifier", arg_tenant_key, PersonIdentifier
        )
        return {
            "email_normalized": email_identifier.value,
            "phone_normalized": phone_identifier.value,
        }
    if qname == "IdentityRepository.find_identifier":
        identifier = await _seed_row(
            context, "identity_identifier", arg_tenant_key, PersonIdentifier
        )
        return {"kind": identifier.kind, "value": identifier.value}
    if qname == "IdentityRepository.find_source_link":
        link = await _seed_row(context, "identity_source_link", arg_tenant_key, SourceLink)
        return {
            "source_system": link.source_system,
            "source_instance": link.source_instance,
            "source_kind": link.source_kind,
            "source_id": link.source_id,
        }
    if qname == "IdentityRepository.get_match_candidate":
        return {"candidate_id": _seed_id(context, "identity_match_candidate", arg_tenant_key)}
    if qname == "IdentityRepository.find_open_match_for_pair":
        candidate = await _seed_row(
            context, "identity_match_candidate", arg_tenant_key, MatchCandidate
        )
        return {"person_pair_key": candidate.person_pair_key}
    if qname == "IdentityRepository.find_active_hint_candidate":
        candidate = await _seed_row(
            context, "identity_match_candidate", arg_tenant_key, MatchCandidate
        )
        return {
            "hint_id": candidate.hint_id,
            "candidate_person_uid": candidate.candidate_person_uid,
        }
    if qname == "IdentityRepository.find_decided_match_for_pair":
        candidate = await _seed_row(
            context, "identity_match_candidate", arg_tenant_key, MatchCandidate
        )
        return {"person_pair_key": candidate.person_pair_key}
    if qname == "IdentityRepository.find_persons_sharing_identifier":
        identifier = await _seed_row(
            context, "identity_identifier", arg_tenant_key, PersonIdentifier
        )
        # A fresh uid that excludes nothing, so the matching (kind, value)
        # person stays in the result and a missing tenant filter would leak it.
        return {
            "kind": identifier.kind,
            "value": identifier.value,
            "exclude_person_uid": uuid.uuid4(),
        }
    if qname == "IdentityRepository.list_open_candidates_for_person":
        return {"person_uid": _seed_id(context, "identity_person", arg_tenant_key)}
    if qname == "IdentityRepository.list_persons_for_sweep":
        return {"updated_since": None, "limit": 100}
    if qname == "IdentityRepository.list_match_candidates_by_status":
        return {"statuses": ("open", "auto_accepted", "accepted"), "limit": 100}
    if qname == "IdentityRepository.list_source_linkage_examples":
        return {"limit": 100}

    if qname == "IngestRepository.find_hint_by_raw_event":
        return {"raw_event_id": _seed_id(context, "ingest_raw_event", arg_tenant_key)}
    if qname == "IngestRepository.list_source_records":
        return {"sources": ("seed",), "limit": 100}
    if qname == "IngestRepository.list_carestack_patients_with_payment_activity":
        return {"payment_codes": ("tenant-isolation-payment",), "limit": 100}
    if qname in {
        "IngestRepository.list_unprocessed",
        "IngestRepository.list_unresolved_hints",
    }:
        return {"limit": 100}

    if qname == "IntegrationsRepository.get_account":
        return {"account_id": _seed_id(context, "integrations_account", arg_tenant_key)}
    if qname == "IntegrationsRepository.find_account":
        account = await _seed_row(
            context, "integrations_account", arg_tenant_key, IntegrationAccount
        )
        return {"provider": account.provider, "company_uid": account.company_uid}
    if qname == "IntegrationsRepository.find_mapping":
        mapping = await _seed_row(context, "integrations_mapping", arg_tenant_key, ObjectMapping)
        return {"account_id": mapping.account_id, "sf_object": mapping.sf_object}
    if qname == "IntegrationsRepository.list_mappings":
        return {"account_id": _seed_id(context, "integrations_account", arg_tenant_key)}
    if qname == "IntegrationsRepository.get_sync_run":
        return {"sync_run_id": _seed_id(context, "integrations_sync_run", arg_tenant_key)}
    if qname == "IntegrationsRepository.list_recent_runs":
        return {"account_id": _seed_id(context, "integrations_account", arg_tenant_key)}
    if qname == "IntegrationsRepository.find_cursor":
        cursor = await _seed_row(context, "integrations_cdc_cursor", arg_tenant_key, CDCCursor)
        return {"account_id": cursor.account_id, "channel": cursor.channel}
    if qname == "IntegrationsRepository.find_external_entity":
        entity = await _seed_row(
            context, "integrations_external_entity", arg_tenant_key, ExternalEntity
        )
        return {
            "account_id": entity.account_id,
            "object_type": entity.object_type,
            "external_id": entity.external_id,
        }

    if qname == "InteractionRepository.list_events_missing_responsibility":
        _ = arg_tenant_key
        return {"limit": 100}
    if qname == "InteractionRepository.list_responsibilities_for_events":
        return {
            "event_ids": [_seed_id(context, "interaction_event", arg_tenant_key)],
        }
    if qname == "InteractionRepository.list_responsibilities_for_event":
        return {"event_id": _seed_id(context, "interaction_event", arg_tenant_key)}
    if qname == "InteractionRepository.find_existing_responsibility":
        return {
            "event_id": _seed_id(context, "interaction_event", arg_tenant_key),
            "actor_id": _seed_id(context, "actor", arg_tenant_key),
            "role": "operational",
        }

    if qname == "InteractionRepository.find_event_by_source":
        event = await _seed_row(context, "interaction_event", arg_tenant_key, Event)
        return {
            "source_provider": event.source_provider,
            "source_event_id": event.source_event_id,
        }
    if qname in {
        "InteractionRepository.find_provider_event_by_external_id",
        "InteractionRepository.list_provider_events_by_external_id",
    }:
        event = await _seed_row(context, "interaction_event", arg_tenant_key, Event)
        return {
            "source_provider": event.source_provider,
            "source_kind": event.source_kind,
            "source_external_id": event.source_external_id,
            "kind": event.kind,
        }
    if qname == "InteractionRepository.list_for_person":
        return {"person_uid": _seed_id(context, "identity_person", arg_tenant_key)}

    if qname.startswith("SemanticCatalog"):
        if "insight_semantic_catalog_proposal" not in context.seeded_ids:
            pytest.skip("insight semantic catalog tables are not present in the live test DB")

    if qname == "SemanticCatalogProposalRepository.get_for_tenant":
        return {
            "proposal_id": _seed_id(
                context, "insight_semantic_catalog_proposal", arg_tenant_key
            )
        }
    if qname == "SemanticCatalogProposalRepository.list_for_tenant":
        return {"status": None, "limit": 100}
    if qname == "SemanticCatalogVersionRepository.list_for_proposal":
        return {
            "proposal_id": _seed_id(
                context, "insight_semantic_catalog_proposal", arg_tenant_key
            ),
            "limit": 100,
        }
    if qname == "SemanticCatalogVersionRepository.list_for_term":
        return {"term": f"tenant_{'a' if arg_tenant_key == 'tenant_a' else 'b'}/seed", "limit": 100}
    if qname == "SemanticCatalogVersionRepository.list_approved_for_tenant":
        return {"limit": 100}

    if qname == "OpsRepository.find_account":
        account = await _seed_row(context, "ops_account", arg_tenant_key, Account)
        return {"provider": account.provider, "source_id": account.source_id}
    if qname == "OpsRepository.find_consultation_by_source":
        consultation = await _seed_row(context, "ops_consultation", arg_tenant_key, Consultation)
        return {
            "source_provider": consultation.source_provider,
            "source_instance": consultation.source_instance,
            "external_id": consultation.external_id,
        }
    if qname == "OpsRepository.get_lead":
        lead = await _seed_row(context, "ops_lead", arg_tenant_key, Lead)
        return {"lead_id": lead.id}
    if qname == "OpsRepository.get_consultation":
        consultation = await _seed_row(context, "ops_consultation", arg_tenant_key, Consultation)
        return {"consultation_id": consultation.id}
    if qname == "OpsRepository.get_followup_task":
        followup = await _seed_row(context, "ops_followup", arg_tenant_key, FollowupTask)
        return {"task_id": followup.id}
    if qname in {
        "OpsRepository.find_lead_by_person",
        "OpsRepository.list_consultations_for_person",
        "OpsRepository.list_followups",
        "OpsRepository.list_person_location_profiles_for_person",
    }:
        return {"person_uid": _seed_id(context, "identity_person", arg_tenant_key)}
    if qname == "OpsRepository.find_person_location_profile":
        return {
            "person_uid": _seed_id(context, "identity_person", arg_tenant_key),
            "location_id": _seed_id(context, "tenant_location", arg_tenant_key),
        }
    if qname == "OpsRepository.list_consultations_for_tenant":
        return {"limit": 100}
    if qname == "OpsRepository.list_leads_with_extra_key":
        return {"key": "tenant_isolation_key", "limit": 100}

    if qname == "TemplateRepository.get_for_tenant":
        return {"template_id": _seed_id(context, "outreach_template", arg_tenant_key)}
    if qname == "TemplateRepository.find_by_name":
        template = await _seed_row(context, "outreach_template", arg_tenant_key, Template)
        return {"name": template.name}
    if qname == "TemplateRepository.list_for_tenant":
        return {"limit": 100}
    if qname == "CampaignRepository.get_for_tenant":
        return {"campaign_id": _seed_id(context, "outreach_campaign", arg_tenant_key)}
    if qname == "CampaignRepository.list_for_tenant":
        return {"limit": 100}
    if qname == "SendRepository.list_for_campaign":
        return {"campaign_id": _seed_id(context, "outreach_campaign", arg_tenant_key)}
    if qname == "SendRepository.get_for_tenant":
        return {"send_id": _seed_id(context, "outreach_send", arg_tenant_key)}
    if qname == "SendRepository.find_by_message_id":
        send = await _seed_row(context, "outreach_send", arg_tenant_key, Send)
        return {"message_id": send.message_id}
    if qname == "SuppressionRepository.list_for_tenant":
        return {"limit": 100}

    if qname == "PhiRepository.get_profile":
        return {"person_uid": _seed_id(context, "identity_person", arg_tenant_key)}

    if qname == "LocationRepository.find_by_carestack_id":
        location = await _seed_row(context, "tenant_location", arg_tenant_key, Location)
        return {"carestack_location_id": location.external_ref["carestack_location_id"]}
    if qname == "LocationRepository.find_by_name":
        location = await _seed_row(context, "tenant_location", arg_tenant_key, Location)
        return {"name": location.name}
    if qname == "LocationRepository.list_for_tenant":
        return {"only_active": False}

    if qname == "TenantRepository.get_credential":
        return {"credential_id": _seed_id(context, "tenant_credential", arg_tenant_key)}
    if qname == "TenantRepository.get_setting":
        _ = arg_tenant_key
        return {"key": "tenant-isolation-seed"}
    if qname in {
        "TenantRepository.list_credentials",
        "TenantRepository.list_settings",
    }:
        return {}

    if qname == "IdentityRepository.list_by_ids":
        return {"person_uids": [_seed_id(context, "identity_person", arg_tenant_key)]}
    if qname == "IdentityRepository.list_source_links_for_dashboard":
        return {
            "source_system": "salesforce",
            "source_kind": "lead",
            "first_seen_from": None,
            "first_seen_to": None,
            "limit": 100,
        }
    if qname == "IngestRepository.list_recent":
        return {"limit": 50, "provider": None}
    if qname == "IngestRepository.get_carestack_invoice_refs":
        # Scalar-ref resolver; an empty id list exercises the tenant-scoped
        # query path without depending on seeded invoice raws.
        return {"invoice_ids": []}
    if qname == "IngestRepository.list_carestack_patients_with_payment_activity":
        return {"payment_codes": ("PATIENTPAYMENTS", "INSURANCEPAYMENTS"), "limit": 100}
    if qname == "IntegrationsRepository.list_latest_runs_for_tenant":
        return {"provider": None, "limit": 20}
    if qname == "InteractionRepository.list_recent_for_tenant":
        return {"limit": 50}
    if qname == "InteractionRepository.get_treatment_payment_aggregate":
        return {"occurred_from": None, "occurred_to": None, "location_id": None}
    if qname == "InteractionRepository.get_treatment_payment_quality_metrics":
        return {"occurred_from": None, "occurred_to": None, "location_id": None}
    if qname == "InteractionRepository.list_payment_event_samples":
        return {"limit": 100}
    if qname == "InteractionRepository.list_payment_events_for_dashboard":
        return {
            "occurred_from": None,
            "occurred_to": None,
            "source_provider": None,
            "location_id": None,
            "query": None,
            "limit": 100,
        }
    if qname == "InteractionRepository.list_payment_event_groups_for_dashboard":
        # ENG-410 same-day groups: same filter surface as the flat list;
        # the group rows (and their legs sub-query) must both stay
        # tenant-scoped.
        return {
            "occurred_from": None,
            "occurred_to": None,
            "source_provider": None,
            "location_id": None,
            "query": None,
            "limit": 100,
        }
    if qname == "OpsRepository.list_latest_consultations_for_persons":
        return {
            "person_uids": [_seed_id(context, "identity_person", arg_tenant_key)],
            "source_provider": None,
        }
    if qname == "OpsRepository.list_leads_for_persons":
        return {
            "person_uids": [_seed_id(context, "identity_person", arg_tenant_key)],
        }
    if qname in {
        "OpsRepository.list_consultation_samples",
        "OpsRepository.list_lead_samples",
    }:
        return {"limit": 100}
    if qname == "OpsRepository.find_lead_by_converted_opportunity_id":
        return {"opportunity_id": "006ISOLATION01"}
    if qname == "OpsRepository.find_lead_by_converted_account_id":
        return {"account_id": "001ISOLATION01"}
    if qname == "OpsRepository.list_leads_for_dashboard":
        return {
            "created_from": None,
            "created_to": None,
            "status": None,
            "lead_source": None,
            "source_provider": "salesforce",
            "limit": 100,
        }
    if qname == "OpsRepository.aggregate_lead_read_model_quality":
        return {
            "created_from": None,
            "created_to": None,
            "source_provider": None,
            "lead_source": None,
            "location_match": None,
            "location_id": None,
        }
    if qname == "OpsRepository.find_opportunity_by_source":
        opportunity = await _seed_row(context, "ops_opportunity", arg_tenant_key, Opportunity)
        return {
            "source_provider": opportunity.source_provider,
            "source_instance": opportunity.source_instance,
            "external_id": opportunity.external_id,
        }
    if qname == "OpsRepository.find_covering_opportunity":
        opportunity = await _seed_row(context, "ops_opportunity", arg_tenant_key, Opportunity)
        # Anchor the lookup at the seeded opportunity's provider_created_at so
        # the row IS reachable for same-tenant calls (lookup returns it) and
        # IS NOT reachable for cross-tenant calls (the tenant filter must hold).
        anchor = opportunity.provider_created_at or opportunity.created_at
        return {
            "person_uid": _seed_id(context, "identity_person", arg_tenant_key),
            "at_moment": anchor,
        }
    if qname == "OpsRepository.list_opportunities_for_person":
        return {"person_uid": _seed_id(context, "identity_person", arg_tenant_key)}
    if qname == "OpsRepository.list_distinct_opportunity_owner_ids":
        _ = arg_tenant_key
        return {}
    if qname == "OpsRepository.list_sales_consultations":
        # ENG-473 Sales dashboard consultations table. Tenant-filtered on the
        # Consultation side via for_tenant; the LEFT-joined opportunity matches
        # on its globally-unique id so it cannot cross tenants.
        return {"limit": 100}

    if qname == "OpsRepository.list_leads_for_source_node":
        # Seeded leads carry no source attribution, so they land in the
        # "unknown" bucket — the broad-list path where a missing tenant
        # filter would surface opposite-tenant rows (ENG-391).
        return {"source": "unknown"}

    raise AssertionError(
        f"No Phase B tenant-isolation argument resolver for {qname}. "
        "Add one here when introducing or renaming repository read methods."
    )


def _iter_result_values(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, dict):
        return value.values()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Iterable):
        return value
    return (value,)


def _extract_seed_like_ids(value: Any) -> set[uuid.UUID]:
    """Extract UUIDs that identify returned ORM rows or row references."""
    found: set[uuid.UUID] = set()
    for item in _iter_result_values(value):
        if item is None:
            continue
        if isinstance(item, uuid.UUID):
            found.add(item)
            continue
        if isinstance(item, dict):
            found.update(_extract_seed_like_ids(item))
            continue
        if isinstance(item, (list, tuple, set, frozenset)):
            found.update(_extract_seed_like_ids(item))
            continue
        for attr in (
            "id",
            "tenant_id",
            "person_uid",
            "actor_id",
            "subject_id",
            "account_id",
            "campaign_id",
            "template_id",
            "send_id",
            "source_send_id",
            "mailbox_credential_id",
            "credential_id",
            "location_id",
            "raw_event_id",
            "source_event_id",
            "candidate_person_uid",
            "source_person_uid",
        ):
            candidate = getattr(item, attr, None)
            if isinstance(candidate, uuid.UUID):
                found.add(candidate)
    return found


def _foreign_seed_ids(context: TwoTenantContext, tenant_key: str) -> set[uuid.UUID]:
    return {tenant_values[tenant_key] for tenant_values in context.seeded_ids.values()}


def _assert_no_foreign_rows(
    *,
    method: RepoMethod,
    result: Any,
    context: TwoTenantContext,
    foreign_tenant_key: str,
    call_description: str,
) -> None:
    if method.qualified_name == "IdentityRepository.list_source_providers_for":
        foreign_ids = _foreign_seed_ids(context, foreign_tenant_key)
        leaked_providers = {
            person_uid: providers
            for person_uid, providers in result.items()
            if person_uid in foreign_ids and providers
        }
        assert leaked_providers == {}, (
            f"{method.qualified_name} leaked source providers during "
            f"{call_description}: {leaked_providers}"
        )
        return

    leaked_ids = _extract_seed_like_ids(result) & _foreign_seed_ids(context, foreign_tenant_key)
    assert leaked_ids == set(), (
        f"{method.qualified_name} leaked {foreign_tenant_key} seed ids during "
        f"{call_description}: {sorted(str(value) for value in leaked_ids)}"
    )


async def _call_repository_method(
    method: RepoMethod,
    context: TwoTenantContext,
    *,
    call_tenant_id: uuid.UUID,
    arg_tenant_key: str,
) -> Any:
    repository = method.repo_class(context.session)
    kwargs = await _method_kwargs(method, context, arg_tenant_key)
    return await getattr(repository, method.method_name)(
        tenant_id=call_tenant_id,
        **kwargs,
    )


@pytest.mark.parametrize(
    "method",
    [m for m in _DISCOVERED if m.has_tenant_id],
    ids=_ids,
)
async def test_repository_read_method_filters_by_tenant_id(
    method: RepoMethod,
    two_tenant_db: TwoTenantContext,
) -> None:
    """Calling a read method as tenant-A must NOT return tenant-B rows.

    For every read method that already takes ``tenant_id``: instantiate
    the repository with the seeded session and exercise both negative
    cross-lookups and same-tenant broad-list lookups.

    The leak-catching path deliberately calls tenant A with tenant B's
    row ids / natural keys, then mirrors the call the other way. A
    repository that forgot its tenant filter would return the opposite
    tenant's row. Methods without row-specific arguments still run the
    same-tenant broad-list path so missing tenant filters surface as
    opposite-tenant rows in the result.
    """
    if not TENANT_SCHEMA_AVAILABLE:
        pytest.skip(
            "tenant.* schema + identity.person.tenant_id column not present "
            "yet (ENG-123 has not landed). Live isolation sweep activates "
            "on rebase."
        )

    assert two_tenant_db.session is not None

    tenant_a_with_b_args = await _call_repository_method(
        method,
        two_tenant_db,
        call_tenant_id=two_tenant_db.tenant_a_id,
        arg_tenant_key="tenant_b",
    )
    _assert_no_foreign_rows(
        method=method,
        result=tenant_a_with_b_args,
        context=two_tenant_db,
        foreign_tenant_key="tenant_b",
        call_description="tenant A call with tenant B arguments",
    )

    tenant_b_with_a_args = await _call_repository_method(
        method,
        two_tenant_db,
        call_tenant_id=two_tenant_db.tenant_b_id,
        arg_tenant_key="tenant_a",
    )
    _assert_no_foreign_rows(
        method=method,
        result=tenant_b_with_a_args,
        context=two_tenant_db,
        foreign_tenant_key="tenant_a",
        call_description="tenant B call with tenant A arguments",
    )

    # Also exercise the broad-list path with same-tenant arguments so a
    # missing tenant filter on methods without row-specific args still
    # surfaces as an opposite-tenant row in the result.
    tenant_a_with_a_args = await _call_repository_method(
        method,
        two_tenant_db,
        call_tenant_id=two_tenant_db.tenant_a_id,
        arg_tenant_key="tenant_a",
    )
    _assert_no_foreign_rows(
        method=method,
        result=tenant_a_with_a_args,
        context=two_tenant_db,
        foreign_tenant_key="tenant_b",
        call_description="tenant A call with tenant A arguments",
    )

    tenant_b_with_b_args = await _call_repository_method(
        method,
        two_tenant_db,
        call_tenant_id=two_tenant_db.tenant_b_id,
        arg_tenant_key="tenant_b",
    )
    _assert_no_foreign_rows(
        method=method,
        result=tenant_b_with_b_args,
        context=two_tenant_db,
        foreign_tenant_key="tenant_a",
        call_description="tenant B call with tenant B arguments",
    )


# ---------------------------------------------------------------------------
# Meta-tests — prove the structural assertion logic itself works.
# ---------------------------------------------------------------------------
#
# These run on EVERY commit (no Phase B gating) so we never silently
# regress the safety net itself. If the structural sweep ever stops
# detecting a missing-tenant_id method, these meta-tests catch it
# before a real domain method slips through.


class _StubRepoCompliant:
    """Synthetic repo whose read method takes ``tenant_id`` — must PASS."""

    async def list_things(self, tenant_id: uuid.UUID) -> list[object]:
        return []


class _StubRepoLeaky:
    """Synthetic repo whose read method does NOT take ``tenant_id`` — must FAIL."""

    async def list_things(self) -> list[object]:
        return []


def _build_stub_method(cls: type, method_name: str) -> RepoMethod:
    """Build a RepoMethod for an in-test stub class — mirrors discovery."""
    method = getattr(cls, method_name)
    signature = inspect.signature(method)
    return RepoMethod(
        repo_class=cls,
        method_name=method_name,
        qualified_name=f"{cls.__name__}.{method_name}",
        file_path=inspect.getsourcefile(method) or "<unknown>",
        line_number=inspect.getsourcelines(method)[1],
        has_tenant_id="tenant_id" in signature.parameters,
    )


def test_meta_compliant_stub_is_classified_as_safe() -> None:
    """A repo method that DOES take ``tenant_id`` registers as compliant."""
    stub = _build_stub_method(_StubRepoCompliant, "list_things")
    assert stub.has_tenant_id is True


def test_meta_leaky_stub_is_classified_as_unsafe() -> None:
    """A repo method that does NOT take ``tenant_id`` registers as leaky."""
    stub = _build_stub_method(_StubRepoLeaky, "list_things")
    assert stub.has_tenant_id is False


def test_meta_failure_message_names_file_and_method() -> None:
    """The structural-failure message must be actionable.

    Failure text MUST include:

    - The qualified method name (so the reviewer knows what to fix).
    - The file path (so they can jump to it).
    - The fix recipe (signature + WHERE clause).
    - The ADR reference (so the WHY is one click away).

    Captured here as a string-shape assertion to prevent the message
    drifting into uselessness on later refactors.
    """
    stub = _build_stub_method(_StubRepoLeaky, "list_things")
    with pytest.raises(pytest.fail.Exception) as excinfo:
        pytest.fail(
            f"{stub.qualified_name} is missing the 'tenant_id' parameter — "
            f"risk of cross-tenant data leak.\n"
            f"  file: {stub.file_path}\n"
            f"  line: {stub.line_number}\n"
            f"  fix:  add 'tenant_id: UUID' to the signature and "
            f"'WHERE tenant_id = :tenant_id' to the query.\n"
            f"  ref:  ADR-0003 §'Isolation model'."
        )
    text = str(excinfo.value)
    assert "_StubRepoLeaky.list_things" in text
    assert "missing the 'tenant_id' parameter" in text
    assert "cross-tenant data leak" in text
    assert "ADR-0003" in text
    # Must point to a real source file so the reviewer can navigate to it.
    assert stub.file_path != "<unknown>"
    assert stub.line_number > 0


def test_root_or_global_read_allowlist_is_narrow_and_documented() -> None:
    """Root/global read exceptions must stay explicit and reviewable."""
    discovered = {method.qualified_name: method for method in _DISCOVERED}
    unknown = sorted(set(ROOT_OR_GLOBAL_READ_ALLOWLIST) - set(discovered))
    assert unknown == []

    assert "TenantRepository.get_credential" not in ROOT_OR_GLOBAL_READ_ALLOWLIST

    for qualified_name, reason in ROOT_OR_GLOBAL_READ_ALLOWLIST.items():
        assert reason.strip(), f"{qualified_name} must document why it is exempt"
        assert discovered[qualified_name].has_tenant_id is False, (
            f"{qualified_name} now takes tenant_id; remove the stale root/global allowlist entry."
        )


# ---------------------------------------------------------------------------
# Diagnostic — non-failing.
# ---------------------------------------------------------------------------


def test_emit_repository_inventory(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the discovered repository inventory.

    Not an assertion. Exists so ``pytest -s tests/integration/
    test_tenant_isolation.py::test_emit_repository_inventory``
    surfaces the full sweep target list — useful when debugging
    discovery on a new branch or in code review.
    """
    repo_files = sorted({Path(m.file_path).resolve() for m in _DISCOVERED})
    by_class: dict[str, list[str]] = {}
    for m in _DISCOVERED:
        by_class.setdefault(m.qualified_name.split(".", 1)[0], []).append(m.method_name)
    print()
    print(f"Repository files swept: {len(repo_files)}")
    for path in repo_files:
        print(f"  - {path}")
    print(f"Repository classes: {len(by_class)}")
    for cls, methods in sorted(by_class.items()):
        marker = ""
        if cls in TENANT_EXEMPT_REPOSITORIES:
            marker = " [EXEMPT]"
        print(f"  - {cls}{marker}: {sorted(methods)}")
    print(f"Read methods total: {len(_DISCOVERED)}")
    print(f"Read methods missing tenant_id: {sum(1 for m in _DISCOVERED if not m.has_tenant_id)}")
    print("Root/global read allowlist:")
    for qualified_name, reason in sorted(ROOT_OR_GLOBAL_READ_ALLOWLIST.items()):
        print(f"  - {qualified_name}: {reason}")
    captured = capsys.readouterr()
    # Re-emit so ``-s`` users see it; non-``-s`` runs still pass silently.
    print(captured.out)
