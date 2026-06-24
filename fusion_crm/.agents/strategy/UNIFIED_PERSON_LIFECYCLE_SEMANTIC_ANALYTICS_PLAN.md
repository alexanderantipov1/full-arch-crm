# Unified Person Lifecycle And Semantic Analytics Plan

## Purpose

This plan aligns the manager-provided unified patient / lead profile spec with
Fusion CRM's existing semantic analytics, provenance, context, and agent
architecture.

The manager spec is a strong business input. It describes the human need for
one operational view of a real person across Salesforce and CareStack:

- lead, source, owner, and attribution evidence from Salesforce;
- appointment, treatment, payment, production, and balance evidence from
  CareStack;
- lifecycle stages that managers can use across dashboards and reports;
- identity matching and manual merge handling;
- explicit write-back and audit rules.

Fusion CRM should use those requirements, but not copy the proposed database
shape literally. The platform already has stronger architectural boundaries:

```text
raw provider evidence
-> identity.person and source links
-> domain projections in ops / phi / interaction / future billing
-> semantic terms and context facts
-> approved read models and query registry
-> dashboard, manager chat, Data Intelligence Agent, context packs
-> controlled audited tools and later write-back
```

## Current Evidence Position

The read-only foundation can start from existing provider feeds and runtime
surfaces:

- Salesforce Lead ingest captures source, status, owner, business unit,
  assigned center, UTM fields, and consultation scheduled evidence.
- Salesforce Event, Task, Opportunity, and Case ingest already contribute to
  workflow-ready evidence and timeline direction.
- CareStack Patient ingest creates identity hints and source links.
- CareStack Appointment ingest creates ops-safe consultation projections and
  timeline events for scheduled, completed, no-show, cancelled, and
  rescheduled consultation states.
- CareStack Treatment Procedure ingest captures raw treatment evidence and
  emits safe lifecycle events.
- CareStack Invoice ingest captures invoice evidence and emits safe billing
  timeline events.
- CareStack Accounting Transaction ingest captures the ledger and emits
  payment timeline events for strict payment/refund/reversal codes.
- CareStack Payment Summary snapshots support outstanding balance and AR-risk
  aggregates.
- Manager analytics V1 already has approved aggregate query ids for lead
  source profile, conversion funnel, paid leads, consultation follow-up, and
  treatment revenue evidence.
- Data Intelligence Agent tooling already supports safe local discovery,
  profiling, linkage coverage, evidence coverage, bounded samples, semantic
  mapping proposals, and gap briefs.

This is enough to plan the next read-only lifecycle and semantic analytics
layer. The missing work is primarily semantic, contractual, and coverage
oriented, not a new provider integration wave.

## What The Manager Spec Confirms

The manager spec confirms the product direction:

1. Managers need one person-centered operational view, not separate Salesforce
   and CareStack dashboards.
2. Salesforce remains the source of truth for lead-side and attribution-side
   operational data.
3. CareStack remains the source of truth for clinical-adjacent, appointment,
   treatment, ledger, payment, and balance evidence.
4. Dashboards and manager chat need shared lifecycle terms such as consult
   scheduled, consult completed, treatment accepted, surgery scheduled,
   payment received, outstanding balance, and closed won.
5. Identity linkage quality is a business requirement because analytics are
   only reliable when Salesforce and CareStack evidence resolve to the same
   `person_uid`.
6. Write-back must be explicit and audited, but it is not the first execution
   slice.

## Architectural Translation

The manager spec should be translated into Fusion CRM architecture as follows.

| Manager concept | Fusion CRM translation |
| --- | --- |
| `patients` spine table | `identity.person.id` remains the canonical `person_uid`. |
| `patient_sf_links` | `identity.source_link` rows for Salesforce source objects. |
| `patient_cs_links` | `identity.source_link` rows for CareStack patient objects. |
| `patient_appointments` | `ops.consultation` and `interaction.event`; PHI fields stay out of `ops`. |
| `patient_treatment_plans` | CareStack raw evidence plus safe treatment lifecycle events; durable PHI/billing projections need later domain decisions. |
| `patient_payments` | CareStack accounting transactions and payment summaries through safe billing timeline events and aggregates. |
| `patient_attribution` | Salesforce lead/source/UTM projections and semantic source mappings. |
| `patient_stage_history` | Lifecycle timeline and future explicit stage-history read model. |
| `patient_writeback_log` | Later write-back router and audit trail, not in the read-only V1 slice. |
| Unified profile API | Service-owned person profile/context contract, not direct raw database or raw provider payload output. |
| AI profile access | Task-specific context packs and approved tools, not a full person dump. |

## Read-Only First Scope

The next execution direction should be read-only.

The goal is to define and later implement a governed lifecycle foundation that
lets dashboard, chat, reports, and internal agents ask reliable questions
without direct SQL, raw provider payloads, or full patient-record exposure.

Read-only V1 should include:

- source-of-truth precedence contract for Salesforce and CareStack fields;
- unified lifecycle stage taxonomy;
- source linkage and identity quality posture;
- semantic catalog extensions;
- query registry/read-model gaps;
- coverage audit across existing evidence;
- manager chat V2 scope boundaries;
- explicit deferral of write-back and external side effects.

Write-back should remain out of scope until profile contracts, source links,
lifecycle stages, policy, audit, and row-level worklists are stable.

## Candidate Semantic Terms

The semantic catalog should gain candidate terms for the next layer:

- `unified_person_profile`
- `person_profile_summary`
- `source_of_truth_precedence`
- `current_lifecycle_stage`
- `lifecycle_stage_history`
- `stage_transition`
- `identity_merge_candidate`
- `manual_merge_required`
- `salesforce_linked`
- `carestack_linked`
- `source_linkage_quality`
- `sync_freshness`
- `sync_drift`
- `reconcile_gap`
- `surgery_scheduled`
- `surgery_completed`
- `speed_to_lead`
- `speed_to_consult`
- `show_rate`
- `close_rate`
- `close_rate_by_owner`
- `treatment_acceptance_rate`
- `production_total`
- `collection_total`
- `outstanding_ar`
- `writeback_attempt`
- `writeback_succeeded`
- `writeback_failed`

These are candidate meanings, not approved catalog truth. They should enter
the normal proposal and human review path before they affect production
dashboard, chat, report, workflow, or agent behavior.

## Candidate Read Models

The next layer should define read-model contracts before implementation:

- `person_lifecycle_summary`
- `lifecycle_funnel`
- `lifecycle_stage_history`
- `revenue_by_source`
- `outstanding_balance`
- `identity_linkage_quality`
- `sync_reconcile_health`
- `source_attribution_quality`
- `consultation_no_next_action_worklist`
- `accepted_treatment_no_payment_worklist`

V1 can remain aggregate-first. Bounded row-level worklists should come after
field allowlists, data-class labels, row caps, role rules, and audit behavior
are explicit.

## Manager Chat Direction

Manager Chat V1 remains aggregate-only and deterministic. The next chat layer
can expand only through approved query specs and registry entries.

Allowed direction:

```text
manager question
-> catalog-backed structured query spec
-> policy preflight
-> allowlisted service/read model
-> result contract with definitions and warnings
-> explanation
-> audit
```

Denied direction:

- raw SQL;
- raw provider payload browsing;
- direct repository or database access;
- unrestricted full patient profile output;
- row-level billing or PHI-adjacent output without allowlists and audit;
- agent-initiated write-back.

Person-specific assistant behavior should use separate person-context tools or
task-specific context packs, not the aggregate analytics chat path.

## Known Gaps

The current evidence layer is strong enough to proceed, but the following gaps
must be handled explicitly:

1. Salesforce LeadHistory / status history is not yet an implemented source
   for authoritative stage history.
2. Salesforce Contact ingestion/linking may need a dedicated slice if
   converted leads and contacts become required for profile completeness.
3. CareStack treatment procedure status mapping needs finer semantics for
   proposed, accepted, scheduled, declined, and completed.
4. Surgery scheduled/completed classification needs reviewed appointment-type
   rules.
5. Production total, collection total, accepted amount, and balance semantics
   must not be mixed until the catalog defines each metric precisely.
6. Row-level billing and AR worklists need field allowlists, caps, roles, and
   audit rules.
7. Galleria OMS / CareStack coverage must be confirmed before cross-business
   unit analytics are treated as complete.
8. Current sync coverage and skipped-link counts should be audited before
   lifecycle read models are promoted.

## Recommended Mission Order

1. Read-only Unified Person Lifecycle Foundation V1.
2. Semantic catalog extension for lifecycle, linkage, source precedence, and
   revenue/balance terms.
3. Read model V2 contracts and implementation.
4. Bounded row-level manager worklists.
5. Manager Chat V2 over approved lifecycle and revenue queries.
6. Person context/profile tools for agent use.
7. Write-back governance and audited write router.

## Human Decisions Needed

1. Confirm the default attribution model: catalog default, first touch, last
   touch, or another reviewed model.
2. Confirm what `paid_lead` means in V2: any payment, deposit, paid in full,
   or catalog-specific variants.
3. Confirm who may see billing-sensitive row-level worklists.
4. Confirm whether Manager Chat V2 remains aggregate-only at first or may
   include bounded row-level worklists for authorized users.
5. Confirm whether Galleria OMS has CareStack access or should be treated as
   Salesforce-only until another adapter exists.
6. Confirm manual merge ownership: admin-only, TC-facing, or operator queue.
7. Confirm write-back remains deferred until read-only profile and lifecycle
   contracts stabilize.

## Readiness

Readiness status: `needs decision`.

The strategy is ready to hand to the Orchestrator for scope validation and
Linear planning, but execution should not begin until the human decisions above
are resolved or explicitly assigned to discovery tasks.
