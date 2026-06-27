# Agent Orchestration Board

| Task | Linear Issue | Role | Owner | Branch | Worktree | Status | Write Scope | Depends On | Report |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | ENG-178 | Claude Code worker | terminal-1 | primary or agent/deploy-smoke-recovery-A1 | primary | reviewed | `.github/workflows/deploy-prod.yml`, optional `tests/core/test_deploy_prod_smoke_logging.py` | none | reports/A1.md |
| A2 | ENG-178 / ENG-180 | Claude Code explorer | terminal-2 | read-only | primary | partial | none | none | reports/A2.md |
| A3 | ENG-178 / ENG-180 | Codex integrator/verifier | orchestrator or terminal-3 | integration/deploy-smoke-recovery | ../Fusion_crm-integration | blocked | integration only | A1, A2 live-evidence follow-up | reports/A3.md |

## File Ownership

| Path / Module | Owner | Status | Notes |
| --- | --- | --- | --- |
| `.github/workflows/deploy-prod.yml` | A1 | planned | Smoke diagnostic logging only. |
| `tests/core/test_deploy_prod_smoke_logging.py` | A1 | reviewed | Static regression test added and passed under Codex review. |
| GitHub Actions logs | A2 | blocked | Claude Code harness denied `gh run`/`gh api`; needs widened permissions or Codex read-only follow-up. |
| Cloud Run logs | A2 | blocked | Claude Code harness denied `gcloud logging read`; needs widened permissions or Codex read-only follow-up. |
| Tenant credential product files | unassigned | protected | Existing dirty files; not part of Wave 1. |

## Blockers

- ENG-178 cannot be accepted until deploy-prod smoke is green end-to-end.
- ENG-180 cannot be completed until deploy-prod green end-to-end proves the pinned IAP audience path.
- Any production deploy/rerun/rollback requires explicit user approval.
- A2 live evidence was not collected in Wave 1 because Claude Code `dontAsk` mode blocked read-only `gh run`, `gh api`, and `gcloud logging read`.
- Claude Code local permissions were broadened after Wave 1. `gh run list` was verified as allowed; A2-live can now be launched for real evidence collection.

## Review Notes

- 2026-05-17 Codex review of A1: ownership respected. Focused test `python -m pytest tests/core/test_deploy_prod_smoke_logging.py` passed: 4 tests.
- 2026-05-17 Codex review of A2: read-only report accepted as partial. It contains useful repo-side inference and concrete follow-up log filters, but no live GitHub Actions or Cloud Run evidence.
- 2026-05-17 Codex permission check: Claude Code `dontAsk` successfully ran `gh run list --workflow deploy-prod.yml --branch main --limit 1` and found failed deploy-prod run `25982799094`.
