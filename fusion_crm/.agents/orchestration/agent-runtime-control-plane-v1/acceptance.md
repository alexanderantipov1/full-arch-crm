# Acceptance Criteria

## Mission Setup

- The mission has durable repo artifacts under
  `.agents/orchestration/agent-runtime-control-plane-v1/`.
- Runtime state exists under the Orchestrator runtime home and includes
  `runtime.json`, `board.md`, `linear-sync.md`, and `runlog.md`.
- Linear project and issues ENG-343 through ENG-350 are mapped in runtime
  files.
- Every worker or self-execution task references a Linear issue id and URL.

## Product Acceptance

- `/dev/agent-runtime` shows OpenAI provider status, health-check controls,
  documentation, mission plan, and what remains for the second layer.
- Tools registry projection shows approved or planned agent-callable tools with
  data classes, limits, policy posture, and downstream surfaces.
- Run history and audit summary contracts prevent secrets, PHI, raw payloads,
  raw SQL, and unmasked rows from reaching the frontend.
- Approval requests make agent proposals review-only until a human approves or
  rejects them.
- DIA and Semantic Catalog linkage keeps the path explicit:
  agent run -> proposal -> approval -> catalog review -> approved version.

## Safety Acceptance

- Agents never call repositories or the database directly.
- Tools call services only.
- Semantic Catalog approved versions remain the only downstream catalog source.
- Frontend docs clearly distinguish Agent Runtime from Data Intelligence tools.
- Deferred work stays visible instead of being hidden inside completed claims.
