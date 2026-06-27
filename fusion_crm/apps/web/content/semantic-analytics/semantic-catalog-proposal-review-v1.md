# Semantic Catalog Proposal Review V1

This document defines the first human-review workflow for evolving the Semantic
Analytics Catalog.

## Purpose

The catalog must improve as real source data changes, but business meaning must
not be changed automatically by an LLM or by an agent. The Proposal Review V1
surface lets authorized builders review source-value discoveries and decide
which mappings become approved catalog truth.

## Current V1 UI Scope

The internal workbench should support:

- viewing proposed mappings;
- adding a manual proposal;
- editing raw value, source field, suggested term, definition, synonyms, reason,
  affected questions, affected read models, and reviewer note;
- marking a proposal as `approved`, `rejected`, `unresolved`, or `proposed`;
- seeing an impact preview before approval;
- seeing review history and approved term version history;
- generating a draft catalog patch from approved proposals through the backend
  API.

V1 stores proposals and approved catalog versions through the backend
`/semantic/catalog` API. Browser-local draft storage is no longer part of the
review workflow.

## Learning Model

The system should learn through reviewed catalog rules, not through model
memory.

```text
real data
-> read-only profiles and gaps
-> mapping proposals
-> human review
-> approved catalog version
-> services, read models, dashboard, chat, and agent tools consume approved meaning
```

The Data Intelligence Agent can propose meaning. Humans approve meaning. The
catalog stores meaning.

## Proposal Statuses

| Status | Meaning |
| --- | --- |
| `proposed` | Candidate mapping needs human review. |
| `approved` | Human reviewer agrees this can become catalog truth. |
| `rejected` | Human reviewer says the proposal is wrong or not useful. |
| `unresolved` | More evidence, owner decision, or Linear follow-up is needed. |

## Review Fields

Each proposal should include:

- `raw_value`;
- `source_system`;
- `source_field`;
- `suggested_term`;
- `definition`;
- `synonyms`;
- `confidence`;
- `reason`;
- `reviewer_note`;
- `affected_questions`;
- `affected_read_models`;
- `status`.

## Backend Status

The backend implementation now includes:

- service-owned catalog version storage;
- append-only audit for review actions;
- proposal source references from Data Intelligence Agent tools;
- review history and approved version history read paths;
- approved catalog version reads for services, dashboard, chat, and agent tools.

Follow-up work remains for:

- conflict detection when approved mappings change existing terms;
- impact preview from query registry and read-model metadata;
- Linear issue generation for unresolved gaps.

## Safety Rules

- Unreviewed proposals must not change production metrics.
- Agents must not approve proposals by themselves.
- Raw provider payloads must not be shown as ordinary review output.
- PHI fields remain denied unless a separate PHI-capable review lane is
  explicitly approved.
- Services, dashboards, chat, and agent tools must consume approved backend
  catalog versions, not browser draft state.

## Review Status

- Status: `current-focus`
- Owner: Orchestrator
- Next dependency: conflict detection and Linear follow-up automation.
