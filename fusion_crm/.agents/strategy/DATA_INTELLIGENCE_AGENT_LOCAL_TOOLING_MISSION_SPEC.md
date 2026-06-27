# Data Intelligence Agent Local Tooling V1 Mission Spec

## Status

- Strategy readiness: `ready for orchestrator`
- Strategy role: Architecture / Strategy
- Execution owner: Orchestrator
- Linear action: continue under the existing `Semantic Context And Analytics
  Foundation` Linear umbrella and create a child mission/issue tree there
- Product code changes in this document: none
- Worker launch authorization: not granted by this document

## Source Context

This mission follows the completed Semantic Context And Analytics Foundation
V1 work. ENG-279 created the Data Intelligence Agent contract, but it did not
implement the operational local tooling that lets the agent profile real local
data through approved service/tool boundaries.

Human-provided current state:

- The dashboard MSW handler for real backend data was removed by Claude Code.
- The next priority is Data Intelligence Agent local tooling.
- Internal production users are currently treated as authorized users; row-level
  visibility is acceptable for this phase when accessed through approved tools.
- Export expansion, scheduled reports, and broader production role matrices are
  later concerns.

Related source documents:

- `.agents/strategy/SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md`
- `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`
- `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`
- `.agents/orchestration/semantic-context-analytics-foundation/data-intelligence-agent-contract-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/analytics-query-registry-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/semantic-analytics-catalog-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/structured-analytics-query-spec-v1.md`

## Mission Title

Data Intelligence Agent Local Tooling V1

## Umbrella

Continue under the existing Linear umbrella:

`Semantic Context And Analytics Foundation`

Do not create a new top-level umbrella for this work. The Orchestrator should
create or link a child mission/project or issue tree under that umbrella:

`Data Intelligence Agent Local Tooling V1`

## Business Goal

Give the internal Data Intelligence Agent a safe, useful, real-data discovery
lane so Fusion CRM can understand local Salesforce, CareStack, identity,
ops, interaction, and revenue evidence coverage without letting agents connect
to the database directly or generate SQL.

The business value is faster semantic catalog evolution:

- identify source mapping gaps;
- quantify Salesforce to Fusion person to CareStack linkage quality;
- inspect consultation, treatment, payment, owner, location, and campaign
  evidence coverage;
- propose new semantic mappings;
- produce gap briefs that become Linear-ready backend, data quality, or
  catalog tasks.

## Why Now

The semantic analytics foundation now has:

- manager questions;
- catalog terms;
- query specs;
- policy preflight rules;
- query registry entries;
- service-owned analytics;
- manager read models;
- frontend-visible documentation and workbench;
- manager dashboard integration over real backend data.

The next bottleneck is data understanding. Without an approved local discovery
tool, future catalog and read-model work will either rely on guesses or tempt
agents into direct database inspection. This mission closes that gap with a
controlled tool boundary.

## Non-Goals

- Do not create a generic SQL terminal.
- Do not allow LLM-generated SQL.
- Do not let agents read `.env*` files or database credentials.
- Do not write or mutate production data.
- Do not run migrations as part of exploratory profiling unless a separate
  implementation issue explicitly requires schema work.
- Do not expose raw provider payloads as ordinary agent, dashboard, chat, or
  report output.
- Do not add production manager chat behavior in this mission.
- Do not implement XLSX exports, scheduled reports, or export workflows.
- Do not create a PHI-capable lane in V1.

## Core Architecture Rule

The Data Intelligence Agent must call approved tools only.

Allowed path:

```text
agent -> packages.tools data_intelligence_* tool
      -> service-owned profiling/query method
      -> repository/data layer
      -> database
```

Forbidden paths:

```text
agent -> database
agent -> SQL string
agent -> repository
agent -> raw provider payload dump
frontend -> database
frontend -> analytics business logic
```

## Data Classes For V1

| Data class | V1 posture |
| --- | --- |
| `ops` | Allowed through approved read-only tools. |
| `identity` | Allowed as `person_uid`, linkage status, and masked identifiers. |
| `integration_metadata` | Allowed for provider ids, source systems, sync/linkage references, and evidence references. |
| `billing` | Allowed for bounded profiling and aggregate evidence checks; row-level samples must be capped and masked. |
| `phi_adjacent` | Allowed only as reviewed metadata with explicit data-class markings. |
| `phi` | Denied in V1 unless a later PHI-capable lane is explicitly approved. |
| `raw_payload` | Denied as ordinary output. |

## Default Policy Decisions

Use these defaults unless the human changes them before Orchestrator acceptance:

- Environment: local/dev first.
- Role: authorized internal builder.
- Row-level access: allowed for internal users through approved tools, with
  masks and caps.
- Default row sample limit: 25.
- Hard row sample cap: 100.
- Default top-value cap: 50.
- Hard profile group cap: 250.
- Date window default: 365 days.
- Export: denied in this mission.
- Raw payload output: denied.
- PHI: denied.
- Audit/logging: required for every tool call.

## Expected Outcome

After this mission:

1. The Orchestrator has a Linear-backed mission with clear ownership,
   dependencies, acceptance criteria, and verification.
2. A Data Intelligence Agent local tooling contract is operationalized into
   service/tool interfaces, not just documentation.
3. Approved tools can list discoverable datasets/query registry entries.
4. Approved tools can produce field profiles, null rates, top values, linkage
   rates, evidence coverage, and bounded masked samples.
5. The tool can produce semantic mapping proposals and gap briefs in a stable,
   reviewable format.
6. Every tool call is logged/audited with dataset, fields, data classes,
   row limits, masks, and result posture.
7. The Semantic Analytics Workbench or another local-dev surface can display
   the Data Intelligence Agent docs, latest gap briefs, and profiling outputs.
8. Verification proves that direct DB access, raw SQL, raw payload output,
   uncapped samples, PHI output, and write actions are blocked.

## Suggested Linear Structure

The Orchestrator should create or link one child Linear mission/project or
issue tree under the existing `Semantic Context And Analytics Foundation`
umbrella:

`Data Intelligence Agent Local Tooling V1`

Suggested issues:

### DIA-01 Mission Setup And Linear Sync

Purpose: create the mission folder and runtime state for Orchestrator control.

Acceptance:

- Mission folder exists at
  `.agents/orchestration/data-intelligence-agent-local-tooling-v1/`.
- Runtime state exists under the configured Orchestrator runtime home.
- `goal.md`, `acceptance.md`, `contract.md`, `verification.md`,
  `ownership.yaml`, `decision-log.md`, `board.md`, `linear-sync.md`,
  `runlog.md`, and `incidents.md` are present or initialized.
- A `Handoff:` event records Strategy to Orchestrator transition.
- The existing umbrella URL plus the child mission/project and issue URLs are
  recorded in `linear-sync.md`.

### DIA-02 Tool Policy And Allowlist

Purpose: translate the ENG-279 contract into executable policy metadata.

Acceptance:

- Allowed datasets, data classes, fields, output levels, limits, masks, and
  denied fields are documented in mission artifacts.
- Policy explicitly denies raw SQL, direct DB access, writes, migrations,
  raw payload dumps, uncapped samples, and PHI output.
- Row-level local samples are allowed only for authorized internal builders
  through approved tools.
- Audit fields are defined before implementation begins.

### DIA-03 Data Intelligence Service Contract

Purpose: define the backend service boundary that owns data profiling logic.

Acceptance:

- Service methods are specified for dataset discovery, field profiles, linkage
  profiling, evidence coverage, bounded samples, semantic mapping proposals,
  and gap briefs.
- DTOs define request and response shapes with data classes and output posture.
- The contract keeps analytics logic in services, not routes, tools, or
  frontend code.
- No tool or route accepts a free-form SQL string.

### DIA-04 Query Registry And Dataset Discovery Tool

Purpose: expose safe discovery of approved analytics and profiling targets.

Acceptance:

- A tool can list approved analytics query registry entries and Data
  Intelligence datasets.
- Discovery output includes ids, titles, data classes, allowed output levels,
  max limits, masking posture, and status.
- Discovery output does not include credentials, SQL, raw table dumps, or raw
  provider payloads.

### DIA-05 Field Profile Tool

Purpose: profile values for allowlisted fields.

Acceptance:

- Tool returns row count, null rate, top values, distinct count posture, data
  class, source system, warnings, and sample policy.
- Requests are rejected when fields are not allowlisted.
- Top-value and field-count limits are enforced.
- Billing-sensitive fields are marked and capped.
- PHI and raw payload fields are denied.

### DIA-06 Linkage And Source Coverage Tool

Purpose: measure whether Salesforce, Fusion person, and CareStack evidence
links are strong enough for catalog/read-model work.

Acceptance:

- Tool returns linkage rates for selected cohorts and date windows.
- Supports Salesforce lead to `person_uid`, `person_uid` to CareStack patient,
  and source-reference coverage where current canonical data permits.
- Outputs aggregate rates plus bounded masked gap examples.
- Does not expose names, phone, email, DOB, clinical notes, or raw payload JSON.

### DIA-07 Evidence Coverage Tool

Purpose: profile consultation, treatment, payment, owner, location, campaign,
and source evidence availability.

Acceptance:

- Tool can summarize evidence presence for manager analytics terms including
  `consultation_scheduled`, `consultation_completed`, `payment_received`,
  `treatment_accepted`, `lead_source`, and owner/location fields.
- Outputs coverage percentages, known gaps, candidate source systems, and
  blocked/unknown states.
- Billing evidence is aggregate-first, with row-level samples only when
  allowed by policy.

### DIA-08 Bounded Masked Sample Tool

Purpose: provide small local examples that help builders understand data shape.

Acceptance:

- Samples are capped by default and hard cap.
- Masking is applied to identifiers and sensitive fields.
- Raw payloads, PHI, clinical notes, and unrestricted billing detail are
  denied.
- The response includes applied masks, data classes touched, row count, and
  audit id or log reference.

### DIA-09 Semantic Mapping Proposal Generator

Purpose: convert profiling observations into reviewable catalog proposals.

Acceptance:

- Outputs proposals for normalized source/campaign/channel/status mappings.
- Each proposal includes observed values, source systems, confidence, affected
  manager questions, data classes, and required human review flag.
- The tool does not mutate the catalog automatically.
- Generated proposals can be attached to Orchestrator reports or future Linear
  issues.

### DIA-10 Gap Brief Writer

Purpose: create stable briefs for data quality, catalog, read-model, or service
follow-up.

Acceptance:

- Gap briefs include severity, affected questions, evidence summary,
  recommended Linear issue title, blocked-by list, and suggested owner.
- Briefs are written to mission/report artifacts or returned in a stable DTO
  for Orchestrator ingestion.
- The tool distinguishes data-quality gaps from semantic-definition gaps and
  implementation gaps.

### DIA-11 Audit And Tool Call Logging

Purpose: make local exploratory access reviewable.

Acceptance:

- Every tool call records actor/session, tool name, dataset, fields, filters,
  data classes, requested and returned row limits, masks applied, status, and
  timestamp.
- Billing and PHI-adjacent requests are clearly marked.
- Denied requests are logged with denial reason.
- Logs do not contain PHI, raw payloads, secrets, or unmasked sensitive values.

### DIA-12 Local Workbench Visibility

Purpose: make the mission readable from the local frontend/dev workbench.

Acceptance:

- Data Intelligence Agent docs and output examples are readable from the local
  semantic analytics workbench or a local-only child page.
- The page is local/dev gated.
- It does not depend on MSW for real backend-backed data.
- It clearly separates docs, approved tools, latest gap briefs, and execution
  status.

### DIA-13 Verification And Production Review

Purpose: prove the mission is safe and ready for the next semantic/read-model
wave.

Acceptance:

- Tests cover accepted and denied tool calls.
- Tests cover no raw SQL input, no direct repository access from tools, no raw
  payload output, caps, masking, and audit records.
- Frontend tests or smoke checks cover local workbench visibility if UI is in
  scope.
- Production review confirms that agents still access platform data only
  through `packages.tools`.
- Orchestrator final report lists changed files, tests, risks, and next
  Linear issues generated from gap briefs.

## Ownership Proposal

Suggested ownership:

| Area | Owner role |
| --- | --- |
| Mission setup and Linear sync | Orchestrator |
| Policy/allowlist | Backend architecture + analytics catalog owner |
| Service contract and implementation | Backend worker |
| Tool layer and registry | Tools worker |
| Audit/logging | Backend worker with audit-domain review |
| Workbench visibility | Frontend worker |
| Verification | Reviewer / integrator |
| Gap brief triage | Orchestrator |

Workers must not overlap write ownership without Orchestrator approval.

## Dependency Order

1. DIA-01 Mission Setup And Linear Sync
2. DIA-02 Tool Policy And Allowlist
3. DIA-03 Data Intelligence Service Contract
4. DIA-04 Query Registry And Dataset Discovery Tool
5. DIA-05 Field Profile Tool
6. DIA-06 Linkage And Source Coverage Tool
7. DIA-07 Evidence Coverage Tool
8. DIA-08 Bounded Masked Sample Tool
9. DIA-09 Semantic Mapping Proposal Generator
10. DIA-10 Gap Brief Writer
11. DIA-11 Audit And Tool Call Logging
12. DIA-12 Local Workbench Visibility
13. DIA-13 Verification And Production Review

DIA-05, DIA-06, and DIA-07 may run in parallel after DIA-03 and DIA-04 if the
Orchestrator assigns disjoint file ownership. DIA-11 should be designed early
and integrated into every tool before mission completion.

## Acceptance Criteria For The Mission

The mission is complete only when:

- The existing `Semantic Context And Analytics Foundation` umbrella is linked,
  and the child mission/project plus all child issues exist in mission runtime
  files.
- Approved local tools can profile real local data without direct DB access by
  the agent.
- All outputs include data-class and masking posture.
- Row-level samples are capped, masked, and audit/logged.
- PHI and raw payload ordinary outputs are denied.
- Billing evidence is marked and bounded.
- Semantic mapping proposals and gap briefs can be generated.
- Local workbench docs/visibility exist if included by Orchestrator.
- Verification covers positive and denial paths.
- Production review finds no architecture invariant violations.

## Verification Plan

Minimum verification:

- `make lint`
- `mypy .` or repo-standard typecheck command if different in current branch
- `make test`
- `cd packages/db && alembic check`
- Focused tests for new service/tool modules
- Focused frontend tests if DIA-12 changes web code
- `git diff --check`

Security and invariant checks:

- grep or test for no tool accepting `sql`, `query_text`, or free-form DB
  query strings;
- verify tools call services, not repositories or `session.execute`;
- verify denied raw payload fields remain denied;
- verify PHI fields are denied in V1;
- verify row limits cannot be bypassed;
- verify audit/logging is called for success and denial cases;
- verify workbench route is local/dev gated if frontend is touched.

## Risks

- The tool can accidentally become a generic data browser. Mitigation:
  deny-by-default allowlist, data classes, caps, masks, and no raw SQL.
- Local profiling can leak sensitive details into logs or reports. Mitigation:
  output DTOs include redaction posture and logs exclude PHI/raw payloads.
- The service layer can duplicate semantic catalog definitions. Mitigation:
  reference catalog term ids/versions and keep proposals review-only.
- Row-level access can spread into production chat/dashboard. Mitigation:
  Data Intelligence Agent remains internal builder tooling; manager chat uses
  approved analytics query registry and policy preflight.
- Workbench docs can accidentally become product runtime dependencies.
  Mitigation: local/dev gating and no product dependency on `.agents/`.

## Human Decisions Needed

No blocking decision is required to create the Linear mission if the defaults
above are accepted.

Decisions the Orchestrator should record:

1. Confirm default row sample limit `25` and hard cap `100`.
2. Confirm default top-value cap `50` and hard cap `250`.
3. Confirm whether DIA-12 should be a new child route or an extension of
   `/dev/semantic-analytics`.
4. Confirm that PHI remains denied for V1.
5. Confirm that exports remain denied for this mission.

## Notes For Orchestrator

- Create or link Linear issues before assigning any Worker.
- Record `Handoff:` from Strategy Agent to Orchestrator.
- Do not launch Workers until the human explicitly approves execution after
  Linear issues exist.
- Use this mission as a continuation of the Semantic Context And Analytics
  Foundation, not a replacement for it.
- Keep the first implementation narrow: discovery, profiling, linkage,
  coverage, mapping proposals, gap briefs, and audit.
