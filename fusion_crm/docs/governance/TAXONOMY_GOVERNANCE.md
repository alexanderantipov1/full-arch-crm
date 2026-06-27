# Taxonomy Governance

Fusion CRM's taxonomy is the governed operational language used by workflows,
agents, reporting, and context builders.

## Principle

Taxonomy can evolve, but it must not mutate unpredictably.

Agents may classify data and propose changes. They may not directly change the
production taxonomy or strategy without approval.

## What Belongs in Taxonomy

Examples:

- treatment intent labels
- objection labels
- urgency labels
- lead source categories
- contactability categories
- workflow stage names
- consultation outcome labels
- escalation reasons
- approved SMS/call strategy labels

## Governance Rules

- Taxonomy versions are explicit.
- Every production taxonomy change has an author, reviewer, rationale, and date.
- Every change includes examples and counterexamples.
- Changes that alter workflow routing require approval.
- Changes that alter patient communication require approval.
- Changes that touch PHI interpretation require approval.
- Agents can create proposals, not production changes.

## Proposal Flow

```text
new pattern detected
-> taxonomy proposal
-> examples attached
-> human review
-> approve / reject / request changes
-> new taxonomy version
-> release notes for workflows/agents
```

## Approval Boundaries

Human approval is required for:

- new taxonomy categories
- category merges/splits
- workflow strategy changes
- SMS/call strategy changes
- PHI-sensitive semantic labels
- any change that changes external patient communication
- any change that changes task priority or escalation

Human approval is not required for:

- storing an agent's proposed label as `needs_review`
- deterministic mapping bug reports
- local-only exploratory analysis
- adding examples to a draft proposal

## Audit Metadata

Approved taxonomy changes must record:

- taxonomy area
- previous version
- new version
- changed labels
- author
- approver
- rationale
- sample evidence
- rollout date
- rollback guidance

## Production Safety

Production workflows should reference a specific taxonomy version or a controlled
active version pointer. Updating the pointer is a governed release action.

If a taxonomy change creates unexpected routing or communication behavior, roll
back the active version pointer and replay affected events through the previous
version when needed.
