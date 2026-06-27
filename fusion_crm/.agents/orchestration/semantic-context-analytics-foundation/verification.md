# Verification — Semantic Context And Analytics Foundation

## Planning Verification

- Run `python3 .agents/skills/agent-orchestrator/scripts/status_wave.py --mission .agents/orchestration/semantic-context-analytics-foundation`.
- Confirm runtime state resolves to
  `~/.fusion-agent-orchestrator/<repo-hash>/semantic-context-analytics-foundation/`.
- Confirm `runtime.json` contains the Strategy -> Orchestrator handoff.
- Confirm `board.md` and `linear-sync.md` list ENG-272 through ENG-281.
- Confirm no worker sessions were launched for this mission.
- Confirm no implementation branches were created for this mission.
- Confirm product code was not modified.

## First Slice Verification

For `Manager Analytics Questions and Semantic Catalog V1`:

- Questions cover lead source, consultation, follow-up, treatment, payment,
  owner, location, and risk workflows.
- The seed draft in `manager-analytics-questions-v1.md` is reviewed before it
  becomes product truth.
- Each question has priority, expected output, filters, row-level/aggregate
  need, data-class concern, and reviewer.
- Catalog terms have definitions, synonyms, source references, data classes,
  permissions, allowed fields, row-level/aggregate rules, version, owner, and
  review status.
- Terms touching PHI, PHI-adjacent, billing, or raw provider evidence are
  explicitly classified.
- Backend implementation needs are identified before service work begins.

For `Data Intelligence Agent V1`:

- Local tooling is read-only and allowlisted.
- Direct agent database access is not permitted.
- Samples have row limits and masking/redaction behavior.
- Tool outputs are gap briefs, profile summaries, and semantic mapping
  proposals, not raw dumps.
- No `.env*` files are read.

For `Semantic Analytics Workbench V1`:

- The frontend can render manager questions, semantic catalog terms, Data
  Intelligence Agent contract, and backend handoff documentation.
- The workbench is read-only.
- The UI distinguishes documentation from executable analytics behavior.
- The UI does not define metric business logic.
- The UI does not expose raw provider payloads.
- Data-class badges and allowed output posture are visible.
- Source artifact links, version, review status, and implementation readiness
  are visible.

## Future Implementation Verification

When implementation begins, use the repository verification loop appropriate to
the touched area:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

Additional checks for this mission:

- raw provider payloads are excluded from ordinary dashboard, chat, agent, and
  analytics results;
- query specs reject raw SQL;
- policy preflight runs before analytics execution;
- PHI access goes through `PhiService` and writes audit;
- services own analytics logic and repositories remain data-only;
- browser-only filters do not define business metrics;
- exports are unavailable unless policy permits them.
