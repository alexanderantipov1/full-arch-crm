# ENG-501 — PHI / BAA Go/No-Go Decision Memo (Prod Mattermost)

**Mission:** Mattermost production bring-up (ENG-442 / Block I)
**Decision owner:** the doctor (single operator) — this memo *prepares* the call, it does not make it.
**Prepared by:** Claude Code (orchestration session, 2026-06-17). Read-only analysis; no infra provisioned, no secrets stored, nothing committed.
**Status of this gate:** FIRST gate in the chain — blocks all real-patient go-live (ENG-500 [7]).

---

## Summary — the decision being asked

ENG-460 flipped the corporate messenger to an **authorized PHI surface**: production Mattermost
cards now carry the patient's **real name + phone + source/provider**, and the Mattermost message
store is durable. Standing up prod Mattermost therefore stands up a **PHI system**. Before any real
patient data flows to it (ENG-500), the operator must decide: **does our PHI/BAA posture cover this,
and are the minimal safeguards in place or scheduled?** This memo lays out (a) what changed, (b) the
control checklist mapped to the child tickets that close each gap, (c) a BAA analysis, and (d) a
clear recommendation plus a sign-off block.

**Bottom line up front:** the existing **account-level Google BAA covers the hosting** (no third
party receives PHI — Mattermost is *our* app on covered GCP infra), so **no new vendor BAA is
needed**. The remaining gaps are purely the standard PHI-system safeguards (TLS, encryption-at-rest
confirmation, retention/backup policy, MM-server-log handling), all already tracked as child tickets.
Recommendation: **GO-with-conditions** — provision the host now, do NOT flip notifications on for
real patients (ENG-500) until the conditions below are all true.

---

## What changed (ENG-460)

- Original posture (ADR-0006 / RUNBOOK §1): messenger was **de-identified by default**
  (`phi_mode="deidentified"`) — cards carried only an opaque `person_uid` + a deep link, never a
  name/phone. Under that posture prod Mattermost was **not** a PHI system.
- ENG-460 reversal (ADR-0006 "Update", 2026-06-15): the operator decided the corporate messenger is
  an **authorized PHI surface** — only staff with PHI access read the Mattermost team, so cards must
  carry real name / phone / source (lead) / provider+kind+time (consultation) to be useful.
- Mechanism (grep-verified):
  - `packages/core/config.py:300` — `Settings.messenger_phi_full` (alias `MESSENGER_PHI_FULL`)
    **defaults to `True`**.
  - `packages/integrations/chat/event_service.py:187` —
    `phi_mode = "full" if settings.messenger_phi_full else "deidentified"`.
  - `packages/integrations/chat/render.py` — `phi_mode="full"` bypasses the de-identification
    allowlist and substitutes any context var verbatim (incl. `{{name}}` / `{{phone}}`).
  - PHI is resolved at the **worker boundary** via `IdentityService`
    (`apps/worker/jobs/ingest_scheduled.py` lead path; `packages/ingest/consultation_notify.py`
    consultation path), never inside the de-identified signal.
- **Net effect:** PHI now physically lands in the **Mattermost store (its own Postgres + GCS file
  store)** — separate from the canonical 8-schema DB (invariant #1 preserved), but it is now a
  protected-data store in its own right.
- **Clean rollback exists:** set `MESSENGER_PHI_FULL=false` → renderer reverts to the de-identified
  allowlist (name/phone become `[redacted]`). This is the immediate "downgrade out of PHI-system
  status" lever if any condition below cannot be met at go-live.

---

## Control checklist

| # | Control | Required? | Current state | Gap | Who closes it |
|---|---------|-----------|---------------|-----|---------------|
| C1 | **BAA covers the host** (no third party receives PHI) | Yes | GCP account-level Google BAA in place (confirmed 2026-05-08, ENG-107). Prod MM is self-hosted on GCE VM + Cloud SQL + GCS — all GCP-covered. Slack / MM-Cloud were rejected in ADR-0006 precisely to avoid an off-perimeter processor. | **None** — analysis below confirms no new BAA needed. Record the determination. | ENG-501 (this memo) → ADR-0006 addendum |
| C2 | **Encryption at rest** (MM DB + GCS file store) | Yes | GCP encrypts Cloud SQL data + GCS objects at rest by default (Google-managed keys, BAA-covered). | Confirm prod MM DB is **Cloud SQL** (not VM-local disk) so at-rest encryption + managed backup apply; if co-located on the VM, confirm the VM persistent disk is encrypted (it is, by GCP default) and that backups are encrypted. Decide DB placement (OPEN DECISION #4). | ENG-494 (host bundle: DB placement) |
| C3 | **Encryption in transit** (TLS to MM + on the webhook callback) | Yes | Local dev is plain HTTP (loopback). No prod TLS termination yet. | Provision `chat.fusioncrm.app` (or chosen host) behind TLS; set `action_callback_base` + outgoing-webhook callback to `https://…`. (ADR-0006 open question; RUNBOOK §5.1.) | **ENG-494** |
| C4 | **Access control to the MM workspace** (who reads the channels) | Yes (record it) | **Single operator today (the doctor), full provider access.** This matches the documented dev-phase "show everything / pre-access-control" posture (CLAUDE.md). MM workspace membership = the gate; only PHI-authorized staff are added. | No technical gap today. **Record** that workspace membership IS the access control and must stay restricted to PHI-authorized staff. When more staff/roles exist, revisit (parallels the platform's future access-control layer). | ENG-495 (workspace/bot/channel setup) + ENG-501 (record posture) |
| C5 | **Audit / retention / backup** of the PHI message store | Yes | Platform-side: notification enqueue/dispatch already audited (`integrations.notification.enqueued`, `notification.dispatch.sent/.failed`). MM-side: **no retention or backup policy defined** (ADR-0006 + RUNBOOK OPEN DECISION #6). | Define + implement: MM DB backup into the existing GCS backup contour; a message/file **retention policy**; document it. | **ENG-494** (backup wiring) + ENG-501 conditions (retention policy decision) |
| C6 | **Platform logs stay PHI-free** | Yes (non-negotiable) | **Already enforced.** `render.py`/`event_service.py` log only `person_uid` + event codes via `packages/core.logging.get_logger`; the rendered card text is never logged. Logging rules in CLAUDE.md + `packages/core/CLAUDE.md` forbid names/phones/DOB/clinical text. This is one of the three things the dev-phase posture does NOT relax. | None on the platform side. | (standing invariant — no ticket) |
| C7 | **Mattermost's OWN server logs may contain PHI** | Yes | MM is third-party software we operate; its server/access logs can contain message content or PII independent of our app's PHI-free logging. | Treat MM server logs as a **PHI artifact**: keep them on BAA-covered infra (the VM / Cloud Logging in project `fusioncrm-494201`), do NOT export to any non-covered sink, restrict access, apply the same retention discipline as C5. Set MM `LogSettings` to avoid verbose message logging where possible. | ENG-494 (log sink config) + operator note |
| C8 | **Delivery runtime actually runs in prod** (operational, not a PHI control but a go-live gate) | Yes | Email `drain_outbound_queue` is PAUSED in prod (ENG-172, no always-on worker). Messenger drains (`drain_notification_outbox` / `map_chat_inbound`) need a prod runtime. | Provide Cloud Scheduler + Cloud Run Jobs (or equivalent) so drains run. | **ENG-498** (delivery design) |

---

## BAA analysis

**Question:** does the existing Google BAA cover prod Mattermost carrying PHI, and is any *new* BAA
required?

**Determination: the existing account-level Google BAA covers it; no new vendor BAA is needed.**

Reasoning:

1. **The PHI never leaves a BAA-covered processor.** Prod Mattermost is **self-hosted on GCP**: the
   image runs on a GCE VM, its database on Cloud SQL (or the VM's encrypted disk), and its file store
   in GCS — all inside project `fusioncrm-494201`, all covered by the **account-level Google BAA
   confirmed 2026-05-08 (ENG-107)**. Mattermost is **our application running on covered
   infrastructure**, not a service that *receives* our PHI as a processor.

2. **No third party receives the PHI.** We use the **Team Edition self-hosted image** and integrate
   via its HTTP API; we send messages into a store we operate. There is no Mattermost, Inc. SaaS in
   the path. Therefore **no separate "Mattermost vendor BAA" is required** — there is no vendor to
   sign one with for this deployment model.

3. **This is exactly why the SaaS options were rejected in ADR-0006.** Both rejected alternatives put
   PHI on a third-party processor:
   - *Option A (Slack SaaS)* — rejected: a HIPAA BAA is only on Enterprise Grid, and conversation +
     attachment data would leave the clinic perimeter onto a third-party SaaS.
   - *Option C (Managed Mattermost Cloud)* — rejected: same off-perimeter / third-party-processor
     problem.
   Self-hosting was chosen specifically to keep the message store **inside the controlled,
   BAA-covered boundary** — which is what makes "no new BAA" true.

4. **Caveat that must hold:** the "no new BAA" conclusion depends on PHI staying on covered infra.
   If any component is later moved off GCP (e.g. MM logs shipped to a non-covered SaaS log analytics
   tool, attachments mirrored to a non-covered CDN, an external uptime/monitoring agent that ingests
   message bodies), that component would receive PHI and would need its own BAA — or must not receive
   PHI. Controls C2/C5/C7 enforce this. No such off-GCP sink is planned.

**Conclusion:** BAA posture is **satisfied by the existing Google BAA**. The decision to record this
self-hosted-on-covered-infra determination is itself part of closing ENG-501.

---

## Recommendation

**Recommended: GO-with-conditions.**

- The **BAA question is settled** (existing Google BAA covers self-hosted MM; no new vendor BAA).
- The remaining items are **standard PHI-system safeguards**, not blockers to *provisioning* — they
  are blockers to *turning real-patient notifications on*. All are already scoped as child tickets.
- A clean **rollback lever exists** (`MESSENGER_PHI_FULL=false` → de-identified rendering), so the
  PHI exposure can be removed instantly if a condition slips at go-live.

**Therefore:** approve **provisioning** the prod host now (ENG-494/495/496/497/498 may proceed under
their own approvals), but treat the following as the **minimal control checklist that MUST all be
true before ENG-500 (enable on prod / first real-patient card)**:

- [ ] **C1 recorded** — BAA determination written into ADR-0006 (this memo's addendum block) and the
      ENG-501 issue. *(ENG-501)*
- [ ] **C2** — prod MM DB placement decided and at-rest encryption confirmed (Cloud SQL preferred;
      VM disk encryption + encrypted backups if co-located). *(ENG-494)*
- [ ] **C3** — TLS terminated on the public MM host; `action_callback_base` + webhook callback use
      `https://`. *(ENG-494)*
- [ ] **C4** — MM workspace membership restricted to PHI-authorized staff (today: the doctor only);
      posture recorded. *(ENG-495 + ENG-501)*
- [ ] **C5** — MM DB backup wired into the GCS backup contour AND a written message/file retention
      policy exists. *(ENG-494 + operator)*
- [ ] **C7** — MM server logs confirmed to stay on BAA-covered infra (no non-covered log sink),
      access-restricted, retention-bounded; verbose message logging disabled where possible.
      *(ENG-494)*
- [ ] **C8** — prod delivery runtime confirmed running the drains (else cards never deliver anyway).
      *(ENG-498)*
- [ ] **Rollback verified** — `MESSENGER_PHI_FULL=false` confirmed to revert to de-identified
      rendering in the prod config, as the standing downgrade lever.

**NO-GO trigger:** if at go-live any of C2/C3/C5/C7 cannot be satisfied, do **not** enable full-PHI
cards — either delay ENG-500 or go live with `MESSENGER_PHI_FULL=false` (de-identified, non-PHI
posture) until the gap closes. C6 is non-negotiable and is already enforced.

This is a recommendation only. The operator makes the final call below.

---

## Decision to record (operator sign-off)

> Paste this block, completed, into (a) ADR-0006 as a dated addendum and (b) the ENG-501 Linear issue.

```
ENG-501 — Prod Mattermost PHI/BAA go/no-go

Decision: [ GO-with-conditions | NO-GO-until | GO (de-identified, MESSENGER_PHI_FULL=false) ]
Decided by: the doctor (single operator)
Date: __________

BAA determination: The existing account-level Google BAA (ENG-107, 2026-05-08) covers prod
Mattermost. It is self-hosted on covered GCP infra (GCE VM + Cloud SQL/encrypted disk + GCS); no
third party receives PHI, so NO separate Mattermost-vendor BAA is required. (Contrast: Slack /
Mattermost Cloud were rejected in ADR-0006 because they place PHI on a third-party processor.)

Conditions required true before first real-patient card (ENG-500):
[ ] C2 at-rest encryption + DB placement confirmed (ENG-494)
[ ] C3 TLS in transit (ENG-494)
[ ] C4 MM workspace access restricted to PHI-authorized staff (ENG-495)
[ ] C5 backup wired + retention policy written (ENG-494 + operator)
[ ] C7 MM server logs kept on covered infra, access-restricted (ENG-494)
[ ] C8 prod delivery runtime running the drains (ENG-498)
[ ] Rollback lever (MESSENGER_PHI_FULL=false) verified in prod config

Non-negotiable (already enforced): platform application logs stay PHI-free (C6).

Operator notes / exceptions: ______________________________________________
```

---

## References

- `docs/decisions/ADR-0006-interactive-messenger-layer.md` — Decision, ENG-460 update, Risks/open
  questions, rejected Options A/C.
- `docs/integrations/mattermost/RUNBOOK.md` §5 — prod bring-up plan + open decisions #2/#3/#4/#6.
- `packages/core/config.py:300` — `messenger_phi_full` flag (default `True`).
- `packages/integrations/chat/render.py`, `chat/event_service.py:187` — render-mode selection.
- `packages/core/CLAUDE.md` + root `CLAUDE.md` (Logging; Data-visibility single-user posture).
- ENG-107 — account-level Google BAA confirmed 2026-05-08.
- Mission: `.agents/orchestration/mattermost-prod-bringup-v1/goal.md` (subtask chain → child tickets).
```
