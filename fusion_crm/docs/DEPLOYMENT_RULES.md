# Deployment and Environment Rules

This document is the standing contract for production deploys, environment
variables, secrets, and Cloud Run configuration.

Any change that touches `Settings`, env vars, Secret Manager bindings,
Cloud Run services/jobs, deploy scripts, GitHub Actions deployment workflow,
OAuth callback URLs, CORS, or public hostnames must follow these rules.

## Strategic Direction

Build features in small, reviewable slices, but keep the deployment contract
stable and centralized. Large feature merges do not make production safer if
the deploy path, env names, secrets, and smoke checks drift.

The immediate strategy is:

1. Stabilize the deploy contract first.
2. Keep feature PRs small after that.
3. Use feature flags for partially built capabilities.
4. Never mix unrelated feature work with infrastructure/deploy changes.

## Google Cloud Hosting Operating Model

Google Cloud CLI is allowed and expected for operator and agent workflows, but
production state must be reproducible from repository scripts.

Agents may run CLI commands, but durable production behavior must be encoded in
the repo. Do not leave production depending on one-off terminal history.

The operating model is:

1. Use Google Console only for inspection, emergency operations, and rare
   one-time setup that cannot reasonably be scripted, such as OAuth consent
   screen setup, billing settings, or domain verification.
2. Use `gcloud` through canonical scripts for repeatable operations:
   `infra/scripts/deploy_cloud_run.sh`,
   `infra/scripts/provision_cloud_run_foundation.sh`,
   `infra/scripts/provision_cloud_iap_lb.sh`, and deployment preflight scripts.
3. Scripts must be idempotent: describe-or-create, safe to re-run, fail loudly,
   avoid interactive prompts in CI, and print only sanitized summaries.
4. Cloud Run Services are for HTTP workloads only. One-shot work belongs in
   Cloud Run Jobs. Long-running stream/subscriber/queue workers need an explicit
   runtime decision before deployment.
5. GitHub Actions must call the same canonical scripts as manual/operator
   deploys. It must not maintain an independent `gcloud run deploy` contract.
6. After deploy, verify the actual Google Cloud state with `gcloud ... describe`
   and strict smoke checks. A deploy is not complete when the command exits; it
   is complete when the deployed revision has the expected config and behavior.
7. Terraform or another IaC layer must not be introduced into stabilization
   work without an ADR. Repository `gcloud` scripts are the current source of
   truth for the Cloud Run production path.

## 1. One Source of Truth for Env Vars

`packages/core/config.py` is the runtime source of truth for application env
variables. Every other file must match it:

- `infra/env/production.env.reference`
- `infra/scripts/deploy_cloud_run.sh`
- `.github/workflows/deploy-prod.yml`
- Docker Compose files
- deploy preflight checks
- env contract tests

If a variable is added to `Settings` but is missing from the deploy/env
reference path, CI should fail.

## 2. One Variable, One Name

Do not keep aliases for the same production value unless there is a documented
migration window.

Preferred production names:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `MICROSOFT_OAUTH_CLIENT_ID`
- `MICROSOFT_OAUTH_CLIENT_SECRET`
- `ENCRYPTION_KEY`

Avoid parallel names such as `GOOGLE_WORKSPACE_CLIENT_ID` for the same value.
Rename references instead of teaching multiple systems different spellings.

## 3. Cloud Run Env Vars Are Strings

Cloud Run env vars are strings. Avoid direct complex field types for values
that operators set in Cloud Run.

Avoid this for Cloud Run-provided values:

```python
api_cors_origins: list[str]
```

Prefer a raw string field plus a computed property:

```python
api_cors_origins_raw: str = ""

@property
def api_cors_origins(self) -> list[str]:
    return [value.strip() for value in self.api_cors_origins_raw.split(",") if value.strip()]
```

This avoids `pydantic-settings` source-decoding failures when an operator sets
`API_CORS_ORIGINS=https://fusioncrm.app` instead of JSON.

## 4. No Localhost Defaults in Production

Production deploys must fail before traffic promotion if public URL settings
contain development hosts or insecure schemes.

Forbidden in production public URLs:

- `localhost`
- `127.0.0.1`
- `0.0.0.0`
- `http://` for browser-facing or OAuth-facing URLs

Production public URLs must use:

- `https://fusioncrm.app`

This applies to:

- `OAUTH_REDIRECT_BASE_URL`
- `WEB_APP_BASE_URL`
- `TRACKING_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- OAuth callback construction
- CORS origins

Direct Cloud Run URLs are allowed only for internal build-time routing such as
`INTERNAL_API_URL`. They must not become browser-visible canonical URLs.

## 5. One Canonical Deploy Path

Production deployment logic must live in one canonical deploy script. GitHub
Actions should call that script instead of re-implementing `gcloud run deploy`
flags in YAML.

Canonical path:

```sh
./infra/scripts/deploy_cloud_run.sh
```

The workflow may provide inputs such as image tag, service subset, commit SHA,
and CI mode. It must not silently drop service account, VPC, ingress, auth,
resource, env var, or secret flags compared with the manual deploy path.

If an emergency requires inline `gcloud run deploy` flags, the PR must call out
that the duplication is temporary and include a follow-up to remove it.

## 6. Secrets Only Through Secret Manager

Production platform runtime secrets must come from Secret Manager references,
not plaintext repo files or workflow logs.

Cloud Run runtime should use `--set-secrets` for secret values. Compose and
operator paths may document `gcp-secret://` references, but do not mix multiple
secret resolution models on the same production runtime path.

Before deploy, preflight should verify that required secret names exist and
have an enabled `latest` version.

Tenant-owned provider credentials are different from platform runtime secrets.
Do not model Salesforce, CareStack, Twilio, HubSpot, mailbox, payment, or AI
vendor credentials as long-lived Cloud Run env vars once the tenant credential
UI exists.

Tenant/company credentials belong in:

```text
tenant.integration_credential
```

They are entered through the company Settings / Integrations UI, encrypted at
rest, scoped by `tenant_id`, audited, and returned to clients only as metadata.
Workers, API services, and agents resolve them through
`IntegrationCredentialService` using the current tenant context.

Never log:

- secret values
- full DSNs
- OAuth client secrets
- access tokens
- refresh tokens
- service account JSON
- tenant provider credential payloads

## 7. Preflight Before Deploy

Production deploys need a blocking preflight before migration and traffic
promotion.

Minimum preflight checks:

- Required env vars are present for the service being deployed.
- Required Secret Manager secrets exist and have `latest`.
- No production public URL contains localhost or insecure browser-facing HTTP.
- Alembic Cloud Run Job runs from `packages/db`.
- GitHub Actions uses the canonical deploy path.
- Non-HTTP workers are not deployed as Cloud Run Services.
- Service account, VPC, ingress, auth, min/max instances, memory, CPU, port,
  env vars, and secrets match the canonical script.
- Any manual `gcloud` recovery command that changed durable production behavior
  has been converted back into a repo script or documented as an explicit
  one-time operator action.

## 8. Strict Smoke After Deploy

Smoke tests are production safety gates, not informational comments. Once the
authentication path is healthy, smoke failures must fail the workflow and block
or roll back promotion.

Minimum smoke coverage:

- API health responds.
- Web app responds.
- OAuth start URL uses `https://fusioncrm.app`.
- CORS preflight passes from `https://fusioncrm.app`.
- Database migration state is current.
- Protected endpoints require authentication instead of serving public data.

Do not keep `continue-on-error: true` on production smoke unless there is a
dated incident note explaining why it is temporarily necessary.

## 9. Keep Feature Work Separate From Infrastructure

Do not combine unrelated product features with deploy infrastructure changes.

Avoid PRs that simultaneously:

- add Salesforce CDC or another integration feature
- change Cloud Run services/jobs
- change Secret Manager bindings
- change OAuth URL construction
- change Alembic command behavior
- change GitHub Actions deploy workflow

When a feature needs infrastructure, split it:

1. Schema/model change.
2. Service/repository implementation.
3. Ingestion or worker path.
4. UI/API exposure.
5. Feature flag enablement.
6. Production runtime change, if still needed.

## 10. New Env Var Checklist

Every new production env var must satisfy this checklist:

- Added to `packages/core/config.py`.
- Documented in `.env.example` when applicable.
- Documented in `infra/env/production.env.reference`.
- Added to `infra/scripts/deploy_cloud_run.sh` or explicitly documented as
  operator-only.
- Covered by env contract tests or preflight.
- If secret: added to Secret Manager/preflight expectations and passed by
  reference only.
- If URL: covered by no-localhost production validation.
- If consumed by web build: documented as build-time vs runtime.
- If optional: the default must be safe in production, not a localhost trap.

Do not add a new production env var for a tenant-owned provider credential
unless it is explicitly a temporary bootstrap fallback with a removal plan.
Prefer the tenant credential UI and `tenant.integration_credential`.

## 11. Concurrent Alembic Heads (Migration Race Guard)

Two PRs can each branch a migration off the same parent revision. Each is a
single head in isolation and passes CI alone. When both merge to `main`, the
revision graph has **two heads**, and the prod `alembic upgrade head` job fails
with "Multiple head revisions are present" — before any DDL, so prod is not
touched, but the deploy is stuck until a merge revision is added by hand. This
has happened more than once (merge revs `af5ba42a505b` 2026-05-10,
`5c46df9990df` 2026-06-21 / PR #199).

The guard is three layers; do not rely on any single one:

1. **Branch protection — "require branch up to date before merging" (strict).**
   Forces the trailing migration PR to rebase onto the moved `main`, which
   brings both migrations into its branch and makes the second head visible to
   that PR's own CI. **Not yet enforced:** rulesets/branch protection on a
   private repo need GitHub Team; on the current Free plan the API returns 403
   and the repo must stay private (PHI). Until upgraded, this layer is
   enforced by discipline — see `.agents/orchestration/PARALLEL_WORK_POLICY.md`
   ("Migration Merge Ordering"). Apply `infra/scripts/setup_main_ruleset.sh`
   once on GitHub Team to make it (and the full merge gate) server-enforced.
2. **CI single-head check — `make verify-alembic-heads`** (folded into
   `make verify`, plus a standalone step in `ci.yml`). Asserts exactly one
   alembic head. Offline: `alembic heads` reads the versions directory only,
   never connects to a DB. With layer 1 it turns the post-rebase double head
   into red CI **before** merge instead of on the prod deploy job.
3. **Deploy-time fail-closed stays as-is.** The prod alembic job must keep
   failing on multiple heads. Do **not** auto-merge heads in the deploy
   pipeline — a silent merge could hide a real ordering dependency between two
   migrations that touch the same table. Rejoining heads is a deliberate act:
   `cd packages/db && alembic merge heads -m 'merge <a>+<b>'`, after confirming
   the two parents are disjoint or encoding the correct order.

## 12. Agent Rule

Before changing deployment, env, secret, Cloud Run, OAuth URL, CORS, or CI/CD
behavior, agents must read this document and apply it directly. If a requested
change conflicts with these rules, stop and ask the user before implementing.

Agents should prefer repo scripts over raw `gcloud` commands. Raw `gcloud`
commands are acceptable for inspection (`describe`, `list`, `logs read`) and
for approved emergency recovery, but repeatable production changes must be
captured in scripts and docs before the work is considered complete.
