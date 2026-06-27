You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-267
(https://linear.app/fusion-dental-implants/issue/ENG-267). You run in an isolated
git worktree on your own branch. Implement → verify → write a report. Do NOT touch
`main`, do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once
verification is green; the Orchestrator integrates.

## Mission
Make the dashboard **Treatment & payments** track respect the **location** filter
(today it ignores location). Attach location to each payment/treatment event at
emit time and filter the aggregate by it. NO new schema — store location in the
event payload.

## Read first
- Root `CLAUDE.md`, `packages/CLAUDE.md`, `packages/interaction/CLAUDE.md`,
  `packages/ingest/CLAUDE.md`, `apps/api/CLAUDE.md`, and the mission spec at
  `.agents/orchestration/carestack-payment-location-v1/`.
- `packages/ingest/carestack_accounting_transaction_service.py` (emits payment
  events; this is where `amount`/`transaction_type` go into the safe payload).
- `packages/ingest/carestack_treatment_service.py` (emits treatment events).
- `packages/tenant/service.py` → `find_by_carestack_id(tenant_id, carestack_location_id)`
  and `packages/tenant/repository.py` → `find_by_carestack_id` (resolves CS
  locationId → our `tenant.location` via `external_ref->>'carestack_location_id'`).
- `packages/interaction/repository.py` → `get_treatment_payment_aggregate`
  (already extracts `Event.payload["amount"]`; add a location filter the same way).
- `apps/api/routers/dashboard.py` (the PM endpoint already has a `location_id`
  query param and calls `get_treatment_payment_aggregate`).

## Verified facts
- `interaction.event` has NO location column → store `location_id` in the event
  payload (string UUID), no migration.
- `accounting-transactions` and `treatment-procedures` payloads both carry
  `locationId` (integer FK).
- ingest may import tenant per `packages/CLAUDE.md` (ingest → tenant ✓) — use the
  service, not the repository.

## Tasks

### 1. Emit location on events
- In both ingest services, after resolving the patient, read the CS `locationId`
  from the row, resolve it to our tenant.location UUID via
  `TenantService.find_by_carestack_id(tenant_id, location_id_int)`, and add
  `location_id` (str(uuid)) to the SAFE event payload. If `locationId` is absent
  or unmapped (resolver returns None / raises NotFound), omit `location_id` — the
  event still emits. Do not fail the whole row over a missing location.
- Location is non-PHI; it is safe in payload + dashboard response. Do NOT add any
  patient identifier or clinical field.

### 2. Aggregate filters by location
- `interaction.get_treatment_payment_aggregate` (service + repository) gains an
  optional `location_id: UUID | None = None`. When set, add a predicate
  `Event.payload["location_id"].astext == str(location_id)` to the existing
  window/provider-filtered query so all the counts/sums become location-scoped.

### 3. Dashboard wiring
- Pass the endpoint's existing `location_id` into `get_treatment_payment_aggregate`.
- Leave `outstanding_total` / `outstanding_patient_count` / `ar_risk_count` as-is
  (tenant-wide — `payment_summary` has no location). Add a small "tenant-wide"
  hint/label on those in the widget so the UI does not imply they are
  location-scoped. (Reuse the InfoHint helper already in
  `apps/web/app/(staff)/project-manager/page.tsx`.)

## Hard constraints
- READ-ONLY CareStack. No new DB schema/migration — location goes in the event
  payload. If you become convinced a real `interaction.event.location_id` column
  is required, STOP and write `Needs decision:` in the report (that is a
  migration → structural, out of this slice).
- No PHI in events/logs/dashboard responses. Cross-domain imports per
  `packages/CLAUDE.md` (ingest → tenant via service). `except Exception` only.
  English only.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` all green.
2. Commit to your worktree branch only (not main) once green.
3. Write `.agents/orchestration/carestack-payment-location-v1/reports/ENG-267-worker-report.md`
   per the worker-report contract (changed files, where location is resolved,
   unmapped-location behaviour, tests, verification status, risks, do-not-merge).
4. If blocked or you hit the migration question, write `Needs decision:` and stop.
