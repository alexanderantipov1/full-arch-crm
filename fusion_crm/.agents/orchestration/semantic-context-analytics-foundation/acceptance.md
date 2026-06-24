# Acceptance — Semantic Context And Analytics Foundation

## Planning Acceptance

- The Strategy handoff is evaluated and accepted for Linear-backed mission
  planning.
- Readiness is preserved as `needs decision` while human decisions remain.
- The Linear project umbrella exists.
- Linear backlog issues exist for the full mission arc A-K.
- Dependencies are represented in Linear through blocker relationships.
- The first recommended execution slice is identified and represented as a
  Linear milestone.
- Mission runtime state records the Strategy -> Orchestrator handoff.
- `board.md`, `linear-sync.md`, and `runlog.md` exist in runtime state.
- Durable mission artifacts exist in the repo spec directory.

## Mission Arc Acceptance

### A. Manager Analytics Questions V1

- 20 to 30 real manager questions are documented.
- Questions are grouped by workflow and priority.
- Each question records output shape, filters, row-level versus aggregate
  expectations, data-class concerns, and review owner.

### B. Semantic Analytics Catalog V1

- First terms, synonyms, definitions, data sources, data classes, permissions,
  row-level/aggregate rules, allowed fields, versions, owners, and review
  statuses exist.
- Unknown terms are explicitly marked instead of guessed.

### B2. Semantic Catalog Proposal Review V1

- Data Intelligence Agent discoveries can be represented as proposed mappings,
  source-drift briefs, or gap briefs without automatically changing approved
  business meaning.
- Proposed mappings support approve, edit, reject, add-synonym, and unresolved
  states.
- Approved changes produce a new catalog version with actor, timestamp,
  previous value, new value, reason, affected analytics, and review status.
- Impact preview identifies affected questions, reports, read models, dashboard
  panels, chat answers, and agent briefs before approval.
- Services, dashboards, chat, and agents consume approved catalog versions, not
  unreviewed proposals.

### C. Structured Analytics Query Spec

- JSON schema, allowed intents, filters, dimensions, metrics, output types,
  validation, examples, and clarification behavior exist.
- Query specs cannot carry raw SQL.

### D. Analytics Policy Preflight

- Role, data-class, PHI, billing, row-level, export, and audit checks run before
  analytics execution.
- Unsafe or ambiguous requests produce deny or clarify decisions.

### E. Analytics Query Registry V1

- Approved typed analytics queries are registered with params schema, result
  schema, roles, environments, limits, audit rules, and AI-chat safety flags.

### F. Analytics Services V1

- First service-owned queries exist for lead source profile, conversion funnel,
  paid leads, consultation follow-up, and revenue evidence.

### G. Manager Analytics Read Models V1

- `lead_conversion`, `paid_leads`, `consultation_followup`, and
  `treatment_revenue` are supported as service-computed or persisted read
  models.

### H. Data Intelligence Agent V1

- Internal role, skill contract, local read-only data tool boundary, masking,
  row limits, source profiling, and semantic mapping/gap brief output are
  defined.

### I. Manager AI Chat V1

- Chat planner flow maps manager questions to approved query specs, runs policy
  preflight, executes approved services, explains results, and writes audit.

### J. Exports And Saved Reports

- V1 implements aggregate CSV export, portable saved-report definitions, and
  export audit after result contracts and policy are stable.
- XLSX, scheduled reports, and row-level exports remain deferred until a later
  decision explicitly approves those surfaces.

### K. Semantic Analytics Workbench V1

- Internal frontend users can read the mission documentation directly from the
  app.
- The workbench renders manager questions, semantic catalog terms, Data
  Intelligence Agent contract, and backend implementation handoff.
- The UI shows question-to-term mapping, data-class badges, allowed output
  posture, source references, version/review status, and implementation
  readiness.
- The workbench is read-only unless a later issue explicitly adds editing or
  review workflows.

## Non-Acceptance

- Worker launch before explicit approval is not accepted.
- Direct agent database access is not accepted.
- Raw SQL from LLM planners, dashboards, chat, or agents is not accepted.
- Raw provider payloads as ordinary dashboard, chat, or agent output are not
  accepted.
- PHI access outside `PhiService` and audit is not accepted.
- Frontend-only metric definitions are not accepted.
