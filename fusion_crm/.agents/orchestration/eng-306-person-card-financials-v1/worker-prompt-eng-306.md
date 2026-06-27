You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-306**
(https://linear.app/fusion-dental-implants/issue/ENG-306/person-card-financial-summary-payments-badge-from-authoritative).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (frontend-first, with a small backend extension)

Surface the per-patient authoritative balance landed by ENG-305 in two places:

1. **Person/patient detail card** (`apps/web/app/(staff)/persons/[uid]/page.tsx`)
   — replace the "Treatment/payments" stub Card (currently lines ~420-435,
   labelled "Read model pending") with a real financial summary block:
   **Billed**, **Adjustments**, **Paid**, **Balance** plus a snapshot timestamp.
2. **Payments page rows** (`apps/web/app/(staff)/project-manager/payments/`)
   — compact balance pill next to each row's patient name.

Empty state: each number renders `"—"` when no snapshot is available — never
`"$0"` (we must not imply we know the balance is zero).

Backend: the existing tenant-wide aggregate
`LatestPaymentSummaryBalancesOut` exposes only `balance_due_*` (no `applied_*`,
no Billed/Adjustments). You will extend the backend to expose a per-patient
shape with all four numbers.

## Pre-flight facts (already audited — do NOT re-investigate)

### Person detail page (the existing patterns to mirror)

- **File:** `apps/web/app/(staff)/persons/[uid]/page.tsx` (client component
  with `useParams`).
- **Data hook:** `usePersonDetail(uid)` fetches `PersonDetailSchema`. The
  Zod schema is at `apps/web/lib/api/schemas/person.ts:238-266` and includes
  `source_links` array.
- **CareStack patient_id access** (lines 73-78):
  ```typescript
  const carestackPatientLink = useMemo(() => {
    if (!data) return null;
    return data.source_links.find(
      (sl) => sl.provider === "carestack" && sl.entity === "patient",
    ) ?? null;
  }, [data]);
  ```
  `carestackPatientLink?.external_id` is the patient_id string (e.g. "PT-9981").
- **Stub slot:** the "Treatment/payments" Card at lines ~420-435 is explicitly
  marked "Read model pending" — **this is where the new FinancialSummary
  lands**. Replace it; do not add a new card alongside.
- **Card pattern:** import `Card, CardHeader, CardTitle, CardDescription,
  CardContent` from `@/components/ui/card`. Color-coded borders + bg:
  emerald-toned for CareStack-sourced ('border-emerald-400/30 bg-emerald-50/40'),
  but pick a fresh tone that fits the financial domain (amber/gold or similar)
  if you want the block to be visually distinct from the existing CareStack
  Card next to it. Match existing typography: `text-base` titles with
  icon + `flex gap-2`; descriptions in `CardDescription`;
  `space-y-3 text-sm` content.
- **FieldLine component** at lines 703-717 already renders `"—"` for
  null/undefined/empty values — REUSE IT for each number; do not duplicate
  the empty-state logic.
- **Currency formatting:** find the existing helper used by the Outstanding
  / Collected displays (likely in `apps/web/lib/utils.ts` or
  `apps/web/lib/format.ts` — grep for `formatCurrency` or USD usage). Reuse;
  do NOT introduce a new formatter.

### Existing payment-summary aggregate (to extend, not duplicate)

- **DTO:** `LatestPaymentSummaryBalancesOut` at `packages/ingest/schemas.py:217-237`.
  Today exposes: `balance_due_patient`, `balance_due_insurance`,
  `outstanding_total`, `patient_count`, `ar_risk_count`, `ar_risk_threshold`.
- **Repository:** `sum_latest_payment_summary_balances(tenant_id, *,
  ar_risk_threshold)` at `packages/ingest/repository.py:215-285`. Already
  dedupes per CareStack patient_id (external_id) + takes the latest
  `received_at`. Tenant-wide.
- **Service:** `latest_payment_summary_balances(tenant_id)` at
  `packages/ingest/service.py:369-397`. Tenant-wide only.
- **API route:** `apps/api/routers/dashboard.py:431-432` (inside `/dashboard/pm`).
- **Frontend hook:** `useDashboardPm()` at
  `apps/web/lib/api/hooks/useDashboard.ts:39-51` — fetches `/dashboard/pm`
  and parses via `DashboardPmSchema`.
- **Frontend Zod:** `DashboardTreatmentPaymentsSchema` at
  `apps/web/lib/api/schemas/dashboard.ts:97-115`.
- **Raw event payload** (the source of truth): `ingest.raw_event` rows of
  type `carestack.payment_summary.snapshot` carry the full CareStack
  response — every snapshot has `appliedPatientPayment`, `appliedInsPayments`,
  `balanceDuePatient`, `balanceDueInsurance`. Today's aggregate only exposes
  `balance_due_*`.

## Tasks (TDD — write tests first per piece)

### 1. Backend: extend the DTO + add a per-patient repository/service method

In `packages/ingest/schemas.py`:

- Either add `applied_patient_payment: float = 0.0` and
  `applied_ins_payments: float = 0.0` to `LatestPaymentSummaryBalancesOut`
  (additive — won't break the existing dashboard caller), OR introduce a
  **new** `PersonPaymentFinancialSummaryOut` DTO with all four core numbers:
  `billed`, `adjustments`, `paid`, `balance`, plus `snapshot_received_at:
  datetime | None`, plus `patient_count: int` and the CareStack patient_ids
  it covered (`carestack_patient_ids: list[str]`).
  Recommendation: **new DTO** — keeps the existing aggregate clean and
  matches the four-number contract of the UI block exactly.

In `packages/ingest/repository.py` (next to
`sum_latest_payment_summary_balances`):

- Add `sum_person_financial_summary(tenant_id, person_uid) -> dict[str, object]`
  that:
  1. Resolves the CareStack patient_id(s) for the given person_uid via
     `identity.source_link` (`source_system='carestack'`,
     `source_kind='patient'`, `person_uid=...`).
  2. For each patient_id, picks the **latest** `ingest.raw_event` of type
     `carestack.payment_summary.snapshot` (`external_id=patient_id`),
     extracts `appliedPatientPayment + appliedInsPayments` (= Paid) and
     `balanceDuePatient + balanceDueInsurance` (= Balance). Sum across
     patient_ids (rare but possible when one person has multiple CS links).
  3. For Billed: Σ debit on `carestack.accounting_transaction.*` raw events
     for these patient_ids where `payload->>'transactionCode' = 'PROCEDURECOMPLETED'`,
     **deduped by `external_id`** (DISTINCT ON `external_id`, latest
     `received_at`) — the raw feed has ~15 % duplicates by design.
   4. For Adjustments: same shape as Billed, but `transactionCode` in
      (`'PATIENTADJUSTMENT'`, `'FEEUPDATION'`). Treat as net (debit − credit
      using existing transactionType field).
   5. Returns the dict with the four floats + `snapshot_received_at` (latest
      across patient_ids) + `carestack_patient_ids` list + `patient_count`.
- If the patient has zero CareStack patient_ids OR no snapshot raw_event:
  return all zeros + `snapshot_received_at=None` + `carestack_patient_ids=[]`
  + `patient_count=0`. The UI uses `snapshot_received_at` to decide whether
  to show "—" everywhere.

In `packages/ingest/service.py`:

- Add `person_payment_financial_summary(tenant_id, person_uid) ->
  PersonPaymentFinancialSummaryOut` next to `latest_payment_summary_balances`.
  Convert dict floats to the DTO.

### 2. Backend: API route

In `apps/api/routers/persons.py` (or wherever the existing `/persons/{uid}`
detail route lives — discover with `grep -RIn "persons.*uid" apps/api/routers/`):

- Either embed the new `PersonPaymentFinancialSummaryOut` into the existing
  `PersonDetailOut` response (cleanest — one round-trip from the frontend),
  OR add a sibling route `GET /persons/{uid}/financial-summary`. **Pick
  whichever the existing patterns favour.** If the existing `PersonDetailOut`
  already aggregates multiple data sources server-side, follow that pattern
  (embed). If most enrichments are sibling routes, add a sibling.
- Add the resolver call in the route handler; pass through the worker
  context (tenant_id, person_uid).

Tests in `tests/api/`:
- Person with snapshot → DTO has correct four numbers + timestamp + patient_ids.
- Person without snapshot → DTO has zeros + `snapshot_received_at=None` +
  empty patient_ids.
- Person with multiple CareStack links → sums across all of them.
- No PHI in serialization or logs.

### 3. Frontend: schema + hook

In `apps/web/lib/api/schemas/person.ts` (or wherever the new DTO is consumed):

- Add a Zod `PersonFinancialSummarySchema` mirroring the backend DTO
  (`billed: number`, `adjustments: number`, `paid: number`, `balance: number`,
  `snapshot_received_at: z.string().datetime().nullable()`,
  `carestack_patient_ids: z.array(z.string())`, `patient_count: z.number()`).
  Strict TS.

- Extend `PersonDetailSchema` to include `financial_summary:
  PersonFinancialSummarySchema | null` (or `.optional()` — match existing
  optionality convention).

- If a sibling route was chosen on the backend: add a `usePersonFinancialSummary(uid)`
  hook next to `usePersonDetail`; both fetched in parallel from the page.

### 4. Frontend: Person card UI

In `apps/web/app/(staff)/persons/[uid]/page.tsx`:

- Replace the stub Treatment/payments Card at lines ~420-435 with a
  `FinancialSummaryCard` (define inline or extract to
  `apps/web/components/persons/FinancialSummaryCard.tsx`).
- Render four `FieldLine` rows: Billed / Adjustments / Paid / Balance. Use
  the existing currency formatter on each number.
- Below the four rows: a small muted line — `Last snapshot:
  <relativeTime(snapshot_received_at)>` when present, else `No balance
  snapshot yet`.
- When `financial_summary === null` OR `snapshot_received_at === null`:
  pass `null` to each `FieldLine` so it auto-renders `"—"` (the existing
  component handles this).
- Match the existing Card visual conventions (color-coded border + bg, icon
  in title, `space-y-3 text-sm` content).

### 5. Frontend: Payments page badge

In `apps/web/app/(staff)/project-manager/payments/page.tsx`:

- Read where each row is rendered (use grep to locate the JSX for the
  patient name column).
- Add a compact `Badge` (shadcn `Badge` variant) next to the patient name
  showing the patient's balance from the same authoritative source.
- The hook powering the Payments page (`useDashboardPmPayments` — confirmed
  by pre-flight) returns rows. Either:
  - Add per-row balance to the existing row payload at the backend, OR
  - Fetch a batch-balance map keyed by patient_id once per page, render
    per-row from the map.
  **Pick whichever has lower N+1 risk.** Document the choice in the report.
- Empty state: render `"—"` inside the pill when no snapshot.
- Add a test that pagination is not regressed (existing tests must stay
  green).

### 6. Tests

Frontend (`apps/web/tests/...` or page-adjacent `__tests__/`):
- `FinancialSummaryCard` renders the four numbers with currency formatting
  when snapshot is present.
- `FinancialSummaryCard` renders four `"—"` + "No balance snapshot yet"
  when `financial_summary === null` OR `snapshot_received_at === null`.
- Person detail page integration: with mocked MSW fixture including a
  financial_summary block, the four numbers appear; with the snapshot
  field null, "—" appears.
- Payments row badge: renders with balance; renders `"—"` when patient has
  no snapshot; pagination tests still pass.

Backend tests covered in Task 1-2 above.

MSW fixtures (`apps/web/lib/msw/fixtures/persons.ts`): add a
`financial_summary` block to the Alice fixture (with realistic numbers,
non-PHI), and a sibling fixture without a snapshot so the empty-state path
is exercised in dev as well.

## Hard constraints

- **NO PHI** in logs, fixtures, or DTOs — counts, patient_id, monetary
  amounts only.
- **Currency formatting** uses an existing helper — DO NOT introduce a
  new one. Grep first: `grep -RIn "formatCurrency\|toLocaleString.*USD"
  apps/web/lib/`.
- **Strict TS.** No `any`. No `as` casts unless absolutely necessary.
- **Do NOT touch `apps/web/lib/msw/handlers.ts`** — unrelated WIP from
  another stream (this rule was in the ENG-305 ticket and still applies).
- **Do NOT delete or alter** `LatestPaymentSummaryBalancesOut`'s existing
  fields — additive only (or build a brand-new DTO).
- **No new migrations** — the data path exists (raw_event rows from
  ENG-305).
- **Empty-state must be `"—"`** in all places, never `"$0"`.
- **`except Exception`, never `except BaseException`.** Repo convention.
- **English in repo files** (RU only in user-facing UI strings — none in
  this ticket).
- **TDD:** write tests first for each task.
- **One commit at the end on the worktree branch.** Commit message format:
  `ENG-306: person-card financial summary + Payments badge`.

## Definition of done

1. `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` clean.
2. If backend touched (Task 1-2): `make lint && mypy . && make test &&
   cd packages/db && alembic check` clean.
3. Commit to worktree branch ONLY (NOT main).
4. Write `.agents/orchestration/current/reports/ENG-306-worker-report.md`
   covering: touched files, what changed per piece, tests added + results,
   verification commands run + their outcome, risks identified, blockers /
   questions, suggested next task, DO-NOT-MERGE conditions.
5. Visual verification: spin up `cd apps/web && npm run dev`, open the
   person detail page in the MSW dev mode, confirm the FinancialSummary
   block renders for the fixture with `financial_summary` AND the empty
   state for the fixture without. Same on the Payments page (badge present
   on rows with snapshot, `"—"` on rows without). Include a sentence in
   the report. If the dev environment will not start, say so explicitly
   in the report — do not silently skip.
6. Do NOT trigger a real CareStack backfill — that is ENG-307 plus a
   SEPARATE operator decision.

If you hit something the implementation map did not predict, STOP and
write `Blocked:` in the report rather than guess. The orchestrator
session is monitoring.
