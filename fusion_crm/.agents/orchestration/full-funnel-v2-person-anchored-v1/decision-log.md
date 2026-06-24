# Decision Log — Full Funnel v2

## 2026-06-16 — Mission accepted (Orchestrator)

**Handoff:** User (operator) → Orchestrator. Mission: re-anchor the Full
Funnel on `identity.person`. Origin: live data investigation of
`/analytics/funnel` with the operator, confirming the lead-anchored funnel
only sees the Salesforce intersection.

Evidence gathered (local DB, read-only):
- Consultations: 92,495 CareStack vs 26 Salesforce.
- 25,478 / 27,452 consultation-persons have no SF lead.
- $5.24M / $6.20M collected belongs to non-lead persons.
- Opportunities: 13 total, `is_won` never true → closed_won always 0.
- Linked persons (SF lead + CareStack patient): 2,222; phone-format
  under-merge ~2,117 more (ENG-463), email merge clean.

**Decisions:**
1. Closure = **money received** (`interaction.event` payments), NOT SF
   opportunity `is_won`. Confirmed by operator.
2. Anchor = `identity.person` universe (`ops.lead` ∪
   `identity.source_link(carestack/patient)`) — same anchor as
   `project-manager/leads`. No new tables.
3. Show / No-show are two distinct CareStack-status numbers
   (`completed` / `no_show`), not the old scheduled-vs-completed buckets.
4. Single Marketing/All toggle via the existing channel resolver; do not
   fork `classifyLeadSource`.
5. Per-stage time windows (each stage on its own timestamp).

**Accepted-incomplete (operator):** phone E.164 merge (ENG-463), CareStack
surgery-stage ingest, opportunity→channel attribution (ENG-475) — out of
scope. "We will merge the data ourselves; the important thing is the logic."

**Linear:** ENG-480 (epic) → ENG-481, ENG-482, ENG-483 created.

**Handoff:** Orchestrator → Worker (ENG-481), claude-code, isolated worktree.
Constraint: no commit/push without explicit user approval.

## 2026-06-16 — Bulk-import base discovery + CS-direct dating fix (operator)

Investigating an apparent 56,782-lead spike in 2026-05 (operator flagged it as
impossible), found the cause: ALL CareStack patients were pulled in one batch in
2026-05, and CareStack-direct persons were dated by `source_link.first_seen_at`
(= our pull date). The CareStack patient object exposes NO creation date.

Evidence (local, read-only):
- 52,510 CareStack-direct persons; 26,996 have ZERO activity (no consult, no
  event, no opportunity). CareStack patient object has no createdOn/registration.
- These are NOT in Salesforce (4 of 52,510 overlap) → loaded directly into
  CareStack, not via SF. Operator: a purchased database from another clinic.
- Separately: ~45k SF leads carry `sf_created_at` = 2025-10 (an SF-side bulk
  load); left as-is (SF CreatedDate is legitimate, and it is outside the window).

Decisions (operator):
1. **Provenance marker** (persisted): tag the zero-activity CareStack-direct
   cohort in `identity.source_link.meta` with
   `{"load_origin":"bulk_import","batch":"carestack_2026_05","no_activity":true}`.
   Implemented as idempotent backfill `infra/scripts/backfill_bulk_import_marker.py`;
   applied to LOCAL DB (27,232 rows). Prod backfill pending (separate step).
2. **Funnel date rule** (read-model): a CareStack-direct person's LEADS-stage
   date = COALESCE(earliest consultation.scheduled_at, earliest event.occurred_at,
   2025-01-01 sentinel). Zero-activity → 2025-01-01 → outside the default window.
   SF-lead persons unchanged. Marker and date rule are independent (a person who
   later becomes active keeps the marker but gets a real date).

Result (audience=all, window 2026-01..06): monthly leads 3217/2662/3388/3336/
3006/1355 (was …/56782/…); headline leads 68,515 → 16,964. marketing ⊆ all holds.
Consults/show/no-show/revenue unchanged.

Open follow-up: SF 2025-10 bulk (~45k) — decide later whether to treat similarly.
Prod marker backfill not yet run.

## 2026-06-16 — CareStack status remap + conversions (operator)

Operator flagged "Pending" appearing on past months. Root cause: `_STATUS_MAP`
only knew a few statuses; real CareStack statuses (Broken, In Operatory, Ready
to Seat, Office Check-Out, Arrived, Deleted, note/admin, …) fell through to
SCHEDULED. Investigated "Deleted" specifically: soft-deleted slots (22% deleted
<1min = data-entry errors, rest removed later), no attendance signal, 72% of
those persons attended other visits → a deleted appt is not a real/attended
appointment.

Decisions (operator-approved):
1. Status → bucket: present-statuses (In Operatory/Ready to Seat/Office
   Check-Out/Arrived/Checked Out)→Showed; Broken + explicit No-Show + any
   PAST appt stuck in a pre-visit status → No-show; Cancelled→Cancelled;
   Rescheduled→own column (NOT folded to no-show — 82% show at the new slot);
   Deleted + note/admin (Note Completed/Dr. Notes/Asst Notes/Review Required)
   → EXCLUDED from the funnel. Future pre-visit → Pending.
2. "Past + unresolved → no-show" is time-dependent → lives in the funnel read
   layer (ops returns is_past), not the static ingest enum.
3. Two conversions added (frontend, derived): Show rate = showed/scheduled;
   Show→money = $/show (revenue/showed) + paid rate (closed_won/showed).

Implementation: added ConsultationStatus.DELETED (varchar, no migration),
extended _STATUS_MAP, idempotent re-backfill
`infra/scripts/backfill_consultation_status.py` (LOCAL applied: 4,760 rows
scheduled→{deleted 2109, no_show 2043, completed 608}). Funnel read rule +
conversion display. Sum identity holds every month; leads/revenue unchanged.
Prod re-backfill pending (separate step). Still uncommitted on branch.
