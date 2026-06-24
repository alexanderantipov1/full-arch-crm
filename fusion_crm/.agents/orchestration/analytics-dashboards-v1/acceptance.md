# Acceptance Criteria — analytics-dashboards-v1 (ENG-468)

## ENG-469 — discovery/mapping doc
- `docs/analytics/dashboards-mapping.md` committed.
- Each Replit dashboard metric mapped to OUR source-of-truth table
  (`marketing.*`, `ops.lead`/`opportunity`/`consultation`, `interaction.event`,
  CareStack revenue), with the computation recipe.
- Every metric we CANNOT yet compute is explicitly flagged (render "—", not
  fake zeros).
- Records which dashboards are buildable now vs partial/blocked.

## ENG-470/471/472/473 — dashboard pages
- New endpoint(s) in `apps/api/routers/dashboard.py` → read-only analytics
  service method (tenant-scoped) → Pydantic `*Out`. No business logic in route.
- Aggregation in a dedicated analytics read layer (service→repo, no commits).
- Zod schema in `apps/web/lib/api/schemas/` using `Datetime` from `common.ts`;
  any MSW handler for the route deleted when the real endpoint lands.
- TanStack hook + page under `apps/web/app/(staff)/analytics/<route>/page.tsx`
  with recharts + shadcn Card/Tabs/Skeleton, loading + error states.
- Nav entry added to the "Analytics" section in `AppShell.tsx` + `allDevHrefs`.
- Metrics without a source render "—" / "not connected", never fake zeros.

## ENG-474 — calls shell
- Page shell renders whatever `call_logged`/`call_reference_found` events exist;
  the rest is marked "pending Phase 3 comms ingest".

## Out of scope (do NOT build)
- AI Call Center (Sofia is the Replit app's own system), TV-wall dashboards,
  Excel export.
