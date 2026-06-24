# Household Identity Grouping, Duplicate Alerting & Merge — Design Proposal

> **Status:** draft / needs decision (operator). Strategy proposal, no code.
> Strategy proposes, Orchestrator disposes.
> **Origin:** operator vision (2026-06-21), following the ENG-541 dedup epic and
> the ENG-550 prod live pass (178 merges; 1,144 ambiguous candidates left open).
> **Supersedes the scope of:** ENG-341 (which becomes the *foundation* layer A).

## 1. Problem & current state

A phone number (or email) is a **shared household contact**, not a unique
identity key. Household members — spouse, children — legitimately share one
phone. The current model forbids that:

- `identity.person_identifier` has a global `UniqueConstraint("kind","value")`
  (`uq_person_identifier_kind_value`, `packages/identity/models.py:173`). It is
  **not even tenant-scoped** — the value is unique across the whole table.
- ENG-340 shipped a surgical workaround: `_SHARED_CONTACT_KINDS = {"phone","email"}`
  with skip-on-conflict (`packages/identity/service.py:64`), so a shared phone no
  longer crashes the ingest tick. **Cost:** the second person's phone/email is
  silently *not* persisted as an identifier row.
- ENG-542 (in prod) works around the *consequence*: the person card surfaces
  same-phone people via the hint resolver (`person_household_members_by_hint`),
  not via identifier rows.
- ENG-309 already encodes the right discriminator: **different DOB or SSN → never
  merge** (household), same/compatible → mergeable (same person).
- ENG-550 (in prod) merged the 178 clearly-duplicate persons; **1,144 candidates
  remain `open`** — genuinely ambiguous shared-contact pairs. This is exactly the
  population this design is about.

## 2. Operator vision (verbatim intent, structured)

1. **Phone = the unit of marketing/outreach work.** One number = one contact we
   work through. If a family left one number, that is their choice — we still
   work via that one phone.
2. **Multiple people may sit under one contact** (spouse, kids) — this is normal,
   not an error.
3. **At the global level we link them into an "account / family block"** — a
   household grouping over the individual persons.
4. **It is a *duplicate* (not a household member) when the data difference is
   suspicious** — i.e. probably the same human wrongly split.
5. **Build a merge mechanism** — on our side first; later optionally push the
   merge into the source systems (CareStack / Salesforce).
6. **At minimum, now: send a Messenger notification when a duplicate is created.**

## 3. Key architectural insight — three independent layers

The vision is **not one ticket**. It decomposes into three layers that must stay
separate so "one marketing contact" never pollutes the identity model:

| Layer | What | Status today |
|---|---|---|
| **A. Identity (individuals)** | Distinct persons may share a phone/email; each holds its own contact. Drop the global `UNIQUE` on `phone`/`email`; keep it for true 1:1 keys. | **= ENG-341 (foundation).** DOB/SSN hard-veto already separates "household" from "same person" (ENG-309). |
| **B. Household / family grouping** | A NEW grouping above `person`: "these N persons are one family/account." Members stay distinct; they are linked. | **Missing.** CareStack already exposes `accountId` (its household key) — the natural anchor. |
| **C. Marketing / outreach contact** | Dedup "one phone = one outreach target" for campaigns/calls — a **projection on top of** identity, not an identity merge. | **Missing as an explicit layer.** Must not mutate `identity`. |

Plus two cross-cutting capabilities:

- **D. Duplicate alerting** — when a *suspicious* duplicate is detected, raise a
  Messenger notification. Maps onto existing `match_candidate status='open'` +
  the ENG-498 notification runtime (`integrations.notification_outbox`,
  Cloud Run Job `fusion-job-notification-drain`).
- **E. Merge mechanism** — operator-facing merge action on our side now
  (`IdentityService.record_merge` exists, append-only); push-to-provider later.

## 4. "Suspicious duplicate" vs "household member" — the discriminator

We already have most of the logic; it needs to be made explicit and surfaced:

| Signal combination | Classification | Action |
|---|---|---|
| Same phone + **different DOB/SSN** | Household member (different person) | Layer B grouping. Never merge (ENG-309 veto). |
| Same phone + compatible name + no contradictions | Same person | Auto-merge (Tier-1; ENG-550 did 178 of these). |
| Same phone + similar but **suspiciously close** (same name, DOB missing; minor mismatch) | **Duplicate under question** | `match_candidate status='open'` → **Messenger alert (D)** → operator merge (E). |

So "suspicious duplicate" ≈ today's open `match_candidate`. There are 1,144 in
prod now. The alert hooks onto the moment such a candidate is created.

## 5. Decisions — RESOLVED by operator 2026-06-21

1. **Household-block anchor — ASSUMED YES (confirm).** Operator restated the
   item without an explicit alternative → interpreted as "anchor as proposed":
   CareStack `accountId` primary + shared-contact signal + fallback for
   non-CareStack origins. *Flagged for explicit confirmation at B design.*
2. **Marketing contact = separate projection — YES.** Outreach dedups by phone
   to one target; identity stays per-person.
3. **Alert routing — per LOCATION into the messenger team's leads channel,
   tagged "lead" (for now).** Reuse the ENG-458 per-location routing. (Operator
   answered the *destination*; combined with #5 the *trigger* is "always on
   shared-contact reuse", see D below.)
4. **Provider-side merge push (E2) — YES, later phase.** Now = our side + alert
   only.
5. **Alert philosophy — ALWAYS inform that the phone already exists.** Not only
   "suspicious" cases: whenever an incoming record reuses an existing phone/email,
   notify — the business goal is to *nudge staff to capture distinct contacts per
   person*. (Still: no retro-blast of the 1,144 existing open candidates; alert on
   new reuse events going forward only. Watch volume.)

### Original recommendations (kept as rationale)

1. **Household-block anchor.** *Recommend:* CareStack `accountId` as primary
   household key (it is their household already), shared phone as a secondary
   signal — avoid inventing a new entity if `accountId` covers it. Needs a fallback
   for non-CareStack-origin persons (Salesforce leads, web forms).
   → **confirm anchor.**
2. **Marketing contact = separate projection?** *Recommend:* yes — outreach dedups
   by phone to one target; identity stays per-person. → **confirm.**
3. **What triggers the Messenger alert?** options: (a) new person created on an
   already-known shared contact; (b) an open "duplicate-under-question" candidate
   created; (c) both. *Recommend:* start with (b). → **confirm.**
4. **Provider-side merge push (CareStack/Salesforce).** *Recommend:* later phase,
   separate ticket; now = our side + alert only. → **confirm.**
5. **Tie-break threshold for "suspicious"** (e.g. same name + missing DOB ⇒ alert;
   different DOB ⇒ household, no alert). → **operator to define rules.**

## 6. Proposed Linear structure

- **ENG-341 stays the foundation (Layer A):** drop global `UNIQUE` on
  `phone`/`email`; keep `UNIQUE` for true 1:1 keys (SSN, CareStack
  patient/account id, Salesforce id, portal). Migration with a pre-check for
  existing duplicate values; audit any matching logic that assumes phone is
  globally unique. **contract_change** (touches a hard identity invariant).
- **New epic — "Household identity grouping, duplicate alerting & merge"** with
  children:
  - **B** Household/family grouping entity (anchor on CareStack `accountId` +
    shared-contact signal); members stay distinct, linked into a group.
  - **C** Marketing/outreach contact projection (one phone = one outreach target;
    read-only over identity).
  - **D** Messenger alert on suspicious-duplicate creation (hook on open
    `match_candidate`; reuse ENG-498 notification runtime).
  - **E1** Operator-facing merge action on our side (UI + `record_merge`).
  - **E2** Push merges into CareStack/Salesforce (later phase).
- Sequencing: **A → (B, D in parallel) → E1 → C → E2.** A unblocks everything; D
  is cheap and high-value (operator visibility); E2 is last.

## 7. Constraints & risks

- **Hard identity invariant** (global person, identifier uniqueness, append-only
  `merge_event`, DOB/SSN never logged or in evidence) — propose-before-implement,
  real patient data. Migrations immutable once shipped.
- **Constraint drop is one-way risk:** must pre-check existing dupes and confirm
  no matching path relies on phone global-uniqueness before dropping.
- **Layer leakage risk:** keep C (marketing) out of `identity`. If a "merge for
  outreach" idea starts editing person rows, stop and reclassify.
- **Provider push (E2)** is a new *write* capability into external systems — high
  blast radius, BAA/consent implications — gate hard, do last.
- **Alert noise (D):** 1,144 existing open candidates → do not retro-blast; alert
  only on *new* suspicious candidates, or batch/summarize historical ones.

## 8. What this proposal does NOT do

No code. No migration. No Linear worker assignment. This is the design + the
decomposition for operator review and Orchestrator disposition.
