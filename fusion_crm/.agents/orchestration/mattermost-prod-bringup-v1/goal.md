# Mission — Mattermost production bring-up (ENG-442 / Block I)

**Opened:** 2026-06-17 (overnight session)
**Orchestrator:** Claude Code (inline orchestration; no CLI workers launched — see decision-log)
**Epic:** ENG-433 Interactive Corporate Messenger Layer (Mattermost) V1
**Parent:** ENG-442 — Block I, production infrastructure (DEPLOYMENT_RULES-gated)

## Business goal

Bring the already-built, locally-proven Mattermost messenger layer to production so
real `lead.created` / `consultation.scheduled` / consult-reminder events reach the
clinic team in a controlled, audited channel — replacing uncontrolled WhatsApp/SMS.

Per ENG-460, the messenger is now an **authorized PHI surface**: prod cards carry the
real patient name + phone. Standing up prod Mattermost therefore stands up a **PHI
system**, which raises the bar (TLS, encryption-at-rest, access control, retention).

## Subtask chain (operator numbering → Linear)

| # | Linear | Title | Class | Gate |
|---|--------|-------|-------|------|
| [8] | ENG-501 | PHI/BAA posture go/no-go | **operator decision** | FIRST — blocks all real-patient go-live |
| [1] | ENG-494 | Host prod MM: GCE VM + Postgres + GCS + chat.fusioncrm.app TLS | contract_change / infra | needs approval + spend + DNS/TLS |
| [2] | ENG-495 | Prod workspace: bot, token, channels, capture channel IDs | infra / manual | needs [1] live base_url |
| [3] | ENG-496 | Store prod MM credential (encrypted, via credential service) | normal | needs [1]+[2] (secret) |
| [4] | ENG-497 | Configure prod rules with prod channel IDs (seeds.py has LOCAL ids) | normal | needs [2] channel IDs |
| [5] | ENG-498 | Prod delivery without a worker: Cloud Scheduler + Cloud Run Jobs | **contract_change** | URGENT — key architectural gap; needs code |
| [6] | ENG-499 | Prod backfill: doctor + source_status (ENG-487) | normal | BLOCKED on PR #168 merged to main |
| [7] | ENG-500 | Enable on prod (NOTIFICATIONS_ENABLED + CUTOFF) + e2e smoke | contract_change | deploy/env flip — needs approval |

## Hard gates (from ENG-442 description + DEPLOYMENT_RULES)

1. **ADR-0006 = Accepted** — ✅ CONFIRMED (status "Accepted", 2026-06-15).
2. **DEPLOYMENT_RULES preflight passes** — partially evaluated this session (see
   `artifacts/eng-442-preflight-evidence.md`). One open item: alembic must be a
   single head on the **deploy branch (main)**; the dev checkout shows 6 heads
   (multi-branch + known `b69bce1e2195` local artifact). Must reconcile on main.
3. **Never mixed with feature PRs** (DEPLOYMENT_RULES §9) — infra goes in its own PR.
4. **Reproducible from repo scripts**, not one-off gcloud (DEPLOYMENT_RULES §Operating-model).

## Why this session could NOT auto-execute the chain

Every executable step is one of: (a) an operator go/no-go decision ([8]), (b) a
hard-to-reverse / outward-facing / spend prod action requiring explicit same-conversation
approval ([1] VM+DNS+TLS, [7] env flip + deploy — CLAUDE.md invariant #3), (c) blocked on
a merge ([6] on PR #168), or (d) dependent on a live secret produced by an earlier manual
step ([2]→[3]→[4]). Standing up an **unattended, public, PHI-bearing host overnight** is
exactly what the mission posture forbids ("let's just try it is not acceptable").

So this session produced **review-and-execute-ready artifacts + the operator decision
memo** instead, so the morning is "decide → approve → run", not "start from scratch".
