# Verification

## Pre-merge checks

1. `pnpm --filter @fusion-crm/web lint` (or `npm run lint` inside
   `apps/web`) clean.
2. `pnpm --filter @fusion-crm/web typecheck` clean.
3. `pnpm --filter @fusion-crm/web test` green (existing + new tests).
4. `grep -RIn "Reconnect flow ships with ENG-128"
   apps/web` returns nothing — stale placeholder removed.
5. Manual smoke recorded in `reports/TASK-H-smoke.md`:
   - Reconnect SF locally end-to-end.
   - Edit CS API key locally.
   - Disconnect SF with typed-confirm.
   - Verify `refreshed_at` / `expires_at` render correctly.
   - Verify callback URL copy works.

## Worker report contract

Final report at `reports/TASK-A-H-worker-report.md` lists changed files,
new tests, manual smoke evidence, do-not-merge conditions, and the
verifier handoff line.
