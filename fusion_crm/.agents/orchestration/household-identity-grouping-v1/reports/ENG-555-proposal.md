# ENG-555 — Messenger alert on shared-contact reuse (Layer D) — PROPOSAL

> **Status:** proposal, propose-before-implement gate (new notification contract + routing).
> **Task class:** normal (medium risk). **Epic:** ENG-552. **Base:** includes ENG-341 (A, live).
> Draft-PR only. NO merge / NO deploy / NO infra edits.

## TL;DR

Add an **`identity.shared_contact_reuse`** notification event. A new **scan job**
(`apps/worker/jobs/shared_contact_reuse_scan.py`) reads the existing reuse
signal — an **OPEN `identity.match_candidate`** with `match_rule ∈
{phone_only_ambiguous, email_only_ambiguous}` — and emits one Messenger alert
per candidate via the existing ENG-437 notification runtime, routed per-location
to the **`leads`** channel. **No new model / no new migration**: the dedupe
ledger (`integrations.notification_emitted`) and the cutoff guard already exist
and are reused. The alert body carries **no PHI** (person uids + contact *kind*
only, never the phone/email value or name).

## 1. Signal source — DECISION: open `match_candidate` (ambiguous reuse rules)

**Confirmed.** The matcher already writes exactly the signal we need. On the
reuse path, `IdentityService.resolve_or_create_from_hint` → `_apply_open_ambiguous`
(`packages/identity/service.py:1422`) creates a **new** source-linked person and
opens a `MatchCandidate(status='open')` with:

- `match_rule = "phone_only_ambiguous"` or `"email_only_ambiguous"`
  (`service.py:494-497`),
- `source_person_uid` = the **incoming/new** person (`service.py:1466`),
- `candidate_person_uid` = the **existing** person already holding the contact
  (`service.py:1467`),
- `created_at` = when the reuse happened.

That row *is* "an incoming record shares a contact with an existing person."
It is the faithful proxy for the operator's "always inform that the phone
already exists" intent, with one deliberate carve-out:

- **Tier-1 auto-accept** (same phone + compatible name) merges into the **same**
  person (`status='auto_accepted'`) — no distinct person, no "capture a distinct
  contact" problem → **intentionally not alerted**.
- **Fallback brand-new** person → no existing owner shares the contact → not a
  reuse → no candidate, no alert (correct).
- **Tier-2 open ambiguous** → a *distinct* new person reused an existing shared
  contact → **alert** (this is the nudge target).

This matches the design doc §4 + §5.5 ("nudge staff to capture distinct contacts
per person"). We do **not** make `identity` import `integrations` — the matcher
keeps writing the ledger row; the worker job reads it and emits (ENG-498 scan-job
pattern, mirroring `consult_reminder_scan.py` + `consultation_reminders.py`).

## 2. No retro-blast — DECISION: cutoff-gated scan + dedupe ledger

Three independent guards keep the 1,144 pre-existing open candidates silent:

1. **Scan-level cutoff (primary).** The scan only selects candidates with
   `created_at >= Settings.notifications_cutoff_at`. **If `NOTIFICATIONS_CUTOFF_AT`
   is unset, the scan is a no-op** (returns early, logs a count of 0) — we refuse
   to scan the whole open backlog without an explicit cutoff. Operator sets this
   to the deploy instant (same env var ENG-456/457 already use for backfill
   suppression).
2. **Emit guard 2 (defense in depth).** We also pass `source_created_at =
   candidate.created_at` to `NotificationEventService.emit`, which independently
   suppresses anything before `notifications_cutoff_at` (`event_service.py:184`).
3. **Master enablement.** `NOTIFICATIONS_ENABLED` defaults **False** → emit
   returns `[]` regardless. Nothing sends until the operator flips it on.

So even a mis-set cutoff cannot blast while notifications are disabled, and a
correct cutoff is required for the scan to pick anything up.

## 3. Routing — DECISION: reuse ENG-458 per-location → `leads` channel

- **Event → channel:** a new default seed rule routes
  `identity.shared_contact_reuse` → channel name **`leads`** (the existing
  `DEFAULT_LEAD_CREATED_CHANNEL`), `provider_kind="mattermost"`, `conditions=[]`.
  "Tagged lead" = the leads channel (Mattermost has no first-class tags); the
  card title/text label it as a lead-hygiene alert.
- **Per-location team:** the emit engine resolves the team from
  `context["location_id"]` → `tenant.location.external_ref['mattermost_team']`
  and qualifies the channel to `team/leads` (`event_service.py:_resolve_team` /
  `_qualify_channel`). No mapping → bare `leads` → adapter default team. Never
  raises.
- **Deriving location for a candidate:** the scan resolves the **incoming**
  person's location via `OpsService.list_person_location_profiles_for_person`
  (most-recent profile by `last_evidence_at`, falling back to the existing
  person if the new one has none). No profile → `location_id=None` → default
  team. The worker boundary may import `ops` (the consult-reminder scan already
  imports `OpsService`).
- **Safe no-op when unconfigured:** if no `identity.shared_contact_reuse` rule
  is seeded, `emit` returns `[]` (no rule → nothing). The job is therefore a
  safe no-op until the operator (a) seeds the rule, (b) sets a per-team `leads`
  channel + `external_ref['mattermost_team']` mapping, (c) sets
  `NOTIFICATIONS_CUTOFF_AT`, (d) flips `NOTIFICATIONS_ENABLED`.

## 4. No PHI in the body — DECISION: uids + contact *kind* only

The card template references **only** non-PHI placeholders:
`{{person_uid}}`, `{{deep_link}}`, `{{other_person_uid}}`, `{{other_deep_link}}`,
`{{contact_kind}}` ("phone"/"email", the *type* not the value), `{{location_label}}`.

It contains **no** `{{name}}`, `{{phone}}`, `{{email}}`, DOB, SSN, or clinical
text. The scan **never puts** name/phone/email into the emit context — unlike the
lead/consult cards (which deliberately carry PHI in `phi_mode="full"`), this card
is PHI-free *by construction*, so it is safe regardless of the
`messenger_phi_full` flag. Logs emit **counts only** (`tenants`, `emitted`,
`failed`) plus opaque `person_uid` — never the contact value (matches the
existing logging discipline).

Sample card:
> ♻️ **Shared contact reused** — a new record reuses an existing **phone** already
> on file. Capture a distinct contact per person.
> Person: `[Open in CRM](…/persons/<new_uid>)` · Existing: `[Open in CRM](…/persons/<existing_uid>)`

## 5. Volume / dedup — DECISION: one alert per candidate, idempotent

`emit(dedupe_key=str(candidate.id))` claims `(tenant,
"identity.shared_contact_reuse", candidate_id)` in the durable
`notification_emitted` ledger (`notification_repository.py:claim`). At-most-once
ever: re-runs, overlapping ticks, and worker restarts all no-op. One alert per
reuse *signal*, never per pull retry. The claim + outbox enqueue share the
scan's session and commit atomically (transactional outbox).

## 6. Prod runtime — Cloud Run Job + Scheduler (operator follow-up, NOT in this PR)

Prod has no always-on worker (ENG-172). Like `consult_reminder_scan`, this ships
a Cloud-Run-Job `run()` entrypoint (`shared_contact_reuse_scan.py`). **This PR
does NOT edit `infra/`.** Operator follow-up (orchestrator handles separately,
like ENG-550):

- add a `fusion-job-shared-contact-reuse-scan` Cloud Run Job to
  `deploy_cloud_run.sh` (reuses the API image — `apps.worker.jobs.*` is
  importable there),
- add a Cloud Scheduler trigger (suggest every 5–10 min; the scan is a cheap
  cutoff-bounded indexed SELECT per tenant),
- set `NOTIFICATIONS_CUTOFF_AT` (deploy instant) + `NOTIFICATIONS_ENABLED=true`
  + seed the rule + per-team `leads` channel mapping.

**Local dev:** an `arq.cron` entry is added to `WorkerSettings.cron_jobs`
(mirrors `scan_consultation_reminders`) so docker-compose dev exercises it.

## 7. Files to touch

| File | Change |
|---|---|
| `packages/integrations/chat/events.py` | + `EVENT_SHARED_CONTACT_REUSE` const + roster |
| `packages/integrations/chat/seeds.py` | + `SHARED_CONTACT_REUSE_CHANNEL="leads"` + PHI-free template + default rule |
| `packages/identity/repository.py` | + `list_open_reuse_candidates_created_after(...)` |
| `packages/identity/service.py` | + `list_open_reuse_candidates_created_after(...)` → `MatchCandidateOut` |
| `apps/worker/jobs/shared_contact_reuse.py` | scan logic (per-tenant emit) |
| `apps/worker/jobs/shared_contact_reuse_scan.py` | Cloud-Run-Job `run()` entrypoint |
| `apps/worker/main.py` | register fn + local-dev cron |
| `tests/identity/…` | unit: repo/service query (cutoff + rule filter) |
| `tests/worker/test_shared_contact_reuse.py` | integration (real PG): new signal→1 enqueued; re-run→0; pre-cutoff→0; no-PHI payload; disabled→0 |
| `tests/integrations/chat/…` | seed rule presence + event roster |

**No migration** (ledger + cutoff reused). Alembic head unchanged.

## 8. Risks / do-not-merge

- **Volume:** every distinct-person reuse pages the leads channel. Mitigations:
  cutoff + dedupe + master gate; operator watches volume after enabling.
- **Location accuracy:** a person with no `person_location_profile` routes to the
  default team. Acceptable; documented.
- **Do-not-merge:** until Codex cross-review + operator approval; infra job +
  scheduler + env (`NOTIFICATIONS_CUTOFF_AT`, `NOTIFICATIONS_ENABLED`) + rule
  seed + per-team `leads` mapping are operator follow-ups, not done here.
