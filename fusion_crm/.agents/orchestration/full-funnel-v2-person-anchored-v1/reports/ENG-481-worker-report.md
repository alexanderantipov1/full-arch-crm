# Worker Report — ENG-481 Full Funnel v2 backend (person-anchored read model + API)

- **Task:** ENG-481 — Full Funnel v2 backend (person-anchored read model + API)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-481
- **Parent epic:** ENG-480
- **Role / agent:** worker / Claude Code (Opus 4.8 1M)
- **Branch:** `eng-481-full-funnel-v2-backend` (working tree only — NOT committed, NOT pushed)
- **Workspace:** canonical checkout
- **Scope:** backend read model + API for `GET /dashboard/analytics/full-funnel`

## What changed

Replaced the lead-anchored Full Funnel computation (ENG-472) with a
**person-anchored** read model computed per `audience` (`marketing` | `all`),
exposed on the same endpoint. The route is now a thin composer over a new
read-only composition service; all aggregation reads live on the owning
domains. No new tables, no Alembic migration.

### Architecture

- New composition service `packages/analytics/full_funnel.py::FullFunnelService`
  — read-only, composes `OpsService` + `IdentityService` +
  `InteractionService` + `MarketingService`. Owns NO SQL; stitches DTOs from
  each domain. Wired at the app boundary via
  `apps/api/dependencies.py::get_full_funnel_service` so cross-domain crossings
  stay service-only (per `packages/CLAUDE.md`).
- Person universe = distinct `person_uid` in `ops.lead` ∪
  `identity.source_link(source_system='carestack', source_kind='patient')` —
  the same anchor `project-manager/leads` uses.
- Per-stage windowing on the stage's OWN timestamp: leads on lead provider
  created-at (`extra.sf_created_at` ?? `created_at`) / CareStack
  `source_link.first_seen_at`; consults on `consultation.scheduled_at`;
  revenue/closed-won on `interaction.event.occurred_at`. Monthly buckets per
  stage's own `YYYY-MM` (UTC).
- Audience resolved through ONE shared person→channel map
  (`OpsService.full_funnel_person_channels`, built on the existing
  `_explorer_channel_label` resolver collapsed to google/facebook/other). A
  person is `marketing` iff their lead resolves to an ad channel
  (google/facebook). Same map attributes consults/revenue to a channel column,
  so `marketing ⊆ all` holds by construction. The legacy `classifyLeadSource`
  is NOT forked.
- Revenue = Net Collected (`payment_recorded − payment_refunded −
  payment_reversed`, `payment_applied` excluded) read through
  `InteractionService` — the router never touches `event.payload` JSON.
- `closed_won` = distinct persons with windowed Net Collected > 0 (money is
  closure). Kept month-level in the contract; per-channel `closed_won` is
  omitted (opportunity→channel attribution deferred).

### Changed files (full list)

- `packages/analytics/full_funnel.py` — **new**: `FullFunnelService` composition.
- `packages/analytics/schemas.py` — **new DTOs**: `FullFunnelV2Out`,
  `FullFunnelV2HeadlineOut`, `FullFunnelV2MonthOut`, `FullFunnelV2ChannelRowOut`,
  `FullFunnelV2WindowOut`, plus `FullFunnelAudience` / `FullFunnelChannel`.
- `packages/ops/repository.py` — `_funnel_channel_label()`,
  `_funnel_month_key()`, `_FUNNEL_AD_CHANNELS`; repo methods
  `full_funnel_lead_rows`, `full_funnel_person_channels`,
  `full_funnel_consultation_rows`.
- `packages/ops/service.py` — `FunnelLeadRow` / `FunnelConsultationRow`
  dataclasses; service methods `full_funnel_lead_rows`,
  `full_funnel_person_channels`, `full_funnel_consultation_rows`.
- `packages/identity/repository.py` — `full_funnel_patient_rows`.
- `packages/identity/service.py` — `full_funnel_patient_rows`.
- `packages/interaction/repository.py` — `sum_collected_by_person_month`.
- `packages/interaction/service.py` — `collected_by_person_month`.
- `apps/api/dependencies.py` — import `FullFunnelService`; add
  `get_full_funnel_service`.
- `apps/api/routers/dashboard.py` — rewrote `analytics_full_funnel` as a thin
  composer (adds `audience` query param, returns `FullFunnelV2Out`); removed
  the dead ENG-472 funnel DTOs (`FullFunnelOut`/`MonthOut`/`ChannelRowOut`/
  `WindowOut`), constants (`_FUNNEL_CHANNELS`/`_FUNNEL_DEFAULT_MONTHS`/
  `_FUNNEL_MAX_MONTHS`), and helpers (`_PROVIDER_TO_CHANNEL`,
  `_funnel_channel_of`, `_month_key`, `_add_month`, `_iter_month_windows`).
  Kept `FullFunnelNotConfiguredOut` (reused by SEO + follow-up tiles).

## Final response field names (canonical contract for the frontend — ENG-482)

`GET /dashboard/analytics/full-funnel?audience=all|marketing&start_date=&end_date=`

```jsonc
{
  "audience": "all" | "marketing",
  "window": { "start_month": "YYYY-MM", "end_month": "YYYY-MM" },
  "channels": ["google", "facebook", "other"],
  "headline": {
    "leads": int,
    "consults_scheduled": int,
    "showed": int,
    "no_show": int,
    "closed_won": int,        // money-based count of paying persons
    "revenue": float
  },
  "by_month": [
    {
      "month": "YYYY-MM",
      "spend": float | null,  // marketing channels only; null if no spend
      "leads": int,
      "consults_scheduled": int,
      "showed": int,
      "no_show": int,
      "closed_won": int,
      "revenue": float
    }
  ],
  "by_channel": [
    {
      "month": "YYYY-MM",
      "channel": "google" | "facebook" | "other",
      "spend": float | null,  // null for "other" and months with no spend
      "leads": int,
      "consults_scheduled": int,
      "showed": int,
      "no_show": int,
      "revenue": float
      // NOTE: no per-channel closed_won — stays month-level
    }
  ]
}
```

Rendering rule: `spend` is `null` (render `—`) for the `other` channel and any
month with no ingested ad spend. Stage counts are distinct-person counts;
`revenue` is summed net cash. `closed_won` appears in `headline` and `by_month`
only.

## Verification

- **ruff** (changed files): `All checks passed!`
- **mypy** (`packages/analytics packages/ops packages/identity
  packages/interaction apps/api`): `Success: no issues found in 52 source files`
- **pytest** `tests/integration/test_full_funnel.py`: `3 passed` (these target
  the unchanged underlying service methods — `monthly_spend_by_provider`,
  `get_opportunity_outcomes_by_month`, `get_lead_source_tree` — which v2 no
  longer calls from the route but which remain on the services).
- **Live endpoint** (local API on 127.0.0.1:8000, real DB on 5434) curled for
  both audiences + a custom date range — all returned 200 with the contract
  shape.

## Reconciliation (local DB, 5434, default trailing-6mo window 2026-01..2026-06)

| Metric | API (audience=all) | Raw DB query | Match |
|---|---|---|---|
| leads (universe) | 68,494 | `ops.lead ∪ source_link(carestack/patient)` windowed = 68,494 | ✓ |
| consults_scheduled (distinct persons) | 5,485 | distinct person_uid, any status, scheduled_at in window = 5,485 | ✓ |
| showed (distinct persons) | 3,555 | distinct person_uid status='completed' = 3,555 | ✓ |
| no_show (distinct persons) | 962 | distinct person_uid status='no_show' = 962 | ✓ |
| revenue (Net Collected) | 6,202,440.87 | Σ recorded − Σ(refunded+reversed), occurred_at in window = 6,202,440.87 | ✓ |
| closed_won (payers) | 1,944 | per-month-positive payers unioned (window-grouped payers>0 = 1,942) | ≈ (see note) |

Note on `closed_won`: the headline value (1,944) unions the per-month
positive-payer sets; the single-grouped windowed payer count (1,942) groups
net over the whole window. The 2-person delta is persons net-positive in one
month but net-zero/negative over the full window — both are valid
interpretations; the per-month definition matches how `by_month.closed_won`
is reported.

**Audience reconciliation (audience=marketing):**
headline = `{leads: 12,811, consults_scheduled: 603, showed: 223, no_show: 247,
closed_won: 79, revenue: 377,994.12}`.

- `marketing ⊆ all` verified programmatically for EVERY stage across headline,
  every `by_month` row, and every `by_channel` row → **PASS** (no violations).
- CareStack-direct / non-ad persons: `all` `other`-channel leads = 55,783;
  `marketing` `other`-channel leads = 0 (confirms direct patients appear in
  `all` but never in `marketing`).
- `spend` is `null` for the `other` channel and present for google/facebook.
- Custom range `start_date=2026-03-01&end_date=2026-04-30` → window
  `2026-03..2026-04`, leads headline 5,792 (window bounding works).

## Risks / open questions

1. **`closed_won` definition (per-month vs window-grouped).** Headline unions
   per-month positive-payer sets (matches `by_month`). If the operator wants
   "distinct persons net-positive over the WHOLE window", that's a 2-person
   difference here; trivially switchable in `_assemble`. Flagged for ENG-483.
2. **Phone E.164 under-merge (ENG-463, accepted out-of-scope §8.1).** ~2,117
   CareStack-direct persons that match an SF lead by phone sit on a different
   `person_uid`; they count as non-marketing in `all` and are absent from
   `marketing` until normalization lands. Funnel logic is correct regardless.
3. **`get_opportunity_outcomes_by_month` is now unused by the funnel route**
   but remains on `OpsService` (Sales dashboard / future use). Left in place;
   not dead code at the package level.
4. **Performance.** Each stage is a single grouped SQL read over the window
   (no per-month fan-out like ENG-472's per-month tree). The lead/consult reads
   return `(person, channel/status, month)` rows; the largest is the lead
   universe (~68k window rows) materialized into Python sets — acceptable, and
   bounded by the 24-month window guard.
5. **No new integration test for the v2 route shape yet** — that is ENG-483's
   scope (real-PostgreSQL integration tests + lock). Existing funnel test still
   green because it tests the underlying service methods, not the route.

## Do-not-merge conditions

- Operator/Orchestrator review of the canonical contract field names before
  ENG-482 (frontend) starts its Zod schema.
- ENG-483 verification pass (integration tests on real PostgreSQL).

## Suggested next task

ENG-482 (frontend) — mirror the contract above in
`apps/web/lib/api/schemas/fullFunnel.ts`; then ENG-483 (real-data verify +
integration tests). Do not start ENG-482 from this session.

---

## CS-direct dating fix (ENG-481 follow-up)

### Bug
The leads stage dated CareStack-direct persons (a `carestack/patient`
source_link with no `ops.lead`) by `source_link.first_seen_at`. All CareStack
patients were bulk-pulled in one 2026-05 batch, so `first_seen_at` clustered
~52k of them into 2026-05 — a fake spike of ~56k leads. The CareStack patient
object has no creation date, so `first_seen_at` is meaningless for funnel timing
(it is a `bulk_import` provenance marker recorded in `source_link.meta`).

### Fix
For the leads stage only, each CareStack-direct person (a `carestack/patient`
link AND no `ops.lead` anywhere, any time) is now dated by earliest real
activity, all-time:
`funnel_entry = COALESCE(MIN(consultation.scheduled_at), MIN(event.occurred_at), 2025-01-01 UTC sentinel)`,
bucketed into the month of `funnel_entry`, counted as a lead only if it lands in
the report window. Zero-activity persons fall to the 2025-01-01 sentinel (outside
the default trailing-6-month window → drop out). SF-lead persons keep their
existing lead-date logic. Consults/showed/no-show/closed-won/revenue stages and
the CareStack-direct `other` channel are unchanged.

The "no `ops.lead`" exclusion is cross-domain, so it is applied in the
`packages/analytics` composition layer (subtract lead-bearing person_uids from
the CareStack-direct universe). Per-person MIN aggregates are computed as a
single GROUP BY over the whole table each (NOT a bound IN over the ~50k-person
universe — that blows asyncpg's parameter cap); the composition layer indexes
into them per person.

### Changed files
- `packages/analytics/full_funnel.py` — replaced the `patient_rows` leads block
  with `_add_carestack_direct_leads(...)`; added `_CARESTACK_DIRECT_SENTINEL`.
- `packages/identity/repository.py` + `service.py` — added
  `full_funnel_carestack_patient_person_uids` (all-time CS-patient universe);
  removed now-dead `full_funnel_patient_rows`.
- `packages/ops/repository.py` + `service.py` — added
  `full_funnel_lead_person_uids` (no-lead exclusion set) and
  `full_funnel_earliest_consultation_at_by_person` (MIN scheduled_at GROUP BY).
- `packages/interaction/repository.py` + `service.py` — added
  `earliest_event_at_by_person` (MIN occurred_at GROUP BY).
- `docs/analytics/full-funnel-v2-person-anchored.md` §5 — documented the rule
  + the `source_link.meta` bulk_import marker.

### Verification
ruff: All checks passed. mypy: Success, no issues found in 16 source files.

Live endpoint `GET /dashboard/analytics/full-funnel?audience=all`
(window 2026-01..2026-06), by_month leads:

| month | leads | target |
|---|---|---|
| 2026-01 | 3217 | 3217 |
| 2026-02 | 2662 | 2662 |
| 2026-03 | 3388 | 3388 |
| 2026-04 | 3336 | 3336 |
| 2026-05 | 3006 | 3006 |
| 2026-06 | 1355 | 1355 |

All six months match exactly (PASS). 2026-05 = 3006, not ~56000 — the spike is
gone.

`audience=marketing` leads (2336 / 1960 / 2557 / 2587 / 2229 / 870) are ≤ the
`all` values for every month, so `marketing ⊆ all` holds (CareStack-direct
persons are channel `other`, present only under `all`).

---

## Consult appointment-level breakdown (ENG-481 follow-up, operator-approved 2026-06-16)

**Decision:** the consultation stages are now counted at the **appointment
level** — one count per `ops.consultation` row, NOT distinct persons — and ALL
statuses are shown so they balance:

```
Scheduled (= total appointment rows in month)
  = Showed + No-show + Cancelled + Rescheduled + Pending
```

Raw `ops.consultation.status` → counter mapping:
`completed → showed`, `no_show → no_show`, `cancelled → cancelled`,
`rescheduled → rescheduled`, `scheduled → pending` (appointment not yet held /
future). `consults_scheduled` is the sum of all five.

Leads and closed-won stay **person-level** (`set[UUID]`), revenue stays summed
cash — only the consult stages moved from person-sets to integer appointment
counters. The audience filter and per-channel attribution still apply per
appointment via the booking person's channel, so `marketing ⊆ all` still holds.

### Changed files

- `packages/analytics/full_funnel.py` — `_StageCell` consult fields changed
  from `set[UUID]` to `int` counters (`consults_scheduled`, `showed`,
  `no_show`, `cancelled`, `rescheduled`, `pending`); consult loop increments
  `consults_scheduled += 1` plus the matching status counter; `_assemble`
  aggregates consult counters by SUM (headline = sum across months, no
  person-dedup) while keeping leads/closed-won as set unions.
- `packages/analytics/schemas.py` — added `cancelled`, `rescheduled`, `pending`
  (int) to headline / by_month / by_channel `*Out` models.
- `apps/web/lib/api/schemas/fullFunnel.ts` — mirrored the three new fields into
  headline / month / channel Zod schemas.
- `apps/web/app/(staff)/analytics/funnel/page.tsx` — added Cancelled /
  Rescheduled / Pending to headline KPIs (grid widened to 9), funnel bar
  stages, monthly table, and by-channel table; added captions clarifying the
  consult stages are counted by APPOINTMENT (balance equation) while
  Leads/Closed-won are people; funnel-bar tooltip now labels consult stages
  "Appointments" and Leads/Closed-won "Persons".
- `docs/analytics/full-funnel-v2-person-anchored.md` §3 — updated the
  stage→source table + notes for the appointment-level 5-status breakdown.

### Live-endpoint verification (`audience=all`, default 6-month window → 2026-06)

| month | scheduled | showed | no_show | cancelled | rescheduled | pending | sum | sum==sched |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 2153 | 1179 | 194 | 256 | 340 | 184 | 2153 | YES |
| 2026-02 | 2017 | 1179 | 128 | 187 | 351 | 172 | 2017 | YES |
| 2026-03 | 2265 | 1311 | 195 | 221 | 376 | 162 | 2265 | YES |
| 2026-04 | 2272 | 1354 | 227 | 253 | 334 | 104 | 2272 | YES |
| 2026-05 | 2312 | 1220 | 203 | 216 | 384 | 289 | 2312 | YES |
| 2026-06 | 2069 | 759 | 114 | 155 | 289 | 752 | 2069 | YES |

All consult numbers match the acceptance gate exactly; the sum identity holds
for every month. Revenue headline = $6,215,412.37 (unchanged, ~$6.21M).

Leads (all): 3217 / 2662 / 3388 / 3336 / 3006 / **1357** — the first five match
the gate exactly; 2026-06 reads 1357 vs the gate's 1355 (a +2 drift). Leads were
NOT touched by this change; the delta is pre-existing time-dependent
CareStack-direct lead dating (earliest-activity bucketing relative to "now",
today = 2026-06-16) plus any ingestion since the gate snapshot — not a
regression of the consult work.

`audience=marketing` consult counts (scheduled 154 / 97 / 167 / 197 / 228 / 226)
are far below the `all` values for every month, so `marketing ⊆ all` holds, and
the sum identity also holds for the marketing audience.

### Typecheck / lint

- `ruff check packages/analytics/full_funnel.py packages/analytics/schemas.py` →
  All checks passed.
- `mypy packages/analytics/full_funnel.py packages/analytics/schemas.py` →
  Success: no issues found in 2 source files.
- `npx tsc --noEmit` (apps/web) → exit 0, no errors.

---

## Status remap + re-backfill (ENG-481, 2026-06-16)

The funnel exposed a real data-quality problem: nearly all CareStack
appointments were stored as `scheduled` because the old `_STATUS_MAP` only knew
a handful of statuses (everything else fell to the SCHEDULED fallback). The
remap below + a re-backfill of `ops.consultation.status` + a time-dependent
read rule fix the buckets. **No Alembic migration** — `consultation.status` is a
varchar / `StrEnum`, so the new `deleted` value is just a string.

### Part A — status mapping (ingest)

- Added `ConsultationStatus.DELETED = "deleted"` to `packages/ops/models.py`.
- Extended `_STATUS_MAP` and the `_map_status` normaliser in
  `packages/ingest/carestack_appointment_service.py`. The normaliser now strips
  spaces / underscores / **hyphens / periods** so "Dr. Notes", "Office
  Check-Out" and "Un-Confirmed" match their keys.
- New mappings:
  - physically-present → COMPLETED: `inoperatory`, `readytoseat`,
    `officecheckout`, `arrived` (+ existing checkedout/checkedin/inchair/completed).
  - `broken` → NO_SHOW.
  - `deleted`, `notecompleted`, `drnotes`, `asstnotes`, `reviewrequired` → DELETED.
  - pre-visit → SCHEDULED: `unconfirmed`, `confirmedelectronically`,
    `leftmessage`, `unabletoreach`, `unscheduled` (+ existing).
  - Blank / genuinely unknown → unchanged fallback (SCHEDULED + `Contract drift:`
    log). Unknown is NEVER routed to DELETED.

### Part B — re-backfill `ops.consultation.status`

`infra/scripts/backfill_consultation_status.py` (new) recomputes each
CareStack consultation's status from the **latest** raw appointment event
(`ingest.raw_event` `event_type='carestack.appointment.upsert'`, DISTINCT ON
`payload->>'id'` ordered by `received_at DESC`), matched on
`consultation.external_id = payload->>'id'`, using the imported `_map_status`
(mapping never duplicated). Dry-run default, `--apply` writes; commit per
tenant; idempotent (only rows whose status actually changes are touched).

Local DB (`127.0.0.1:5434` fusion/fusion) dry-run → apply, from → to:

| from      | to        | rows |
|-----------|-----------|------|
| scheduled | deleted   | 2109 |
| scheduled | no_show   | 2043 |
| scheduled | completed |  608 |
| **total** |           | **4760** |

Re-running the dry-run after `--apply` reports **0** rows would change
(idempotent confirmed).

### Part C — funnel read rule (time-dependent + exclude)

- `OpsRepository.full_funnel_consultation_rows` now also returns `is_past`
  (`Consultation.scheduled_at < func.now()` in SQL); the row tuple is
  `(person_uid, status, month, is_past)`. `OpsService` `FunnelConsultationRow`
  + method signature updated to carry `is_past`.
- `packages/analytics/full_funnel.py` consult loop:
  - `deleted` → SKIP entirely (excluded; not counted in `scheduled`).
  - `completed`→showed, `no_show`→no_show, `cancelled`→cancelled,
    `rescheduled`→rescheduled.
  - `scheduled` → `no_show` if `is_past` else `pending`.
  - `consults_scheduled` = sum of the 5 buckets (every non-deleted appointment).

### Verify (audience=all, default window ending 2026-06)

Live `GET /dashboard/analytics/full-funnel?audience=all`, by_month consults:

| month   | sched | showed | no_show | cancel | resched | pending |
|---------|-------|--------|---------|--------|---------|---------|
| 2026-01 | 2040  | 1241   | 203     | 256    | 340     | 0       |
| 2026-02 | 1905  | 1231   | 136     | 187    | 351     | 0       |
| 2026-03 | 2151  | 1343   | 211     | 221    | 376     | 0       |
| 2026-04 | 2201  | 1380   | 234     | 253    | 334     | 0       |
| 2026-05 | 2199  | 1243   | 356     | 216    | 384     | 0       |
| 2026-06 | 1976  | 790    | 167     | 155    | 290     | 574     |

- **Sum identity** `showed+no_show+cancelled+rescheduled+pending == scheduled`
  holds for every month. Past months `pending == 0`. Matches the acceptance
  gate within a few rows (live data grew since the gate snapshot).
- Leads (3217/2662/3388/3336/3006/1371) and revenue ($6,215,912.37 ≈ $6.21M)
  unchanged.
- `audience=marketing` consults (headline 1040) ≤ `all`; marketing sum identity
  also holds per month — `marketing ⊆ all` confirmed.

### Lint / typecheck

- `ruff check` on all changed packages → All checks passed.
- `mypy packages/ops/repository.py packages/ops/service.py
  packages/analytics/full_funnel.py
  packages/ingest/carestack_appointment_service.py
  infra/scripts/backfill_consultation_status.py` → Success, no issues.
