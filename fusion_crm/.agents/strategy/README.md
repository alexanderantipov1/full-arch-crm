# Agent Strategy Runtime

Optional strategy artifacts live here.

Expected shape:

```text
.agents/strategy/
  inbox/
  discussions/
  candidate-missions/
  CANDIDATE_MISSIONS.md
  HANDOFF_TO_ORCHESTRATOR.md
  SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md
  UNIFIED_PERSON_LIFECYCLE_SEMANTIC_ANALYTICS_PLAN.md
  PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md
  RAW_TO_CONTEXT_NORMALIZATION_SPEC.md
  architecture-radar.md
  roadmap.md
  business-assumptions.md
  strategic-decisions.md
```

This layer tracks strategic questions, candidate missions, architecture radar,
business assumptions, and items that are ready for orchestrator handoff.

`PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md` records how raw Salesforce,
CareStack, and future provider observations become canonical person-linked
evidence, normalized events, semantic context, and agent-safe context packs.

`RAW_TO_CONTEXT_NORMALIZATION_SPEC.md` records the technical layer model for
raw capture, minimal indexing, human review tables, canonical projections,
semantic interpretation, and agent context-pack promotion.

`SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md` records the business and
strategy plan for the shared semantic analytics foundation used by manager
dashboards, manager AI chat, internal Data Intelligence agents, reports, and
future workflow-ready context.

`DATA_INTELLIGENCE_AGENT_LOCAL_TOOLING_MISSION_SPEC.md` records the Strategy
handoff spec for operationalizing the Data Intelligence Agent as a local
read-only discovery and profiling tool under Orchestrator and Linear control.

`UNIFIED_PERSON_LIFECYCLE_SEMANTIC_ANALYTICS_PLAN.md` records how the
manager-provided unified patient / lead profile requirements map onto Fusion
CRM's existing person, provenance, semantic analytics, context, and agent
architecture without copying the proposed database shape literally.

The dashboard reads this directory as source material only. It does not promote
strategy items into execution missions.

`PROTOCOL.md` is the authoritative local role contract for the Strategy /
Architecture Agent. The repo-local Codex skill lives at
`.agents/skills/strategy-agent/SKILL.md`; the Claude Code command lives at
`.claude/commands/strategy.md`.

## Protocol

Strategy and Architecture agents may create candidate missions and structured
handoff requests for the Orchestrator. They must not launch workers, assign
execution tasks directly, or modify product code.

Handoff rule:

```text
Strategy proposes, Orchestrator disposes.
```

Each handoff must include:

- business goal;
- why now;
- expected outcome;
- assumptions;
- architecture constraints;
- suggested decomposition;
- risks;
- human decisions needed;
- readiness status: `draft`, `needs decision`, or `ready for orchestrator`.
