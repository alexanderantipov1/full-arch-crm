# Re-merge sweep + Possible-duplicates UI — design

Status: proposed (2026-05-28). Owner: TBD. Linear: TBD.

## Problem

Cross-provider identity merge today runs **only at ingest time** via
`IdentityService.resolve_or_create_from_hint`. When a SF Lead arrives with
only `phone+name` and a CareStack Patient already exists with only
`email+name`, the tier rules (`email_phone_name 0.99`,
`phone_name 0.95`, `email_name 0.92`) cannot fire because the two sides
share no identifier. Result: two separate Persons for the same human.

Concrete case observed 2026-05-28:

- SF Lead `00QVw00000ZlthdMAB` — `Lyubov Anatskaya`, phone `9165059354`,
  no email.
- CS Patient `2179041` — `Liubov Anatskaya` (note the `i` vs `y`), email
  `galanotdali@gmail.com`, no phone.
- Local DB: two persons (`4b7de961…` from CS, `bc470d73…` from SF).
- Prod DB: one person (`507ef884…`) because the CS pull on prod landed
  earlier when payload happened to carry both an email and a phone, so
  the SF pull later matched on `phone_name`.

The bug is the absence of a **second look** after data enriches. Once two
parallel persons exist, ingest never re-evaluates the pair, even when a
later pull adds the missing identifier.

## Decision

User picked: **periodic batch sweep, no new match rules in v1**, plus a
read+act UI surface on the person detail page. Full one-time backfill
sweep on first deploy, then incremental.

Rationale: keep the conservative auto-merge policy (avoiding wrong merges
matters more than avoiding duplicates per `packages/identity/CLAUDE.md`),
but cover the time-of-arrival blind spot. Fuzzy name / DOB / location
signals stay out of v1 to keep the false-merge surface flat.

## Architecture

```
┌─ Cloud Scheduler (hourly) ──────────────────────────┐
│                                                     │
│   fusion-job-remerge-sweep (Cloud Run Job)          │
│      └─ apps.worker.jobs.remerge_sweep              │
│              └─ IdentityService.sweep_for_merges()  │
│                     ├─ existing tier rules          │
│                     ├─ writes/updates MatchCandidate│
│                     └─ auto-merges high-conf pairs  │
│                                                     │
└─────────────────────────────────────────────────────┘
                       │
                       ▼ (writes)
              identity.match_candidate
                       │
                       ▼ (reads)
┌─ fusion-api routes ─────────────────────────────────┐
│   GET    /persons/{uid}/possible-duplicates         │
│   POST   /persons/{uid}/merge-candidates/{id}/accept│
│   POST   /persons/{uid}/merge-candidates/{id}/reject│
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─ Staff UI: /persons/[uid] ──────────────────────────┐
│   <PossibleDuplicates>                              │
│      ├─ list of open MatchCandidate rows            │
│      └─ Merge / Not-a-duplicate buttons             │
└─────────────────────────────────────────────────────┘
```

## Components

### 1. `IdentityService.sweep_for_merges(tenant_id, *, scope)`

New public method on `IdentityService`. Signature:

```python
class SweepScope(StrEnum):
    INCREMENTAL = "incremental"   # default: persons updated in last 2h
    FULL = "full"                  # backfill + monthly maintenance

@dataclass
class SweepSummary:
    persons_scanned: int
    pairs_evaluated: int
    auto_merged: int
    open_candidates_created: int
    skipped_already_decided: int
```

Algorithm per person:

1. Load identifiers of person `P`.
2. For each identifier `(kind, value)`, find other persons in the same
   tenant carrying the same `(kind, value)` (cheap index lookup).
3. For each candidate pair `(P, C)`:
   - Skip if `MatchCandidate(tenant, person_pair_key)` exists in
     `{accepted, auto_accepted, rejected}` — already decided.
   - Build a `MatchHintIn`-shaped struct from `C`'s identifiers + name.
   - Reuse the existing tier evaluator (`_evaluate_match_policy`) to
     score the pair.
   - High confidence (≥ `0.92`): write
     `MatchCandidate(auto_accepted)` and call `record_merge` so the
     downstream merge chain is updated. Emit
     `interaction.event(kind='person_merged', source_provider='system')`.
   - Weak / ambiguous: write/update `MatchCandidate(open)` with
     `conflicts` evidence (e.g. `["name_compatible_diff_spelling"]`).
4. Return `SweepSummary`.

The function is tenant-scoped, idempotent (re-runs no-op on already-
decided pairs), and chunkable (yields after every N persons so cron
ticks can checkpoint).

### 2. `apps/worker/jobs/remerge_sweep.py`

Cloud Run Job entrypoint. Reads `REMERGE_SCOPE` env (`incremental` /
`full`). Calls `IdentityService.sweep_for_merges` for every tenant.
Logs `remerge_sweep.tick` with `SweepSummary` payload.

Provisioned alongside the other `fusion-job-*` cron jobs:

- `fusion-job-remerge-sweep` — schedule `0 * * * *` (hourly),
  `REMERGE_SCOPE=incremental`.
- One-time invocation with `REMERGE_SCOPE=full` for the backfill, run
  via `gcloud run jobs execute --update-env-vars=REMERGE_SCOPE=full`.

Wired into `.github/workflows/deploy-prod.yml` `update-worker-jobs`
step so future deploys retarget it like the other ingest jobs.

### 3. API surface (`apps/api/routers/identity.py` or `persons.py`)

```
GET  /persons/{uid}/possible-duplicates
       → list of {candidate_id, other_person_uid, other_display_name,
                  source_systems: ["salesforce","carestack"],
                  match_rule, confidence, conflicts, created_at}

POST /persons/{uid}/merge-candidates/{candidate_id}/accept
       → IdentityService.accept_candidate(candidate_id, principal)
         which:
           - finds the candidate, validates `status == 'open'`
           - decides survivor by deterministic rule:
             older `created_at` wins, ties broken by lexicographically
             smaller UUID (stable, predictable)
           - calls record_merge(surviving, merged, reason='cross_provider_match')
           - sets MatchCandidate.status='accepted',
             accepted_person_uid=<survivor>
           - emits interaction.event(person_merged) on the survivor

POST /persons/{uid}/merge-candidates/{candidate_id}/reject
       → IdentityService.reject_candidate(candidate_id, principal)
         sets status='rejected'; sweep will not propose this pair again.
```

All three behind `get_principal_with_tenant`. Read endpoint uses the
existing `OpsService.snapshot` style allowlist — no PHI, no raw payloads.

### 4. Frontend (`apps/web/app/(staff)/persons/[uid]/page.tsx`)

New section `<PossibleDuplicates personUid={uid} />`:

- Hidden when the list is empty.
- Each row shows: other person's display name, SF / CS badge chips for
  source links, a one-line "why we think this matches" derived from
  `match_rule` (e.g. "Same phone and name") plus a small "View
  candidate" link to the other person card.
- Two actions: **Merge** (calls accept) and **Not a duplicate** (calls
  reject). Optimistic update via TanStack Query — row disappears, then
  rolls back on error.
- New Zod schema `PossibleDuplicatesSchema` in
  `apps/web/lib/api/schemas/person.ts`; hook
  `usePossibleDuplicates(uid)` in `useIdentity.ts` (new file) or
  `usePersons.ts`.

## Data flow

```
hourly Cloud Scheduler
   │
   ▼
fusion-job-remerge-sweep starts
   │
   ▼
IdentityService.sweep_for_merges(scope=incremental)
   │   ├─ enumerate persons updated since last_sweep_at - 2h
   │   ├─ for each: enumerate identifiers
   │   ├─ for each (kind,value): find other persons sharing it
   │   ├─ for each pair: score via existing tier rules
   │   ├─ high → record_merge + MatchCandidate(auto_accepted)
   │   └─ weak → MatchCandidate(open)
   ▼
job logs SweepSummary, container exits 0

  ── separately, in a staff session: ──

staff opens /persons/{uid}
   │
   ▼
useSession → useCurrentPerson → usePossibleDuplicates
   │
   ▼  GET /persons/{uid}/possible-duplicates
       returns open candidates
   │
   ▼
<PossibleDuplicates> renders the list
   │
   staff clicks Merge:
   │
   ▼  POST /persons/{uid}/merge-candidates/{candidate_id}/accept
       record_merge + MatchCandidate.status='accepted'
   │
   ▼
TanStack invalidates ["person", uid] + ["person", uid, "duplicates"]
   row disappears; person card refreshes with merged source links
```

## Idempotency, safety, audit

- **No reverse merges.** `merge_event` stays append-only. If a wrong
  merge happens (operator pushes Merge by mistake), a *new* merge_event
  records the corrective merge — never an UPDATE.
- **Already-decided pairs are skipped.** The sweep checks
  `MatchCandidate(status IN ('auto_accepted','accepted','rejected'))`
  via the existing `uq_match_candidate_person_pair_open` index
  semantics before writing.
- **Tier rules are reused, not redefined.** No new confidence values,
  no new identifier kinds. Risk surface = existing surface.
- **PHI hygiene.** `MatchCandidate.evidence/conflicts` already
  documented as normalised signals only (no clinical text, no raw
  payloads). The API response and UI mirror that.
- **Tenant scope.** Every read+write threads `tenant_id` via the
  existing repo helpers; cross-tenant matches are impossible by query.
- **Audit log.** `accept` / `reject` write to `audit.access_log` via
  the existing audit decorator on `IdentityService` (already used by
  `record_merge`). Actor is the human staff principal or
  `system:remerge_sweep` for auto-merges.

## Error handling

- Sweep partial failures (one bad person) are caught per-person and
  logged as `remerge_sweep.person_error`; the sweep continues. The
  summary `SweepSummary.persons_errored` exposes the count.
- Cloud Run Job exit code: non-zero only on catastrophic failures
  (DB down, no tenants). Per-pair errors do not fail the job.
- API endpoints raise `PlatformError` subclasses
  (`MatchCandidateNotFoundError`, `MatchCandidateAlreadyDecidedError`,
  `NotFoundError` for unknown person). Middleware translates to the
  standard `{error: {code, message, details}}` envelope.
- Frontend: error toast on accept/reject failure plus query rollback.

## Testing

### Unit

- `IdentityService.sweep_for_merges`:
  - happy path: pair created → auto-merge written + interaction event.
  - already-decided pair: no-op, counter increments
    `skipped_already_decided`.
  - weak match: `MatchCandidate(open)`, no `record_merge`.
  - per-person exception: logged, sweep continues, summary counts.
- `accept_candidate`:
  - survivor selection deterministic.
  - status mutation + audit row.
  - already-accepted: raises `MatchCandidateAlreadyDecidedError`.
- `reject_candidate`:
  - status='rejected', sweep skip works on re-run.

### Integration

- `tests/identity/test_remerge_sweep.py`:
  - real Postgres test DB, seeded with the Lyubov-style scenario
    (CS person + SF person sharing only `name`).
  - First sweep: writes `MatchCandidate(open)` (weak match) — verify
    row + tier `email_only_ambiguous`-style label.
  - Add a phone identifier to one person via a service call.
  - Second sweep: now `phone_name` rule fires → auto-merge happens.
  - Verify: one survivor person, two source links on it, one
    interaction.event emitted, `merge_event` row appended.

### Frontend

- Vitest component test for `<PossibleDuplicates>` — loading skeleton,
  empty hidden, populated rendering, accept-then-disappear, reject-
  then-disappear, error toast.

### Verification gate

Add the integration test to `make test`; the existing CI gate handles
the rest.

## Rollout

1. PR 1: backend (service method + tests + API endpoints). No worker
   yet. Allows manual verification via API.
2. PR 2: frontend section + Zod + hook + component test.
3. PR 3: worker job + Cloud Run Job provisioning + workflow
   `update-worker-jobs` extension.
4. One-time full backfill: `gcloud run jobs execute fusion-job-remerge-sweep
    --update-env-vars=REMERGE_SCOPE=full --wait`.
5. Flip the hourly Cloud Scheduler trigger on.

## Out of scope (v1, recorded for future ticket)

- Fuzzy name (Levenshtein / Jaro-Winkler) — would solve the
  Lyubov-vs-Liubov spelling drift today. Defer until v1 telemetry shows
  this class of duplicate dominates the unmerged residue.
- DOB or location as a match signal. DOB is PHI-adjacent and tenant
  policy isn't decided; location-as-proxy carries its own merge risk.
- Bulk "Merge all suggested" action in the UI.
- A separate `/duplicates` dashboard view across all persons (v1 stays
  per-person on the existing card).
