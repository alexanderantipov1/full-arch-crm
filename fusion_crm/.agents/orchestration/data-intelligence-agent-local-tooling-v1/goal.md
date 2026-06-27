# Data Intelligence Agent Local Tooling V1

## Mission Goal

Operationalize the internal Data Intelligence Agent as a local read-only
discovery and profiling lane under the existing Linear umbrella:

`Semantic Context And Analytics Foundation`

This mission follows ENG-279, which defined the Data Intelligence Agent
contract. This mission plans the implementation work required to let the agent
profile real local data through approved Fusion service and tool boundaries.

## Business Outcome

Fusion CRM should be able to understand real local data shape, source coverage,
linkage quality, semantic gaps, and evidence readiness for Salesforce,
CareStack, identity, ops, interaction, and billing-adjacent evidence without
letting agents access the database directly or generate SQL.

## Linear Structure

- Parent project: `Semantic Context And Analytics Foundation`
- Parent issue: ENG-286 — Data Intelligence Agent Local Tooling V1
- Child issues: ENG-287 through ENG-299

## Scope

- Create policy and allowlist for local Data Intelligence tooling.
- Define service-owned profiling contracts and DTOs.
- Expose approved tools for dataset discovery, field profiling, linkage
  coverage, evidence coverage, bounded masked samples, mapping proposals, and
  gap briefs.
- Add audit/logging expectations for tool calls.
- Add local workbench visibility if included during execution.
- Verify allowed and denied paths.

## Non-Goals

- No generic SQL terminal.
- No LLM-generated SQL.
- No direct database access by agents.
- No raw provider payload output.
- No PHI output in V1.
- No exports, XLSX, or scheduled reports.
- No Worker launch until explicit human approval after this Linear structure.
