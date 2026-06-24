# SELF_LEARNING_AGENT_ARCHITECTURE.md

## Self-Learning Agent Architecture for Unified Dental Operations Platform


# Purpose

This document defines the architectural principles for building self-learning AI agents inside the Unified Dental Operations Platform.

The goal is NOT to create uncontrolled autonomous agents.

The goal IS to create:
- governed learning systems,
- semantically-aware workflow agents,
- adaptive operational intelligence,
- and continuously improving decision systems.

---

# Core Principle

Experience
→ Interpretation
→ Pattern Recognition
→ Structured Knowledge
→ Approved Learning
→ Improved Decisions

Self-learning agents must improve:
- workflow quality,
- semantic understanding,
- lead classification,
- follow-up prioritization,
- operational routing,
- and recommendation quality.

WITHOUT:
- bypassing governance,
- mutating production logic directly,
- or creating uncontrolled behavior.

---

# High-Level Learning Architecture

Raw Events
→ Event History
→ Semantic Interpretation
→ Workflow Outcomes
→ Pattern Analysis
→ Proposed Knowledge
→ Human / Governance Review
→ Approved Learning
→ Updated Agent Behavior

---

# Architectural Layers

## 1. Raw Event Layer

All external inputs are preserved unchanged.

Examples:
- Salesforce Lead updates
- CareStack appointment updates
- SMS messages
- AI call transcripts
- coordinator notes
- workflow state changes

Purpose:
- immutable history,
- auditability,
- future reprocessing,
- learning source data.

Agents NEVER overwrite raw history.

---

## 2. Semantic Interpretation Layer

Agents transform:
- raw CRM fields,
- transcripts,
- interactions,
- and operational events

into semantic meaning.

Example:

Double_Arch__c = true
Flexible_Payments__c = true

becomes:

intent = full_arch
financial_profile = financing_needed
lead_temperature = hot

This semantic layer becomes the operational language of the platform.

---

## 3. Workflow Intelligence Layer

The system tracks:
- workflow states,
- transitions,
- outcomes,
- failures,
- delays,
- conversions,
- and recovery patterns.

Examples:
- lead converted,
- consultation booked,
- no-show recovered,
- financing objection resolved,
- patient reactivated.

This creates operational feedback loops.

---

## 4. Pattern Recognition Layer

Learning agents analyze:
- repeated workflows,
- successful interventions,
- failed interventions,
- timing patterns,
- behavioral segments,
- and semantic correlations.

Examples:
- Spanish-speaking implant leads respond better to SMS before calls.
- Patients with financing anxiety respond better to coordinator escalation.
- Leads with repeated form submissions are high reconversion candidates.

---

## 5. Taxonomy Governance Layer

The system maintains:
- versioned taxonomy,
- semantic categories,
- workflow classifications,
- and operational dimensions.

Agents MAY:
- propose taxonomy updates,
- suggest new categories,
- identify obsolete fields,
- recommend semantic mappings.

Agents MUST NOT:
- automatically modify production taxonomy.

All taxonomy evolution must be:
- versioned,
- reviewed,
- auditable,
- and reversible.

---

## 6. Skill Generation Layer

Agents should gradually produce reusable operational skills.

Examples:
- lead_reactivation_skill
- financing_objection_skill
- no_show_recovery_skill
- carestack_identity_match_skill
- consultation_confirmation_skill

A skill represents:
- reusable operational reasoning,
- repeatable decision logic,
- contextual workflow intelligence,
- and semantic behavior patterns.

---

## 7. Vector Memory Layer

Self-learning agents require semantic memory.

Vector memory should store:
- transcript summaries,
- communication summaries,
- objections,
- behavioral observations,
- and operational reasoning.

Examples:
- Patient expressed financing anxiety.
- Patient prefers text communication.
- Patient responds negatively to aggressive follow-up.

This enables:
- semantic retrieval,
- contextual memory,
- and adaptive workflows.

---

## 8. Structured Operational Memory

The system must also maintain structured learning memory.

Examples:
- Most successful follow-up channel
- Average callback responsiveness
- Likely reconversion probability
- Preferred language
- High-value treatment indicators

This memory belongs in:
- normalized SQL tables,
- semantic profiles,
- workflow summaries,
- and analytics-safe structures.

---

## 9. Agent Learning Constraints

Agents MUST NOT:
- directly rewrite workflow rules,
- directly rewrite production schemas,
- directly mutate taxonomy,
- bypass audit logging,
- bypass human review,
- or operate outside approved tools.

Agents MUST:
- operate through tools,
- preserve explainability,
- preserve event lineage,
- produce auditable reasoning,
- and maintain deterministic workflow boundaries.

---

## 10. Human-in-the-Loop Learning

High-impact learning changes must require review.

Examples:
- taxonomy updates,
- workflow routing changes,
- new semantic categories,
- operational escalation rules,
- PHI-related classifications.

This preserves:
- governance,
- safety,
- explainability,
- and operational stability.

---

## 11. Agent Memory Philosophy

Agents should not rely entirely on:
- prompt context,
- temporary session memory,
- or raw transcript loading.

Instead, the system should provide decision context through tools.

Example:
get_decision_context(person_uid)

returns:
- semantic profile,
- recent workflow state,
- open tasks,
- relevant vector memories,
- communication summaries,
- and operational signals.

---

## 12. Self-Learning Through Workflow Outcomes

Agents improve by analyzing outcomes.

Examples:
- Which follow-up pattern led to consultation booking?
- Which communication pattern reduced no-shows?
- Which financing language improved conversion?
- Which workflow timing improved callbacks?

This creates reinforcement through operational feedback.

---

## 13. Multi-Agent Learning System

The platform should evolve toward specialized learning agents.

Examples:
- Taxonomy Governance Agent
- Workflow Optimization Agent
- No-Show Recovery Agent
- Lead Quality Agent
- Communication Optimization Agent
- Identity Resolution Agent

---

## 14. Repository as Persistent Memory

The repository itself becomes part of the learning system.

Repository documents should preserve:
- architectural principles,
- semantic rules,
- workflow philosophy,
- governance policies,
- and operational constraints.

Agents entering the repository should understand:
- what the system is,
- what it is not,
- what principles must remain stable,
- and how learning is controlled.

---

## 15. What This System Must Never Become

The system must never degrade into:
- uncontrolled autonomous AI
- direct SQL-writing agents
- ungoverned self-modifying workflows
- PHI leakage systems
- prompt-only memory systems
- CRM field chaos
- hidden non-auditable automation

---

## 16. Long-Term Strategic Goal

The long-term objective is to build Governed Operational Intelligence.

The platform should evolve from:
Static workflows + manual operations

into:
Adaptive semantic operational intelligence platform

while preserving:
- human oversight,
- deterministic workflow structure,
- PHI safety,
- operational transparency,
- and controlled learning evolution.

---

# Final Principle

Self-learning should improve:
- interpretation,
- prioritization,
- semantic understanding,
- and operational intelligence.

Self-learning should NEVER remove:
- governance,
- explainability,
- auditability,
- or human control.
