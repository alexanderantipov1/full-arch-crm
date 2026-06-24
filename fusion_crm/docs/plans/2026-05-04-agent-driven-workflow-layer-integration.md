# Agent-Driven Workflow Layer Integration Plan

> **Status:** strategic integration note, 2026-05-04  
> **Source:** `agent_driven_workflow_layer_whitepaper.md`  
> **Scope:** align the agent-driven workflow whitepaper with the Fusion CRM
> roadmap, schema plan, HIPAA posture, and phased delivery model.

This document records how the flexible agent-driven workflow layer fits into
the platform vision. It is doctrine for later phases, not a request to expand
the current Phase 1 vertical slice.

---

## 1. Positioning

The whitepaper strengthens the existing operating model:

```text
Raw Event -> Context -> Decision -> Flow / Action -> Result -> New Event
```

It makes the "Decision" and "Action" portions more explicit:

```text
interaction.event
  -> context.context_fact
  -> workflow.flow_instance / workflow.action_step
  -> workflow.agent_decision
  -> policy preflight
  -> service-backed tool execution
  -> audit.agent_tool_call / workflow.action_result
  -> new interaction.event
```

The core architectural boundary remains unchanged:

- agents never read or write the database directly;
- tools call services only;
- services enforce permissions, policy, PHI boundaries, and audit;
- every action creates durable state that can be replayed or reviewed.

---

## 2. Non-Goals

These ideas must not be pulled into Phase 1 prematurely:

- no production workflow runner in the Phase 1 vertical slice;
- no `workflow.agent_decision`, approval queue, or timer runner in Phase 1;
- no staff-created agent builder before role/capability enforcement exists;
- no direct DB access from agents;
- no raw PHI or raw transcripts exposed to marketing or operations agents;
- no production raw-payload inspector outside local/development gates;
- no autonomous restricted writes before human approval and audit are live.

Phase 1 should continue to prove ingestion, identity linking, normalized
events, read-only MCP tools, and the operator UI surface.

---

## 3. Canonical Term Mapping

| Whitepaper term | Fusion CRM term |
|---|---|
| Raw event | `ingest.raw_event` |
| Normalized event | `interaction.event` |
| Workflow instances | `workflow.flow_instance` |
| Workflow events | `interaction.event`; optional `workflow.event_log` only if later needed |
| Workflow steps | `workflow.flow_node` + `workflow.action_step` |
| Workflow timers | future `workflow.timer` |
| Agent decisions | future `workflow.agent_decision` |
| Tool calls | `audit.agent_tool_call` |
| Tool outcomes | `workflow.action_result` |
| Human approvals | future `workflow.approval_request` |
| Policies / guardrails | service-level checks, `auth.permission_grant`, data-class sentinels, and Phase 8 runtime gates |
| Role-based agents | `actor.actor`, `actor.actor_capability`, `auth.permission_grant` |

The whitepaper's operational tables should be adapted to the repo's existing
domain separation instead of added as a second parallel schema.

---

## 4. Phase Integration

### Phase 1

No scope expansion. The agent-driven workflow layer is included only as
doctrine. Phase 1 remains focused on real Salesforce + CareStack data moving
through the canonical model and becoming visible in the operator UI.

Phase 1 may create foundational read surfaces that future agents will use:
normalized timeline reads, person resolution, integration status, sync run
visibility, and audit summaries.

### Phase 3

Interaction ingestion should normalize external activity into a durable event
taxonomy that future workflows can subscribe to. Event names may use the
whitepaper's dotted vocabulary at the API/domain boundary, while table columns
can keep the current `snake_case` convention if that remains easier for
queries and Python literals.

The main requirement is semantic consistency: calls, SMS, appointment changes,
manual tasks, and provider sync changes must be append-only inputs to later
workflow evaluation.

### Phase 4

Context extraction becomes the input layer for agent decisions. Each
`context.context_fact` should carry enough structured metadata for a future
decision engine to reason without reading raw payloads:

- context type and key;
- confidence;
- urgency and SLA hints;
- source event references;
- data class / PHI flag;
- short sanitized summary where possible.

Phase 4 should not execute tools. It produces context, review hooks, and
classified inputs.

### Phase 5

Phase 5 is the natural home for the first durable workflow and agent-decision
foundation:

1. subscribe workflow rules to `interaction.event` and `context.context_fact`;
2. seed `workflow.flow_definition` records for lead follow-up, no-show
   recovery, consultation booking, price recovery, and reactivation;
3. create `workflow.flow_instance`, `workflow.flow_node`, and
   `workflow.action_step` records through a runner service;
4. introduce `workflow.timer` for waits, callbacks, SLA checks, retries, and
   delayed follow-ups;
5. introduce `workflow.agent_decision` for structured model/rule decisions;
6. define tool metadata: risk category, required capability, data class,
   human-approval requirement, and allowed actor roles;
7. run policy preflight before every tool call;
8. introduce `workflow.approval_request` for human review before restricted
   actions;
9. write `audit.agent_tool_call` and `workflow.action_result` for every
   attempted execution;
10. emit a new `interaction.event` when an action materially changes the
    business state.

The expected loop is:

```text
Event -> State -> Agent Decision -> Policy -> Tool -> Audit -> Event
```

### Phase 6

Encounter workflows consume the same layer. Consultation completion,
no-shows, treatment-plan presentation, surgery scheduling, and reactivation
should create workflow events and downstream action steps, but clinical PHI
must remain behind `PhiService`.

### Phase 8

The whitepaper's policy layer becomes concrete in Phase 8:

- do-not-call and do-not-SMS rules;
- office-hours and quiet-hours rules;
- role + capability checks;
- data-class and PHI checks;
- vendor BAA eligibility;
- low-confidence human approval;
- restricted-write approval enforcement;
- deny-by-default behavior for unknown tools or unknown data classes.

This layer should sit before tool execution, not inside agent prompts.

### Phase 9

The operator UI should expose the workflow layer in ways humans can inspect
and control:

- approval queue;
- agent decision trace;
- tool-call drilldown;
- action result history;
- flow tree with timers and blocked steps;
- context review panel linked to decisions;
- automation coverage by actor, role, and workflow.

Agent management UI can expose capabilities and deployment status here, but
staff-created agents should remain constrained until Phase 10.

### Phase 10

The staff agent builder and workflow template builder belong here after evals,
permissions, release records, and audit review are mature.

Staff-created agents should be stored as governed templates, not as arbitrary
prompt blobs. Each template needs:

- goal;
- allowed context sources;
- allowed tools;
- role/capability requirements;
- prohibited actions;
- approval thresholds;
- output schema;
- eval set;
- release status and rollback record.

---

## 5. Schema Recommendations

The v0.2 schema plan should reserve three future workflow tables:

- `workflow.agent_decision` for structured decisions and evidence;
- `workflow.approval_request` for human review and edited approvals;
- `workflow.timer` for delayed workflow execution.

Do not add a duplicate operational `tool_calls` table unless we later need
mutable execution orchestration state. The durable audit log remains
`audit.agent_tool_call`; the workflow outcome remains `workflow.action_result`.

Decision outputs and audit summaries must be sanitized. PHI-bearing reasoning
belongs behind the PHI gate or in explicitly classified context records, not
in generic workflow or audit summaries.

---

## 6. Future Open Decisions

- Where the policy DSL lives: `auth.permission_grant`, workflow metadata,
  package-level Python policy objects, or a dedicated policy table.
- How the timer runner is implemented: database polling, Redis delayed jobs,
  arq scheduled jobs, or a hybrid.
- Whether event names are stored as dotted names (`sms.received`) or
  snake_case names (`sms_received`) with API-level mapping.
- Exact `workflow.approval_request` payload schema and redaction rules.
- Staff agent-builder governance: who can create, approve, publish, and retire
  agent templates.
- Whether long-term workflow event projection needs a dedicated
  `workflow.event_log`, or whether `interaction.event` plus audit logs are
  sufficient.

---

## 7. References

- `agent_driven_workflow_layer_whitepaper.md`
- `docs/ROADMAP.md`
- `docs/plans/2026-04-30-full-schema-v0_2.md`
- `ai_context_workflow_whitepaper.md`
- `AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx`
