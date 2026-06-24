# Governed Agent Learning Strategy

> Status: strategic development doctrine  
> Scope: R&D direction for agents, workflows, taxonomy, memory, and learning  
> Non-scope: no production schema or behavior change by itself

## Purpose

Fusion CRM should evolve into a governed operational intelligence platform, not
an uncontrolled autonomous-agent system.

The platform should learn from:

- provider events,
- normalized interaction history,
- semantic interpretations,
- workflow outcomes,
- human corrections,
- approved taxonomy changes,
- and reviewed operational skills.

The platform must not learn by silently mutating production rules, prompts,
schemas, taxonomy, or patient communication behavior.

This document exists so future agent, workflow, taxonomy, and memory work keeps
moving toward the same long-term architecture.

## North Star

```text
Raw event
-> canonical entity/event
-> semantic interpretation
-> governed context pack
-> workflow decision
-> policy preflight
-> service-backed tool call
-> audit + action result
-> outcome event
-> pattern analysis
-> learning proposal
-> human review
-> versioned taxonomy / skill / workflow rule
```

The goal is continuous improvement with durable control:

- better lead classification,
- better follow-up prioritization,
- better routing and escalation,
- better communication timing,
- better no-show and reactivation workflows,
- better operational recommendations,
- and better semantic understanding.

The guardrail is that approved production behavior changes only through
versioned, reviewable, auditable releases.

## Non-Goals

The system must not become:

- an agent with direct database access,
- a prompt-only memory system,
- an unreviewed workflow mutation system,
- a raw provider-payload reasoning system,
- a hidden patient communication engine,
- a PHI leakage path,
- or a self-modifying production application.

Agents may propose. Services, policies, review flows, and versioned releases
decide what becomes production behavior.

## Core Principles

### Deterministic Boundaries First

Clear, repeatable facts should be handled by deterministic code and governed
tables before model interpretation:

- provider identifiers,
- UTM/source mapping,
- appointment status,
- opt-out and consent flags,
- known campaign mappings,
- tenant and location scope,
- and do-not-contact constraints.

Agents should focus on ambiguity, synthesis, language, pattern detection, and
proposal generation.

### Context Over Raw Data

Agents should consume least-privilege context packs, not raw database tables or
raw provider payloads.

A context pack should state:

- what the agent may know,
- what data classes are included,
- which source events support the context,
- which taxonomy version was used,
- which tools are available,
- what action is being requested,
- what approval boundary applies,
- and what must not be inferred or exposed.

### Learning Produces Proposals

The first-class output of learning is a proposal, not an automatic production
change.

Examples:

- taxonomy proposal,
- workflow timing proposal,
- routing/escalation proposal,
- communication strategy proposal,
- semantic mapping proposal,
- operational skill proposal,
- eval or replay-case proposal.

Every proposal should include evidence, examples, counterexamples, confidence,
expected impact, risk, and rollback guidance.

### Skills Are Governed Operational Knowledge

Operational skills are reusable procedures and reasoning patterns.

Examples:

- `lead_reactivation`,
- `financing_objection`,
- `no_show_recovery`,
- `consultation_confirmation`,
- `identity_resolution_review`,
- `carestack_appointment_followup`.

A production skill must have:

- a goal,
- allowed context sources,
- prohibited context sources,
- allowed tools,
- required actor capability,
- output schema,
- human approval requirements,
- eval cases,
- owner,
- release status,
- version,
- rollback guidance.

Agent-created draft skills may exist, but production workflows must only use
approved skill versions.

### Memory Must Be Layered

Fusion CRM needs multiple memory surfaces with different governance rules.

Repository memory:

- architecture doctrine,
- ADRs,
- taxonomy policy,
- workflow philosophy,
- agent safety rules.

Structured operational memory:

- person-level non-PHI operational summaries,
- workflow summaries,
- contactability profiles,
- source/channel performance,
- follow-up responsiveness,
- outcome aggregates.

Semantic/vector memory:

- sanitized conversation summaries,
- objection patterns,
- preference summaries,
- communication summaries,
- de-identified learning examples.

Decision memory:

- context pack used,
- decision output,
- tool call,
- policy result,
- outcome,
- human correction,
- model/prompt/tool versions.

Prompt context is not memory. It is only a temporary delivery mechanism for
approved context.

### Policy Is Outside The Prompt

Safety and authorization should be enforced by services and policy preflight,
not by asking the model to behave.

Policy must cover:

- tenant scope,
- actor capability,
- PHI access,
- data class,
- consent and suppression,
- quiet hours,
- tool risk,
- confidence thresholds,
- review requirements,
- and deny-by-default behavior for unknown tools or unknown data classes.

### Outcomes Drive Improvement

Learning must connect decisions to real outcomes.

Examples:

- lead booked consultation,
- no-show recovered,
- financing objection resolved,
- task escalated in time,
- SMS got a response,
- patient opted out,
- appointment cancelled,
- coordinator overrode agent recommendation.

Without outcome linkage, the system is only generating plausible narratives.

## Strategic Components

### Semantic Interpretation

Semantic interpretation converts raw/canonical data into stable operational
meaning.

Future implementation should preserve:

- source event references,
- interpreter type (`rule`, `agent`, `human`),
- interpreter version,
- taxonomy version,
- confidence,
- review status,
- data class,
- and created timestamp.

Low-risk deterministic interpretations may be auto-accepted. New labels,
PHI-sensitive summaries, routing-changing outputs, and communication-changing
outputs require review before they become production rules.

### Context Packs

Context packs are the primary input to agent decisions.

Future context pack types:

- lead decision context,
- person operational context,
- conversation context,
- consultation context,
- workflow context,
- agent-specific context.

Context pack builders must be idempotent and replayable. Replaying the same
source events under the same taxonomy/rule versions should produce the same
context or an explicitly versioned successor.

### Agent Decision Ledger

Every material agent decision should become durable state.

The ledger should record:

- actor id,
- agent/template/skill version,
- model and prompt version,
- context pack id or hash,
- input data classes,
- output schema,
- recommendation or action,
- confidence,
- evidence references,
- policy preflight result,
- tool call references,
- approval references,
- outcome references,
- and human correction.

The decision ledger is the foundation for audit, replay, evals, regression
tests, and learning proposals.

### Learning Proposal Queue

Pattern analysis should produce learning proposals.

Proposal categories:

- taxonomy change,
- semantic mapping change,
- workflow rule change,
- skill change,
- communication strategy change,
- evaluation set addition,
- policy change,
- data-quality issue,
- integration mapping issue.

Review states:

- `draft`,
- `needs_review`,
- `approved`,
- `rejected`,
- `superseded`,
- `released`,
- `rolled_back`.

Production behavior changes only after a proposal is approved and released.

### Operational Skill Registry

The skill registry should be a governed library of reusable operational
procedures.

Early skills may live as documents. Production skills should eventually become
stored templates with explicit metadata, evals, and release state.

Skill lifecycle:

```text
observed pattern
-> draft skill
-> examples and counterexamples
-> eval cases
-> human review
-> approved version
-> limited rollout
-> outcome monitoring
-> revision proposal
```

### Eval And Replay Lab

Before agents can influence high-impact workflows, the platform needs replay
and evaluation infrastructure.

Minimum eval inputs:

- de-identified historical events,
- context packs,
- expected safe outputs,
- known bad outputs,
- policy-denied examples,
- human correction examples,
- outcome labels.

Eval outputs:

- schema validity,
- policy compliance,
- taxonomy consistency,
- recommendation accuracy,
- regression detection,
- PHI/data-class boundary violations,
- and outcome correlation.

## Phased Adoption

### Phase 0: Doctrine And Guardrails

Current strategic work.

Deliverables:

- maintain this document,
- maintain semantic interpretation doctrine,
- maintain context architecture doctrine,
- maintain taxonomy governance doctrine,
- keep AI tools service-backed only,
- keep PHI gated behind `PhiService`.

Exit criteria:

- every future agent/workflow proposal can be mapped to this architecture,
- non-goals are clear,
- new docs use consistent terms.

### Phase 1: Read-Only Context And Tool Metadata

Build foundations without autonomous production actions.

Deliverables:

- least-privilege context-pack design,
- richer tool metadata design,
- read-only agent tools for normalized timeline/context,
- audit records for all tool calls,
- clear data-class labels in tool and context outputs.

Exit criteria:

- an agent can explain a lead/person/workflow state using governed context,
- no raw provider payload or direct DB access is exposed,
- policy requirements are visible before tool expansion.

### Phase 2: Semantic Interpretation With Review

Introduce structured semantic outputs for ambiguous data.

Deliverables:

- structured semantic interpretation outputs,
- taxonomy version attached to interpretations,
- review states for action-changing interpretations,
- deterministic mappings for clear provider fields,
- draft proposal generation for unknown patterns.

Exit criteria:

- ambiguous transcripts/messages/forms produce structured, reviewable outputs,
- new labels become proposals rather than production taxonomy changes,
- semantic outputs can be replayed against source events.

### Phase 3: Decision Ledger And Outcome Linkage

Make decisions measurable.

Deliverables:

- durable agent decision records,
- context pack references or hashes,
- tool call and policy result references,
- outcome event linkage,
- human correction capture,
- initial replay dataset.

Exit criteria:

- the platform can answer why an agent recommended an action,
- the recommendation can be replayed,
- outcome analysis can distinguish successful and failed patterns.

### Phase 4: Draft Operational Skills

Convert repeated successful patterns into governed draft skills.

Deliverables:

- draft skill format,
- required metadata,
- examples and counterexamples,
- eval cases,
- human review flow,
- skill versioning policy.

Exit criteria:

- agents can propose skills,
- humans can approve/reject skills,
- workflows do not use unapproved draft skills.

### Phase 5: Workflow Runner Integration

Connect approved skills and decisions to workflow execution.

Deliverables:

- workflow decision records,
- timers/retries/SLA triggers,
- approval requests for restricted actions,
- policy preflight before every tool call,
- action results linked back to interaction events,
- operator review UI for decisions and approvals.

Exit criteria:

- low-risk workflows can run with governed automation,
- restricted writes require approval,
- every action is explainable, auditable, and replayable.

### Phase 6: Learning Proposal System

Make continuous improvement explicit.

Deliverables:

- proposal queue,
- proposal evidence model,
- review and release states,
- taxonomy/rule/skill release notes,
- rollback metadata,
- impact monitoring.

Exit criteria:

- pattern analysis produces proposals,
- proposals can become reviewed releases,
- releases can be rolled back and affected events can be replayed.

### Phase 7: Adaptive Operational Intelligence

Use approved learning to improve operations continuously.

Deliverables:

- outcome-driven prioritization,
- segment-aware communication recommendations,
- agent performance dashboards,
- automated eval regression checks,
- scoped A/B or holdout experiments where appropriate,
- policy-reviewed model/prompt/skill upgrades.

Exit criteria:

- learning improves measurable workflow outcomes,
- humans can inspect and control every release,
- governance remains stronger as automation increases.

## Implementation Readiness Gates

Do not allow an agent to influence production behavior unless all relevant
questions have concrete answers:

- What context did the agent receive?
- Which data classes were included?
- Which taxonomy version was used?
- Which model, prompt, and skill version was used?
- Which tools were available?
- Which policy checks ran?
- Was human approval required?
- Where was the decision recorded?
- What outcome will validate or invalidate the decision?
- How is the behavior rolled back?

If these answers are missing, the work belongs in R&D or draft mode, not
production automation.

## Maintenance Protocol

Update this document when:

- a new agent category is proposed,
- a new workflow category is proposed,
- a new taxonomy area is introduced,
- a new memory surface is introduced,
- a tool gains write behavior,
- a tool starts touching a new data class,
- a model/prompt/skill can affect patient communication,
- a learning proposal becomes a production release,
- or a real workflow exposes a new governance gap.

Every substantial agent/workflow design doc should include a short section:

```text
Governed learning alignment:
- Context source:
- Data class:
- Tool surface:
- Decision record:
- Outcome signal:
- Review boundary:
- Learning proposal path:
- Rollback path:
```

## Near-Term Development Recommendations

The next strategic steps should be documentation and low-risk scaffolding:

1. Define the canonical `DecisionContext` shape before adding more agent tools.
2. Expand tool metadata design before adding write-capable tools.
3. Define learning proposal fields before creating a proposal table.
4. Define operational skill metadata before creating agent-generated skills.
5. Start collecting de-identified replay cases before optimizing prompts.
6. Treat taxonomy changes as releases, not edits.
7. Keep Phase 1 focused on ingestion, identity, normalized events, and safe UI
   visibility while preparing the future learning architecture.

## Final Rule

Fusion CRM may become more adaptive over time, but adaptation must always be:

- explicit,
- reviewed,
- versioned,
- auditable,
- reversible,
- service-backed,
- and bounded by PHI, tenant, consent, and policy rules.

