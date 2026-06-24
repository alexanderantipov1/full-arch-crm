# Unified Person Lifecycle Foundation V1

## Summary

The manager-provided unified patient / lead profile spec confirms the next
semantic analytics direction: Fusion CRM needs a read-only, person-centered
lifecycle foundation across Salesforce and CareStack.

The request is valid from the human workflow side. Managers want one reliable
view of a real person:

- where the lead came from;
- who owns the lead or treatment workflow;
- whether consultation was scheduled, completed, missed, or stale;
- whether treatment was proposed, accepted, scheduled, or completed;
- whether payment, collection, production, or outstanding balance evidence
  exists;
- whether Salesforce and CareStack records are linked to the same person.

This does not mean Fusion CRM should implement a literal unified `patients`
table as the source of truth. The product architecture already has a stronger
foundation:

```text
identity.person.id
-> provider source links
-> ops / interaction / phi / future billing projections
-> semantic catalog terms and context facts
-> approved read models and query registry
-> dashboard, manager chat, reports, Data Intelligence Agent, context packs
```

## What We Already Have

The current system already captures most of the evidence needed for a read-only
first layer:

- Salesforce Lead ingest with lead source, status, business unit, assigned
  center, UTM fields, owner, and consultation scheduled fields.
- Salesforce Events, Tasks, Opportunities, and Cases through scheduled ingest.
- CareStack Patient ingest that creates identity hints and source links.
- CareStack Appointment ingest that creates safe consultation projections and
  timeline events.
- CareStack Treatment Procedure ingest that captures treatment evidence and
  emits safe lifecycle events.
- CareStack Invoice ingest that captures invoice evidence and emits billing
  timeline events.
- CareStack Accounting Transaction ingest that emits strict payment, refund,
  reversal, and applied-payment timeline events.
- CareStack Payment Summary snapshots that support outstanding balance and
  AR-risk aggregates.
- Aggregate analytics query ids for lead source profile, conversion funnel,
  paid leads, consultation follow-up, and treatment revenue evidence.
- Data Intelligence Agent local tools for discovery, profiling, linkage
  coverage, evidence coverage, bounded masked samples, mapping proposals, and
  gap briefs.

The next mission should therefore start from coverage, semantics, and
contracts, not from another broad data-pull project.

## What Changes In The Next Layer

### Human Surface

The human surface can show a unified operational view:

- person identity and source links;
- lifecycle stage;
- source/UTM attribution;
- consultation state;
- treatment and revenue evidence;
- outstanding balance posture;
- linkage and sync quality warnings.

The UI should still consume service-owned DTOs and read models. It should not
join raw provider payloads or reimplement metric logic in the browser.

### Analytics Surface

Semantic analytics should add lifecycle and profile terms such as:

- `current_lifecycle_stage`
- `lifecycle_stage_history`
- `source_of_truth_precedence`
- `source_linkage_quality`
- `sync_freshness`
- `sync_drift`
- `surgery_scheduled`
- `surgery_completed`
- `speed_to_lead`
- `speed_to_consult`
- `show_rate`
- `close_rate`
- `production_total`
- `collection_total`
- `outstanding_ar`

These terms should enter the normal catalog review flow. They are not approved
business truth until reviewed.

### Manager Chat Surface

Manager Chat V1 remains aggregate-only. A future Manager Chat V2 can expand
only through the same safe path:

```text
manager question
-> structured query spec
-> policy preflight
-> approved query registry entry
-> service-owned read model
-> explanation with definition versions and warnings
-> audit
```

Manager Chat must not browse raw payloads, generate SQL, or return a full
person profile. Person-specific assistant behavior should use separate
person-context tools or task-specific context packs.

### Agent Surface

Agents should receive task-specific context packs, not full records.

Examples:

- a speed-to-lead context pack;
- a consultation follow-up context pack;
- a treatment revenue status context pack;
- a source linkage quality context pack.

Each pack should declare purpose, allowed data classes, source references,
review status, PHI posture, tools, and approval boundary.

## Read-Only V1 Scope

Read-only V1 should define the contracts before implementation:

1. Requirements alignment brief.
2. Evidence coverage audit.
3. Salesforce versus CareStack source-of-truth precedence.
4. Lifecycle stage taxonomy.
5. Semantic catalog extension candidates.
6. Read-model V2 contracts.
7. Manager Chat V2 boundaries.
8. Write-back deferral brief.

Write-back is intentionally out of scope. It should become a later governance
mission after read-only contracts, source links, lifecycle semantics, row-level
policy, and audit behavior are stable.

## Known Gaps

The platform has enough evidence to plan and begin the read-only layer, but the
following gaps must be handled explicitly:

- Salesforce LeadHistory / status history is not yet the authoritative source
  for stage history.
- Salesforce Contact linking may need a dedicated follow-up if converted Lead
  and Contact records become required.
- CareStack treatment status needs finer mapping for proposed, accepted,
  scheduled, declined, and completed.
- Surgery scheduled/completed needs reviewed appointment-type classification.
- Production total, collection total, accepted amount, and balance semantics
  must be catalog-defined before they are used in chat or reports.
- Row-level billing and AR worklists need field allowlists, row caps, roles,
  and audit.
- Galleria OMS / CareStack coverage must be confirmed before cross-business
  unit analytics are treated as complete.
- Sync and backfill coverage must be audited before lifecycle read models are
  promoted.

## Recommended Order

1. Read-only unified person lifecycle foundation.
2. Semantic catalog extension for lifecycle and revenue/balance terms.
3. Read-model V2 contracts and implementation.
4. Bounded row-level manager worklists.
5. Manager Chat V2 over approved lifecycle and revenue queries.
6. Person context/profile tools for agents.
7. Write-back governance and audited write router.

## Human Decisions

The Orchestrator should not start implementation until these decisions are
resolved or assigned as discovery tasks:

- attribution model;
- `paid_lead` definition;
- billing row-level audience and field allowlists;
- Manager Chat V2 row-level posture;
- Galleria OMS / CareStack coverage;
- manual merge ownership;
- write-back deferral confirmation.

## Strategy Artifacts

Authoritative planning artifacts:

- `.agents/strategy/UNIFIED_PERSON_LIFECYCLE_SEMANTIC_ANALYTICS_PLAN.md`
- `.agents/strategy/CANDIDATE_MISSIONS.md`
- `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md`

Readiness status: `needs decision`.
