# Agent Runtime Control Plane V1

## Mission Goal

Turn the current Agent Runtime health-check into a governed product control
plane for Fusion CRM agents.

The mission starts from the existing foundation:

- tenant-scoped OpenAI credentials are stored server-side;
- the backend can run a server-side Agents SDK health check;
- `/dev/agent-runtime` exists as an internal workbench;
- Data Intelligence Agent tools and Semantic Catalog review flows already
  define the first downstream agent-adjacent surfaces.

## Business Outcome

Fusion should be able to show what agents are allowed to do, what they actually
did, where human approval is required, which policy posture applied, and how
agent outputs move into Data Intelligence and Semantic Catalog review without
becoming automatic business truth.

## Linear Structure

- Project: `Agent Runtime Control Plane V1`
- Parent issue: ENG-343 — Agent Runtime Control Plane V1 Mission Control
- Child issues:
  - ENG-344 — AR-01 Mission Setup And Linear Sync
  - ENG-345 — AR-02 Tools Registry Projection V1
  - ENG-346 — AR-03 Agent Run History V1
  - ENG-347 — AR-04 Human Approval Requests V1
  - ENG-348 — AR-05 Agent Audit Summaries V1
  - ENG-349 — AR-06 DIA And Semantic Catalog Linkage V1
  - ENG-350 — AR-07 Workbench Documentation And Verification

## Scope

- Create dashboard-visible Orchestrator state for the mission.
- Define and expose the Agent Runtime tools registry projection.
- Define first run history contracts and visible run summaries.
- Define human approval request contracts for agent proposals.
- Define safe audit summary posture for runtime actions.
- Connect Agent Runtime outputs to Data Intelligence Agent and Semantic
  Catalog review boundaries.
- Keep `/dev/agent-runtime` as the visible plan, docs, and verification surface.

## Non-Goals

- No autonomous write-capable agent in V1.
- No direct database access from agents.
- No raw SQL exposure.
- No automatic Semantic Catalog approval.
- No PHI, secrets, raw provider payloads, or unmasked sensitive values in
  prompts, run history, docs, or frontend responses.
