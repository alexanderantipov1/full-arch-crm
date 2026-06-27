# Context Architecture

Fusion CRM does not expose raw provider data directly to agents. Agents operate
on governed context objects built from raw events, canonical records, semantic
interpretations, and workflow state.

## Context Layers

```text
raw provider data
-> canonical records
-> semantic interpretations
-> context objects
-> workflow decisions
-> agent-specific context packs
-> controlled actions
```

## Context Types

### Lead Context

Used for speed-to-lead calling and SMS.

Typical fields:

- source channel
- UTM source/medium/campaign/content/term
- landing page or form source
- treatment intent
- financing signal
- market/location
- urgency
- contactability
- recommended next action

### Person Context

The longitudinal operational view of a person.

Typical fields:

- current identifiers
- lead history
- communication history
- appointment/consultation history
- important non-PHI operational facts
- open tasks
- workflow stage

### Conversation Context

Produced from calls, SMS, email, chat, and form free text.

Typical fields:

- summary
- intent
- objections
- sentiment
- unanswered questions
- promised follow-up
- consent / opt-out signals
- escalation signals

### Consultation Context

Produced from CareStack appointment data, consultation outcomes, and safe
summaries.

Typical fields:

- scheduled / confirmed / completed / no-show / cancelled
- location and appointment time
- treatment interest
- financing concern
- next-step readiness
- follow-up due time
- safe operational summary

Clinical content remains in `phi` and is accessed only through `PhiService`.

### Workflow Context

The context consumed by workflow execution.

Typical fields:

- current stage
- SLA timer
- allowed actions
- blocked actions
- escalation reason
- required human approval
- last event that changed the workflow

### Agent Context

The least-privilege context pack for a specific agent task.

It defines:

- what the agent can know
- what the agent must not see
- which tools are available
- what action is requested
- what approval boundary applies

## Update Model

Context is updated continuously. Every relevant provider event, call, SMS,
email, appointment change, consultation result, or manual note can create:

1. a raw event,
2. a canonical projection,
3. a semantic interpretation,
4. a refreshed context object,
5. a workflow transition or task.

Context builders must be idempotent. Replaying an event should produce the same
context state or an explicitly versioned successor.

## Storage Direction

Early phases can build context on demand from canonical records and events.
When a context object becomes operationally important, persist it with:

- `person_uid`
- context type
- context version
- source event ids
- semantic interpretation ids
- generated_at
- confidence
- review status when applicable

## Agent Boundary

Agents do not read `ingest.raw_event` directly in production. They receive
context packs assembled by services that enforce permissions, PHI boundaries,
redaction, and audit.
