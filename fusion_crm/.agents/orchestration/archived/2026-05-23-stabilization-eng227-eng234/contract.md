# Contract

## Scope

- Linear issues covered: ENG-227, ENG-228, ENG-229, ENG-230, ENG-231, ENG-232.
- Execution is limited to verification stabilization, tenant-isolation safety
  net follow-up, and local agent-orchestration state.
- Production-reviewer agent work is already isolated in commit `44d704e`.
- Current dirty `apps/web/*` and `.agents/strategy/*` changes are not part of
  the production-reviewer commit scope.

## Invariants

- Do not weaken tenant isolation tests to make the suite pass.
- Do not record PHI, secrets, or `.env*` values in mission files.
- Do not change deployment, OAuth/CORS, Cloud Run, deploy scripts, GitHub
  Actions deployment, or env var contracts in this mission.
- Keep repository files in English.
- Do not commit, push, or run destructive git commands without explicit user
  approval.

## Completion Gate

Before opening a PR from the current checkout, rerun:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

If the dirty web changes remain in scope, also rerun:

- `cd apps/web && npm run lint`
- relevant Playwright smoke coverage
