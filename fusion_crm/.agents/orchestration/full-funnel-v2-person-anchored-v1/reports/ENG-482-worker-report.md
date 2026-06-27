# Worker Report — ENG-482 Full Funnel v2 frontend (person-anchored)

- **Task:** ENG-482 — Full Funnel v2 frontend (consume the new ENG-481 contract)
- **Parent epic:** ENG-480
- **Role / agent:** worker / Claude Code (Opus 4.8 1M)
- **Branch:** current working branch (working tree only — NOT committed, NOT pushed)
- **Scope:** funnel page + its Zod schema + its data hook

## What changed

Rewired the Full Funnel page to the **person-anchored v2 contract**
(`FullFunnelV2Out` in `packages/analytics/schemas.py`). The page now drives an
`audience` toggle, renders the no-show stage, and treats closed-won as money
received.

### Changed files

- `apps/web/lib/api/schemas/fullFunnel.ts` — **rewritten** to mirror
  `packages/analytics/schemas.py::FullFunnelV2Out` field-for-field:
  `FullFunnelAudienceSchema` (`all` | `marketing`), `FullFunnelChannelSchema`
  (`google` | `facebook` | `other`), `FullFunnelWindowSchema`
  (`start_month` / `end_month`), `FullFunnelHeadlineSchema`
  (`leads`, `consults_scheduled`, `showed`, `no_show`, `closed_won`,
  `revenue`), `FullFunnelMonthSchema` (adds `no_show`; `spend` nullable),
  `FullFunnelChannelRowSchema` (adds `no_show`; NO per-channel `closed_won`;
  `spend` nullable), and the top-level `FullFunnelSchema`
  (`audience`, `window`, `channels`, `headline`, `by_month`, `by_channel`).
  Kept `FullFunnelNotConfiguredSchema` in this file because `salesAnalytics.ts`
  and `seoAnalytics.ts` import it (backend keeps `FullFunnelNotConfiguredOut`);
  dropping it would break those contracts. Removed the dead ENG-472 shapes
  (`impressions`, `consults_attended`, `closed`, `carryover`,
  `center_breakdown`, `tc_breakdown`, the old `months`/per-month `channels`
  nesting).
- `apps/web/lib/api/hooks/useFullFunnel.ts` — added `audience?:
  FullFunnelAudience` to `FullFunnelFilters`. It flows through the existing
  `toQueryString` (so `?audience=…` is sent) and is part of the React Query
  key, so toggling refetches.
- `apps/web/app/(staff)/analytics/funnel/page.tsx` — **rewritten**:
  - **Marketing / All toggle** (shadcn `Button` segmented group, `default` vs
    `ghost` variant; `all` default) driving the `audience` query param.
  - **Headline KPIs** read from `headline`: Leads · Consults scheduled ·
    Showed · No-show · Closed won (money) · Revenue (6-up grid).
  - **No-show** added to the aggregate bar funnel, the monthly table, and the
    by-channel table.
  - **Closed won** rendered as money received (CareStack net collected cash);
    KPI shows the dollar figure with a tooltip clarifying it is money in the
    door (not the SF is-won flag) and noting the paying-person count. Monthly
    table keeps the integer `closed_won` (paying persons) column with the same
    clarifying header tooltip; revenue column shows the cash.
  - `—` rendering kept strictly for `spend === null` (unconnected source /
    spendless month). Real integer counts (incl. genuine `0`) render as
    numbers, never `—`.
  - Helper copy under the title rewritten for the person-anchored,
    Marketing/All, CareStack-truth model; removed the old "Channels are limited
    to Google / Facebook / Other today" line.
  - Reads `by_month` / `by_channel` flat arrays (v2) instead of the old nested
    `months[].channels[]`.

No MSW handler existed for `/dashboard/analytics/full-funnel`
(`grep` of `apps/web/lib/msw` found none) — nothing to delete.

## Verification

- **`npm run typecheck`** (`tsc --noEmit`) in `apps/web`: **clean, no errors**
  (ran twice — once via `npm run typecheck`, once via direct `npx tsc
  --noEmit`; both exit 0).
- **`npm run lint`** (`next lint` — ESLint): **`✔ No ESLint warnings or
  errors`.**
- **`npm run build`** (`next build`): **could not complete on this machine —
  environment stall, not a code error.** Reproduced twice (including a clean
  run with `.next` removed and the contending `next dev` server killed): the
  build reaches `Creating an optimized production build ...` (webpack compile)
  then sits at **0% CPU** indefinitely (>14 min on the first run). This is the
  documented local `next build` stall trap, independent of this change. The two
  authoritative static gates — `tsc --noEmit` (full TS type check) and `next
  lint` (ESLint) — both pass clean, so the code itself is sound. The build
  printed **no errors** before stalling. Recommend re-running `npm run build`
  on a clean CI runner to confirm.

### Visual confirmation (how to)

`cd apps/web && npm run dev`, open `/analytics/funnel`. Expect: a Marketing/All
toggle top-right next to the period select. Toggling to Marketing refetches and
shrinks every number (`marketing ⊆ all`). The bar funnel shows five stages incl.
No-show; the Monthly table has Spend · Leads · Scheduled · Showed · No-show ·
Closed won · Revenue; the By-channel table has the same minus Closed won, with
Spend "—" for the Other channel.

## Contract discrepancies vs the backend

**None.** The Zod schema mirrors `FullFunnelV2Out` exactly:

- `headline`: `leads`, `consults_scheduled`, `showed`, `no_show`, `closed_won`
  (int), `revenue` (float) — match.
- `by_month[]`: `month`, `spend` (nullable), `leads`, `consults_scheduled`,
  `showed`, `no_show`, `closed_won`, `revenue` — match.
- `by_channel[]`: `month`, `channel` (google|facebook|other), `spend`
  (nullable), `leads`, `consults_scheduled`, `showed`, `no_show`, `revenue` —
  match; **no** per-channel `closed_won`, as the backend omits it.
- `audience`, `window{start_month,end_month}`, `channels: string[]` — match.

Note: the Zod schema types `closed_won` / counts as `z.number()` (TS has no
int/float split); the backend emits ints there and a float for `revenue` —
both parse fine.
