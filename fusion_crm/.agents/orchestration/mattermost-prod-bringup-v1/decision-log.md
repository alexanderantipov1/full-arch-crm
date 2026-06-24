# Decision log — Mattermost prod bring-up

## 2026-06-17 — Orchestrator: overnight session runs as artifact-prep, not auto-execute

**Decision:** Do NOT launch unattended CLI workers to execute the ENG-442 prod chain
overnight. Produce review-and-execute-ready artifacts + the operator decision memo instead.

**Why:**
- ENG-501 [8] is a pure operator **go/no-go** — an agent cannot decide a HIPAA/PHI posture.
  Per the user's own ordering it gates everything.
- ENG-494 [1] provisions a **public, PHI-bearing GCE VM + DNS (chat.fusioncrm.app) + TLS +
  GCS** — spend + outward-facing + hard-to-reverse. CLAUDE.md invariant #3 and
  DEPLOYMENT_RULES §11 require explicit same-conversation operator approval; standing it up
  unattended overnight is forbidden ("let's just try it is not acceptable").
- ENG-499 [6] is **blocked** on PR #168 (ENG-487) being merged to main.
- ENG-495/496/497 chain depends on a **live secret** (bot token) produced by manual MM-UI
  steps after [1] is reachable.
- ENG-500 [7] is a **prod env flip + deploy** — approval-gated.

**Consequence:** Morning is "decide → approve → run", not "start from scratch". All gated
actions are surfaced in `reports/MORNING_REPORT.md` with the exact commands queued.

## 2026-06-17 — Gate 1 confirmed: ADR-0006 = Accepted

`docs/decisions/ADR-0006-interactive-messenger-layer.md` Status: **Accepted** (2026-06-15).
The first half of the ENG-442 start-gate is satisfied.

## 2026-06-17 — Preflight finding: 6 alembic heads on dev checkout

The current dev branch shows 6 heads incl. the known-local `b69bce1e2195` duplicate
(memory: `blocker_alembic_broken_chain_main.md`). Per RUNBOOK §5.2 the single-head check
must be run against the **deploy branch (main) + a clean checkout**, not this multi-branch
dev DB. Flagged as an open preflight item, not auto-resolved.

## 2026-06-17 — OPERATOR DECISION: ENG-501 PHI/BAA = GO (gate [8] cleared)

The operator (doctor) decided **GO** on the PHI/BAA posture for prod Mattermost
("Это дело и всё. Разрешает всё. Всё разрешается." — 2026-06-17). Recorded as the
operator decision ENG-501 asked for. The messenger may carry PHI in prod under the
standard safeguards tracked in the child tickets (TLS+at-rest ENG-494, backup/retention
ENG-494, workspace access control ENG-495, delivery runtime ENG-498). Downgrade lever
remains `MESSENGER_PHI_FULL=false`.

Gate [8] is cleared. This does NOT auto-execute the irreversible prod steps — provisioning
a billable, public, PHI-bearing host ([1]) and the prod enable ([7]) remain confirm-first /
operator-hands actions (see the "Hold point" note below). Ready-to-paste ADR-0006 addendum
text is in `artifacts/eng-501-phi-baa-decision-memo.md`.

## 2026-06-17 — ENG-498 [5] built autonomously → draft PR #173

After "делай и продолжайся", built the one truly-buildable + reversible child: ENG-498
delivery code (2 Cloud Run Job entrypoints + deploy-script wiring + tests), verified
(ruff clean, 4 tests pass, existing reminder tests pass, bash -n), pushed to
`eng-498-prod-notification-delivery`, opened **draft PR #173**. Correction to the earlier
design artifact: `scan_consultation_reminders` IS on main (ENG-486 merged) — both
entrypoints built, not just the drain. NOT merged, NOT deployed.

## 2026-06-17 — Hold point: NOT auto-provisioning the prod host overnight

Even with "всё разрешается", I am NOT firing the host provisioning overnight, because:
(1) it creates billable, public, PHI-bearing infra (ongoing ~$40/mo) — a confirm-first,
hard-to-reverse action; (2) the provisioning script is still an unreviewed `.draft` (the
author flagged DNS-provider + GCS-HMAC unknowns); (3) the immediate next steps (Mattermost
admin-UI: team/bot/token/channels — ENG-495) physically require the operator's hands.
Running an unreviewed billable public-infra script unattended is exactly "let's just try
it", which the mission forbids. Recommendation: harden the draft into a reviewed
`infra/scripts/provision_mattermost_host.sh` + confirm DNS, then run [1]→[2] together in a
~20-min supervised step.
