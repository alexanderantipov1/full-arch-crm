# ENG-205 Worker Report

## Scope

Linear: https://linear.app/fusion-dental-implants/issue/ENG-205/move-legacy-integrations-ui-into-tenant-settings

Verified the legacy integrations UI move into tenant settings without touching ENG-204 source-data work or ENG-206 people search route work.

## Touched Files

- `.agents/orchestration/current/reports/ENG-205-worker-report.md`

No code files were changed by this worker. Existing workspace changes in the ENG-205 scope were inspected only:

- `apps/web/app/(staff)/integrations/page.tsx`
- `apps/web/app/(staff)/settings/tenant/page.tsx`
- `apps/web/app/(staff)/integrations/carestack/page.tsx`
- `apps/web/components/layout/AppShell.tsx`
- deleted legacy Salesforce Lead files that are still visible in `git status`

## Verification

- `/integrations` now server-redirects to `/settings/tenant?tab=integrations`.
- Tenant settings reads `?tab=integrations`, controls the active tab from the query string, and keeps the integrations tab after OAuth callback cleanup.
- The CareStack inspector back link targets `/settings/tenant?tab=integrations`.
- The sidebar no longer links to the legacy `/integrations` page; it links to tenant settings and the CareStack inspector.
- Legacy Salesforce Lead UI/hook/schema references were not found in active web app code.
- Deleted legacy files are not referenced by active imports:
  - `apps/web/components/integrations/SfLeadDetailDialog.tsx`
  - `apps/web/components/integrations/SfLeadsPanel.tsx`
  - `apps/web/lib/api/hooks/useSfLeads.ts`
  - `apps/web/lib/api/schemas/sfLead.ts`

## Commands Run

- `cd apps/web && npm run typecheck` - passed
- `cd apps/web && npm run lint` - passed
- `cd apps/web && npm run test` - passed, 5 files / 24 tests
- `rg -n "SfLeads|SfLead|useSfLeads|sfLead|Salesforce Leads|manual Salesforce|LeadDetail|LeadsPanel|/integrations\"|href=\"/integrations\"" apps/web/app apps/web/components apps/web/lib -g '!node_modules'` - no legacy Salesforce Lead UI references found; remaining `/integrations` matches are API/MSW endpoint paths, not route navigation

Note: an initial `npm run test -- --runInBand` attempt failed because Vitest does not support Jest's `--runInBand` flag. The supported `npm run test` command passed.

## Risks

- The working tree contains many unrelated modified/untracked files from other orchestration work. This worker did not modify or revert them.
- `apps/web/components/layout/AppShell.tsx` currently includes unrelated source-data sidebar changes from ENG-204; left untouched.
- `apps/web/app/api/people/search/route.ts` has unrelated ENG-206 changes; left untouched.

## Blockers

- None for ENG-205 verification.

## Suggested Next Task

- Add or update a focused component/navigation test for tenant settings tab query handling if the orchestration wave wants automated coverage for `/settings/tenant?tab=integrations`.

## Do Not Merge Conditions

- Do not merge if deleted legacy Salesforce Lead files are reintroduced or referenced again.
- Do not merge if `/integrations` renders the legacy provider/manual Salesforce Leads page instead of redirecting to `/settings/tenant?tab=integrations`.
- Do not merge if the sidebar links directly to `/integrations` as a primary navigation target.
- Do not merge if web typecheck, lint, or tests fail after other workers' changes are reconciled.
