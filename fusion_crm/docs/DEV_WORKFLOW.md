# Dev Workflow — Rules of Engagement (operator-facing)

> One-page summary of **how we ship**: the two environments, who needs
> permission for what, how parallel agents stay out of each other's way, and
> where secrets live. This is the index — the deep rules live in the canonical
> docs linked throughout. If this page and a linked doc ever disagree, the
> linked canonical doc wins, and this page is the bug.
>
> Canonical sources: [`docs/WORKFLOW.md`](./WORKFLOW.md) (engineering loop),
> [`.agents/orchestration/PARALLEL_WORK_POLICY.md`](../.agents/orchestration/PARALLEL_WORK_POLICY.md)
> (parallel work / worktrees / merge ordering / roles),
> [`docs/DEPLOYMENT_RULES.md`](./DEPLOYMENT_RULES.md) (env / secrets / deploy),
> and the root [`CLAUDE.md`](../CLAUDE.md) (hard invariants).

## 1. Two environments — see it local first, then prod

There is **no staging** today (decoupling merge from deploy via a staging
contour is the deferred "variant A" milestone). The pre-prod contour **is** your
local machine.

| Contour | What it is | How you see it | Permission |
| --- | --- | --- | --- |
| **Local** | Docker Postgres + Redis, then API `:8000` / Web `:3000` / Worker, via `make up` then `./infra/scripts/dev-up.sh` | browse `localhost` | **None.** Run / reload / migrate the local DB freely. |
| **Production** | GCP Cloud Run (`fusioncrm-494201`), real PHI data | the live app after deploy | **Explicit operator approval, every time.** |

**Local actions need no approval, but they must be signalled.** Whenever an
agent starts, reloads, loads data into, or migrates the local stack, it
**announces it** ("started local stack, API on :8000, migrations applied to
local DB") — local is approval-free but never silent, so the operator knows
there is something new to look at.

## 2. Reaching production = merging to `main`

Production has no separate deploy button. **Merge to `main` = unattended prod
deploy + prod migrations** (workflow `deploy-prod`). Therefore:

- **No agent merges to `main` without the operator's explicit "merge / deploy"
  in the current session.** Approval does not carry across sessions.
- The same gate applies to any production-infra action (GCP / WIF / Cloud Run /
  Secret Manager), and to `push` / force-push / branch deletion.
- Hard-to-reverse or outward-facing actions always require confirmation,
  regardless of contour.

This is the standing invariant — see the `merge-to-main-auto-deploys-prod`
memory and [`docs/DEPLOYMENT_RULES.md`](./DEPLOYMENT_RULES.md).

## 3. Server-side merge gate (live on `main`)

A GitHub ruleset enforces the gate so a bad or racing change can't reach prod:

- PR required (no direct push to `main`); branch must be **up to date** with
  `main` before merge; required CI checks **green**
  (`Lint + typecheck + tests`, `Web — eslint + tsc + vitest`).
- `0` required approvals (single operator can't self-approve — strict status
  checks are the real control); force-push and deletion of `main` blocked; no
  bypass actors.
- `make verify-alembic-heads` (folded into `make verify` + a standalone CI step)
  catches the concurrent-migration "two heads" race **before** merge. Rejoining
  heads is a deliberate `alembic merge heads`, never an auto-merge in the deploy
  pipeline. See [`docs/DEPLOYMENT_RULES.md`](./DEPLOYMENT_RULES.md) §11 and the
  "Migration Merge Ordering" section of the parallel-work policy.

The ruleset config lives in `infra/scripts/setup_main_ruleset.sh` (idempotent;
re-run reconciles the live ruleset). Re-applying after any repo rename/transfer
also requires repointing the prod WIF/OIDC provider condition and the
deployer-SA principalSet to the new `owner/repo`.

## 4. Parallel agents without collisions

Several agents work at once — Codex on a separable direction plus multiple
Claude Code terminals — isolated by **git worktrees** so they never collide on
shared HEAD. The canonical checkout `~/dev/Fusion_crm` is the **integration
cockpit**: merge + read-only inspect only, **never edit there**.

Three lanes by nature of work (full rules:
[`PARALLEL_WORK_POLICY.md`](../.agents/orchestration/PARALLEL_WORK_POLICY.md),
operator guide: `.agents/orchestration/RUNBOOK_OPERATOR.md`):

- **A. Large separable features** → 1 Linear issue = 1 worktree = 1 branch off
  `origin/main`; Codex vs Claude split by **non-overlapping** file/domain
  territory.
- **B. Small interactive fixes / debugging** → the **fix-lane** (`/fix-lane
  <area>` → `../fusion-fix-<area>`), tracked under the standing umbrella issue
  **ENG-537**. One lane per session, partitioned by area, so terminals don't
  collide.
- **C. Cross-cutting** → tripwires (a 3rd file, a 2nd domain, a shared
  contract / DTO / schema / migration / env / metric / date-time / PHI / audit
  change, or a dependency chain) → **STOP and reclassify** to a normal /
  contract-change task with its own worktree and cross-runtime review.

A pre-flight + pre-commit **HEAD-race guard** (in the parallel-work policy)
protects against two sessions racing the same HEAD. A statusline badge surfaces
repo/mission drift to the operator.

## 5. Secrets — env vs. database

Two distinct classes (canonical:
[`DEPLOYMENT_RULES.md`](./DEPLOYMENT_RULES.md) §6 and `CLAUDE.md` invariant #10):

- **Platform / infra runtime secrets** (DB DSN, `ENCRYPTION_KEY`, provider OAuth
  *app* secrets, service-account creds): **env-only** — local `.env`, production
  **Secret Manager** injected as env (`--set-secrets`). Never hardcoded, never
  logged, never in repo plaintext.
- **Tenant / company credentials** (per-company OAuth tokens, CareStack
  vendor/account, integration API keys): **stored in the database**,
  tenant-scoped, **encrypted at rest** (today: `integrations.integration_account`
  with the Fernet `EncryptedString` type; the documented direction is
  `tenant.integration_credential` via `IntegrationCredentialService`). Entered
  through the company Settings / Integrations UI, audited, returned to clients
  only as metadata.

The bridge: **env holds the master encryption key; the DB holds the
per-company secrets encrypted with it.** This is consistent with "secrets are
env-only" — env is for *platform* secrets; the DB stores *tenant* data, which
includes their (encrypted) credentials.

## 6. Invariants that never relax (any contour)

Logs stay PHI-free · `phi.*` schema separation, PHI reads through `PhiService` ·
append-only `audit` · AI agents never touch the DB directly (services only) ·
full-fidelity raw ingestion · secrets env-only (per §5) · confirmation for
hard-to-reverse / outward-facing actions. Full list: root
[`CLAUDE.md`](../CLAUDE.md) "Hard architectural invariants".
