
# PROJECT_REPOSITORY_STRATEGY.md

# Strategic Repository Architecture & Agent Governance

## Purpose

This document defines the strategic repository structure and architectural philosophy for the Unified Dental Operations Platform.

This repository is intended for:
- developers,
- AI agents,
- orchestration systems,
- workflow engines,
- automation pipelines,
- and future engineering teams.

The repository must function as:
- technical memory,
- operational memory,
- governance layer,
- architectural map,
- and strategic constraint system.

---

# Core Philosophy

The platform is NOT:
- another CRM clone,
- a direct Salesforce mirror,
- a collection of disconnected automations,
- an unrestricted AI system,
- a PHI dumping ground,
- or a workflow system driven by raw CRM fields.

The platform IS:
- a semantic operational intelligence system,
- an event-driven workflow platform,
- a unified operational memory,
- a controlled AI orchestration environment,
- and a canonical business intelligence layer.

---

# Strategic Principle

```text
Raw Data
→ Events
→ Semantic Interpretation
→ Workflow Intelligence
→ Agent Decisions
→ Controlled Actions
```

The system separates:
- raw truth,
- operational truth,
- semantic understanding,
- workflow state,
- and agent decisions.

For provider data ingestion, the operational version of this principle lives in
`docs/PROVIDER_INGESTION_STRATEGY.md`. Salesforce and CareStack data must enter
as raw events first, then be hydrated, projected into canonical records, and
converted into semantic context before agents or workflows act on it.

Context and taxonomy are governed layers, not ad hoc prompt content:

- `docs/architecture/CONTEXT_ARCHITECTURE.md`
- `docs/architecture/SEMANTIC_INTERPRETATION.md`
- `docs/governance/TAXONOMY_GOVERNANCE.md`

Agents may classify, summarize, and propose improvements, but taxonomy,
strategy, and workflow-changing interpretations require human approval before
they become production behavior.

---

# Repository Philosophy

The repository should contain:

## 1. Strategic Knowledge
Long-term architectural principles that rarely change.

## 2. Technical Architecture
Implementation-specific structures that may evolve over time.

## 3. Agent Operating Rules
Behavioral and operational constraints for AI agents.

## 4. Governance & Safety
Policies for:
- PHI,
- workflows,
- auditability,
- permissions,
- semantic interpretation,
- and tool access.

---

# Recommended Repository Structure

```text
/docs
    /strategy
    /architecture
    /governance
    /agents

/agents
    PROJECT_CONTEXT.md
    AGENT_OPERATING_PRINCIPLES.md
    TAXONOMY_GUIDELINES.md
    WORKFLOW_RULES.md
    SAFE_ACTIONS.md
    SYSTEM_CONSTRAINTS.md

/docs/strategy
    VISION.md
    SYSTEM_PRINCIPLES.md
    SEMANTIC_ARCHITECTURE.md
    AGENT_MODEL.md
    WORKFLOW_PHILOSOPHY.md
    DATA_PHILOSOPHY.md

/docs/architecture
    EVENT_MODEL.md
    IDENTITY_MODEL.md
    TOOL_LAYER.md
    VECTOR_MEMORY.md
    FASTAPI_STRUCTURE.md
    POSTGRES_SCHEMAS.md

/docs/governance
    PHI_BOUNDARY.md
    FIELD_AUTHORITY_MATRIX.md
    AUDIT_MODEL.md
    RBAC_MODEL.md
```

---

# Strategic Documents

These documents represent the stable conceptual foundation of the platform.

They should explain:
- WHY the system exists,
- WHAT principles must not be violated,
- HOW intelligence flows through the system,
- and HOW agents are expected to behave.

These documents should remain implementation-flexible.

---

# Technical Architecture Documents

These documents describe:
- schemas,
- APIs,
- event pipelines,
- sync systems,
- vector memory systems,
- identity resolution,
- tool layers,
- and infrastructure.

Unlike strategic documents, these may evolve significantly over time.

---

# Agent Repository Philosophy

AI agents must not operate blindly.

Agents entering the repository should understand:
- system philosophy,
- data model,
- semantic architecture,
- governance constraints,
- workflow structure,
- and operational boundaries.

The repository itself becomes an operational memory system.

---

# Agent Operating Principles

## Agents MUST NOT:
- directly access raw SQL,
- bypass workflow engines,
- modify production taxonomy automatically,
- expose PHI outside approved scope,
- directly manipulate workflow state without audit,
- operate without tool restrictions,
- create uncontrolled side effects.

## Agents MUST:
- operate through tools,
- preserve auditability,
- explain reasoning,
- use semantic interpretation,
- respect workflow state,
- respect PHI boundaries,
- preserve event lineage,
- use canonical operational context.

---

# Semantic Architecture Principle

The platform must never rely directly on raw CRM schemas.

Instead:

```text
CRM fields
→ semantic interpretation
→ operational meaning
→ workflow intelligence
```

Example:

```text
Double_Arch__c = true
Flexible_Payments__c = true
```

Becomes:

```text
intent = full_arch
financial_profile = financing_needed
lead_temperature = hot
```

This semantic layer becomes the operational language of the platform.

---

# Taxonomy Philosophy

The taxonomy system is versioned and governed.

Taxonomy:
- must evolve,
- must be auditable,
- must not mutate unpredictably,
- and must remain operationally stable.

The system separates:

## Runtime Interpretation
Per-lead semantic classification.

## Taxonomy Governance
System-wide schema and semantic evolution.

---

# Event Philosophy

The system is fundamentally event-driven.

Everything becomes an event:

```text
lead.created
sms.received
call.completed
appointment.scheduled
consultation.completed
payment.received
```

Events:
- are immutable,
- are historically preserved,
- and drive workflow progression.

---

# Hybrid Storage Philosophy

The system intentionally combines:

## JSONB Event Store
Used for:
- raw payloads,
- schema evolution,
- diffs,
- AI outputs,
- metadata.

## Relational SQL Model
Used for:
- operational truth,
- workflows,
- appointments,
- analytics,
- identity,
- revenue,
- reporting.

## Vector Memory
Used for:
- transcript memory,
- semantic retrieval,
- contextual reasoning,
- communication understanding.

---

# Workflow Philosophy

The workflow engine controls:
- timing,
- retries,
- transitions,
- escalation,
- lifecycle state.

Agents do NOT control workflow progression directly.

Agents provide:
- recommendations,
- classifications,
- prioritization,
- and contextual interpretation.

---

# Human-in-the-Loop Principle

The platform assumes:
- humans remain operational supervisors,
- AI assists workflows,
- and high-risk actions require review.

Examples:
- clinical recommendations,
- PHI-sensitive operations,
- financial decisions,
- and taxonomy changes
should remain reviewable.

---

# PHI Boundary Principle

The repository and system must maintain a clear distinction between:

## PHI Domain
Clinical / HIPAA-sensitive data.

## OPS Domain
Operationally safe business intelligence.

The OPS layer should receive:
- safe summaries,
- workflow-safe projections,
- and operational abstractions.

The OPS layer should NOT receive:
- raw clinical notes,
- diagnoses,
- or unrestricted medical transcripts.

---

# Tool-First Architecture

Agents must interact with the system through tools.

Examples:

```text
resolve_person()
get_person_snapshot()
get_workflow_context()
create_followup_task()
schedule_callback()
send_sms_draft()
```

This guarantees:
- auditability,
- permission enforcement,
- safe abstraction,
- and system stability.

---

# Repository as Persistent Memory

The repository should function as:

```text
persistent operational memory
```

for:
- developers,
- coordinators,
- future engineers,
- AI agents,
- workflow systems,
- and orchestration pipelines.

This is critical because implementation details may evolve while strategic principles remain stable.

---

# Long-Term Strategic Goal

The platform should evolve from:

```text
Static CRM + manual operations
```

into:

```text
Dynamic semantic operational intelligence platform
```

Where:
- every interaction becomes structured operational knowledge,
- workflows are context-aware,
- agents operate safely through tools,
- and the system continuously learns without losing governance.

---

# Final Principle

Stable principles.
Flexible implementation.

The architecture must preserve:
- semantic consistency,
- auditability,
- identity continuity,
- workflow integrity,
- and controlled agent behavior,

even as:
- models,
- frameworks,
- APIs,
- and infrastructure
change over time.
