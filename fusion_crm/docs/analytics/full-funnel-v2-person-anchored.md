# Full Funnel v2 — Person-Anchored Funnel (ENG-480)

> Design doc for re-anchoring the Full Funnel report from the Salesforce
> lead table onto the global `identity.person`, computing each stage from
> its **system of truth** (Salesforce for marketing leads, CareStack for
> consultations / show / no-show / money), and adding a single
> **Marketing / All** audience toggle.
>
> Supersedes the lead-anchored parts of ENG-472. No new tables — this is a
> read-model change over data we already ingest and already merge.
>
> Children: ENG-481 (backend read model + API), ENG-482 (frontend),
> ENG-483 (verify on real data + integration tests).

---

## 1. Problem — what the current funnel actually measures

The shipped `/dashboard/analytics/full-funnel` endpoint (ENG-472) is a thin
composer over `OpsService.get_lead_source_tree()`, which is **anchored on
`ops.lead`** (the Salesforce lead table) and joins everything else to a
person *only if that person has an SF lead*. In a two-system clinic that is
structurally wrong.

Verified against local real data (2026-06-16):

| Signal | Finding |
|---|---|
| Consultations by system | **92,495 CareStack** vs **26 Salesforce** — CareStack is the truth |
| Consultation-persons without an SF lead | **25,478 of 27,452 (93%)** — CareStack-direct patients, invisible to the funnel |
| Collected money without an SF lead | **$5.24M of $6.20M (85%)** — invisible to the funnel revenue |
| Opportunities total | **13**, all `is_closed=false` / `is_won=false` (even stage "Surgery Completed") → `closed_won` always **0** |
| Scheduled vs Showed | computed as **disjoint status buckets** (`status='scheduled'` vs `status='completed'`); `no_show`/`cancelled` dropped → "showed > scheduled", leaky funnel |

So the report shows the **Salesforce intersection**, not the clinic.

The fix is *not* new infrastructure. The identity merge already exists and
is already used correctly by `project-manager/leads`, which anchors on
`identity.person` and unions SF leads + CareStack patients via `person_uid`.
The funnel simply needs to adopt the same person-anchored model.

---

## 2. The operator's funnel model

Truth is split across the two systems, stage by stage:

```
Lead (Salesforce, marketing)            ── source of truth: Salesforce
  │   (some leads are created directly in CareStack and never hit SF)
  ▼
Consultation scheduled (CareStack)      ── source of truth: CareStack
  ▼
Showed / No-show (CareStack)            ── source of truth: CareStack ONLY
  ▼
Closed won = money received (CareStack) ── source of truth: CareStack payments
  ▼
Revenue (CareStack)                     ── sum of that money
```

Salesforce opportunities are, at best, a hand-maintained duplicate of what
the CareStack schedule already shows; they are frequently skipped and are
not the source of truth for closure. **Closure is money in the door.**

A single **Marketing / All** toggle filters every stage:

- **Marketing** — persons whose lead came from advertising (channel resolves
  to google / facebook / …).
- **All** — every person, including CareStack-direct, referral and manual
  leads that have no ad source.

---

## 3. Stage → source-of-truth mapping (all from existing tables)

No new tables. Everything below already exists and is already populated.

| Stage | Definition | Source | Key |
|---|---|---|---|
| **Leads** | distinct persons (merged = one) with an SF lead **or** a CareStack patient link | `ops.lead` ∪ `identity.source_link(carestack/patient)` | distinct `person_uid` |
| **Consults scheduled** | total appointments put on the schedule (all statuses) | `ops.consultation` (CareStack truth) | **count of rows** (appointment-level) |
| **Showed** | appointments held | `ops.consultation` where `status='completed'` | count of rows |
| **No-show** | appointments the patient did not attend | `ops.consultation` where `status='no_show'` | count of rows |
| **Cancelled** | appointments cancelled | `ops.consultation` where `status='cancelled'` | count of rows |
| **Rescheduled** | appointments moved to a new slot | `ops.consultation` where `status='rescheduled'` | count of rows |
| **Pending** | appointments not yet held / future | `ops.consultation` where `status='scheduled'` **and** `scheduled_at >= now()` | count of rows |
| **Closed won (money)** | real closure = money received | `interaction.event` payment kinds, Net Collected > 0 | by `person_uid` |
| **Revenue** | sum of collected money | `interaction.event` (recorded − refunded − reversed) | by `person_uid` |

### 3.1 CareStack status → funnel bucket (ENG-481 status remap)

CareStack emits ~22 free-form appointment status strings. They are normalised
(lowercase, with spaces / underscores / hyphens / periods stripped) and mapped
to one canonical `ops.consultation.status`, then to a funnel bucket. The
canonical→bucket step is **time-dependent** for the `scheduled` status.

| Funnel bucket | Canonical status | Raw CareStack statuses (examples) |
|---|---|---|
| **Showed** | `completed` | Completed, Checked Out, Checked In, In Chair, In Operatory, Ready To Seat, Office Check-Out, Arrived (patient was physically present) |
| **No-show** | `no_show` | No Show, No-Show, **Broken** (a broken appointment is a no-show) |
| **Cancelled** | `cancelled` | Cancelled / Canceled |
| **Rescheduled** | `rescheduled` | Rescheduled |
| **Pending** *(if future)* / **No-show** *(if past)* | `scheduled` | Scheduled, Confirmed, Un-Confirmed, Confirmed Electronically, Left Message, Unable To Reach, Unscheduled |
| **Excluded** *(skipped entirely)* | `deleted` | Deleted; note/admin rows that were never a real appointment — Note Completed, Dr. Notes, Asst Notes, Review Required |

Rules:

- **Past unresolved → no-show.** A still-`scheduled` appointment whose
  `scheduled_at` has already passed (`scheduled_at < now()`, evaluated in SQL)
  counts as a **no-show** — the patient never showed and the slot is gone. Only
  a `scheduled` appointment in the future is **pending**. Hence past months
  always show `pending == 0`.
- **Deleted / notes → excluded.** `deleted` rows are dropped before any
  counting: they are NOT in `consults_scheduled` and contribute to no bucket.
  This covers both genuinely deleted appointments and note/admin "appointments"
  (Dr. Notes, Asst Notes, Note Completed, Review Required) that never put a real
  patient on the schedule.
- **Blank / genuinely unknown status** keeps the fallback (`scheduled` + a
  `Contract drift:` log) — unknown is NEVER routed to `deleted`.
- `consults_scheduled` = `showed + no_show + cancelled + rescheduled + pending`
  = every **non-deleted** appointment, so the sum identity holds per month.

Notes:

- **Person universe** = `SELECT person_uid FROM ops.lead` `UNION`
  `SELECT person_uid FROM identity.source_link WHERE source_system='carestack'
  AND source_kind='patient'`. This is exactly the anchor `project-manager/leads`
  already uses (SF leads + CareStack patient links resolved through identity).
- **Net Collected** = Σ`payment_recorded.amount` − Σ`payment_refunded` −
  Σ`payment_reversed` (exclude `payment_applied` allocation legs). Read it
  through `InteractionService` (e.g. `collected_by_person`) — **never** query
  `event.payload` JSON from the router.
- **The consultation stages are counted at the APPOINTMENT level (ENG-481,
  operator-approved 2026-06-16)** — one count per `ops.consultation` row, NOT
  distinct persons. All statuses are shown so they balance exactly:
  `consults_scheduled = showed + no_show + cancelled + rescheduled + pending`.
  `consults_scheduled` is the total **non-deleted** appointment rows in the
  month (every status summed). The canonical `ops.consultation.status` maps to
  exactly one counter (see §3.1 for the full status→bucket table):
  `completed → showed`, `no_show → no_show`, `cancelled → cancelled`,
  `rescheduled → rescheduled`, `scheduled → pending` if future else `no_show`,
  and `deleted → excluded` (skipped). Leads and closed-won/revenue stay
  **person-level / money** as before;
  only the consult stages moved from person-sets to appointment (row) counts.
  The audience filter (marketing / all) and per-channel attribution still apply
  per appointment via the booking person's channel, so `marketing ⊆ all` still
  holds per stage and month.

---

## 4. Marketing / All audience definition

- **Marketing** = the person has at least one `ops.lead` whose resolved
  channel is an ad source. Reuse the **single** existing resolver
  (`_explorer_channel_label` / `_channel_of_source`, `packages/ops`) which
  maps `last_touch_source` → `utm_source` → `hubspot_lead_source` →
  `lead_source` → `lead.source` to `google` / `facebook` / passthrough.
  Marketing = resolved channel ∈ {`google`, `facebook`, …ad channels}.
- **All** = the whole person universe (marketing + referral + direct +
  manual + CareStack-direct).
- **Invariant:** `marketing ⊆ all` for every stage and every month.

Do **not** fork the legacy `classifyLeadSource()`. If we later need more ad
channels (Dima, Implant Engine, paid-vs-organic), extend the one resolver so
every dashboard benefits (see `dashboards-mapping.md` §6).

`lead.source` is empty for ~62,782 of 62,865 rows — attribution lives in
`lead.extra` (`utm_source` 19,044, `last_touch_source` 11,630,
`hubspot_lead_source` 18,754), which is exactly what the resolver reads.

---

## 5. Time window — apply per stage on that stage's own timestamp

Because stages live in different systems, the reporting window must be
applied to **each stage on its own timestamp**, not folded onto the lead's
created-at (today's bug folds consultation/revenue onto the lead window):

| Stage | Window timestamp |
|---|---|
| Leads — SF-lead persons (SF-only and SF+CareStack linked) | lead provider created-at (`lead.extra.sf_created_at` ?? `lead.created_at`) |
| Leads — CareStack-direct persons (`carestack/patient` link AND **no** `ops.lead`, any time) | earliest real activity, all-time (see below) |
| Consults scheduled / showed / no-show | `consultation.scheduled_at` (the booking/appointment time) |
| Closed won / Revenue | `interaction.event.occurred_at` (payment time) |

Default window stays trailing-6-months with optional `start_date` /
`end_date`, matching the current endpoint. Monthly breakdown buckets each
stage by its own timestamp's `YYYY-MM`.

> A person can therefore contribute to different months at different stages
> (lead in March, consult in April, payment in May) — that is correct and
> is what makes the funnel honest about lag.

### 5.1 CareStack-direct leads dating (ENG-481 fix)

The CareStack patient object exposes **no creation date**, and every
CareStack patient was pulled in a single bulk batch in 2026-05. Dating
CareStack-direct persons by `source_link.first_seen_at` therefore clustered
~52k of them into 2026-05 — a fake spike of ~56k "leads" in one month. The
bulk pull is recorded as a provenance marker in `source_link.meta`
(`{"load_origin": "bulk_import", "batch": "carestack_2026_05",
"no_activity": …}`); `first_seen_at` is the load time, **not** a lead arrival
time, so it is meaningless for funnel timing.

Operator-approved rule: for the **leads** stage only, date each
CareStack-direct person — a `carestack/patient` source link **and no
`ops.lead` anywhere, any time** — by their earliest real activity, all-time:

```
funnel_entry = COALESCE(
    MIN(consultation.scheduled_at),   # ops.consultation
    MIN(interaction.event.occurred_at),  # interaction timeline
    TIMESTAMPTZ '2025-01-01'          # sentinel (UTC)
)
```

The person buckets into the month of `funnel_entry` and counts as a lead
**only if** `funnel_entry` falls inside the report window. Persons with zero
activity fall to the `2025-01-01` sentinel, which sits before the default
trailing-6-month window, so they correctly drop out — they are a bulk-loaded
patient base, not organic leads.

SF-lead persons (SF-only and SF+CareStack linked) are **unchanged**: they
keep the lead provider created-at logic above and never enter the
earliest-activity path. The "no `ops.lead`" exclusion is cross-domain, so it
is applied in the `packages/analytics` composition layer (subtract the set of
lead-bearing person_uids from the CareStack-direct universe), not inside
`identity`. Channel for CareStack-direct stays `other` (never marketing), so
they appear only under `audience=all` and `marketing ⊆ all` still holds. The
consults / showed / no-show / closed-won / revenue stages are untouched.

---

## 6. API contract

Extend the existing endpoint (thin composer; logic in services):

```
GET /dashboard/analytics/full-funnel
    ?audience=all|marketing      (default: all)
    &start_date=YYYY-MM-DD        (optional)
    &end_date=YYYY-MM-DD          (optional)
```

Response (additive to today's shape):

- **headline**: `leads`, `consults_scheduled`, `showed`, `no_show`,
  `closed_won` (money-based count of paying persons), `revenue`.
- **by_month[]**: per `YYYY-MM` — `spend` (marketing channels only, may be
  null), `leads`, `consults_scheduled`, `showed`, `no_show`, `closed_won`,
  `revenue`.
- **by_channel[]**: per month × {google, facebook, other} — `spend`
  (null for `other`), `leads`, `consults_scheduled`, `showed`, `no_show`,
  `revenue`. (`closed_won` stays month-level; opportunity→channel attribution
  is still deferred — see §8.)

Rendering rule unchanged: a metric with no connected source renders `—`
(null), never a fabricated `0`. Spend is null for the `other` channel and
for any month with no ingested ad spend.

Suggested composition layer: `AnalyticsService` (read-only) calling
`OpsService` + `IdentityService` + `InteractionService` + `MarketingService`,
per the `packages/CLAUDE.md` import matrix. New aggregation reads that don't
exist yet (person-universe counts, consultation status counts by person,
collected-by-person) belong on the owning domain's service/repository.

---

## 7. Architecture & invariant compliance

- **No new schema / tables.** Read model only.
- **Cross-domain crossings via services only.** The router/analytics layer
  must not query another domain's repository or `event.payload` directly.
- **No business logic in the route** — it stitches DTOs from services.
- **`ops` must not import `phi`** — unaffected; funnel touches no PHI schema.
- **Person identity** is the global anchor (`identity.person.id`), exactly as
  invariant #2 intends.

---

## 8. Out of scope / accepted-incomplete (operator confirmed 2026-06-16)

1. **Phone E.164 under-merge (ENG-463).** ~2,117 CareStack-direct persons
   match an SF lead by phone but sit on a different `person_uid` (email merge
   is clean — 0 gap). Until normalization lands, those people count as
   non-marketing in `all` and are absent from `marketing`. The funnel logic
   is correct regardless of merge completeness; the data merge is fixed
   separately. Operator: "we will merge the data ourselves; the important
   thing is that the logic is right."
2. **CareStack surgery/operation stage.** Surgeries appear today only as the
   13 SF opportunities; a real surgery stage from the CareStack schedule is a
   separate ingest epic. v2 stops at money-as-closure.
3. **Opportunity → channel attribution** for `closed_won` (kept month-level,
   per ENG-475).
4. **Center / TC / per-arch pricing** breakdown (legacy `classifyLeadSource`)
   stays deferred (`dashboards-mapping.md` §6).

---

## 9. Verification (ENG-483)

Reconcile v2 output against raw DB counts on real data, then lock with
integration tests on a real PostgreSQL test DB (no mocks):

- **Leads (all)** = distinct persons in `ops.lead` ∪
  `identity.source_link(carestack/patient)`.
- **Consults scheduled / showed / no-show (all)** match raw `ops.consultation`
  status counts by `person_uid` in window.
- **Revenue (all)** matches Net Collected from `interaction.event`
  (≈ $6.2M lifetime locally; windowed accordingly).
- **`marketing ⊆ all`** for every stage and month.
- **Closed won (money)** = count of payers with Net Collected > 0; non-zero.
- Spot-check that CareStack-direct persons (no lead) appear in `all` but not
  in `marketing`.
