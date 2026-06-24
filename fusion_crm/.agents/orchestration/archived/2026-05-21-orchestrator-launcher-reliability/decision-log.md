# Decision Log

- 2026-05-20T17:00:00Z | orchestrator | Mission folder created at `.agents/orchestration/orchestrator-launcher-reliability/`. Prior `current/` archived to `.agents/orchestration/archived/2026-05-19-integration-foundation/`. Reason: prior wave was the merged integration-foundation set; reusing it would pollute the archive.
- 2026-05-20T17:00:00Z | orchestrator | Tests location set to `.agents/skills/agent-orchestrator/tests/` (skill-local). Reason: ship with the skill, do not pollute product `tests/`.
- 2026-05-20T17:00:00Z | orchestrator | Contract tests env-gated via `CODEX_CONTRACT_TESTS=1` and `CLAUDE_CONTRACT_TESTS=1`. Reason: hermetic CI without binaries.
- 2026-05-20T17:00:00Z | orchestrator | `--codex-bypass-approvals` defaults to off. Reason: safe default; opt-in per launch.
- 2026-05-20T17:00:00Z | orchestrator | Single parent Linear issue with Task A as hard blocker for B–H. Reason: B–H all depend on the post-A flag surface; sequential execution on one branch.
- 2026-05-20T17:48:26Z | verifier | TASK-A ACCEPTED. Reason: V1-V11 sweep passed independently; ppid=1 on detached background worker proves setsid fix landed. Acceptance #4 grep phrasing flagged for orchestrator rewording — current literal phrasing matches audit/strategy/mission docs that intentionally cite the deprecated flag.
- 2026-05-20T17:48:26Z | verifier | Do-not-merge condition recorded: TASK-B-H must land before integration (acceptance #3 requires pytest suite to be green).
