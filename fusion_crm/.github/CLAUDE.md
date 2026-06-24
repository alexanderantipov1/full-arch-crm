# CLAUDE.md — `.github/` (GitHub Actions workflows)

> This is the CI/CD surface for Fusion CRM. Per ADR-0002, all
> production deploys flow through `deploy-prod.yml`; manual recovery
> goes through `deploy-prod-rollback.yml`. There is no other deploy
> path. **Do not** add a workflow that pushes to Artifact Registry or
> calls `gcloud run deploy` outside these two files without an ADR.

Before changing production deployment workflow behavior, read and
follow `docs/DEPLOYMENT_RULES.md`. GitHub Actions must not drift from
the canonical deploy script's service account, VPC, ingress, auth,
resource, env var, or secret contract.
The workflow should pass inputs to repo scripts, not maintain a
separate Google Cloud deployment implementation in YAML.

## Files

- **`workflows/deploy-prod.yml`** — forward deploy, push-to-`main`.
- **`workflows/deploy-prod-rollback.yml`** — `workflow_dispatch`
  rollback, one service at a time, requires the `ROLLBACK` confirm
  token.

## Auth model (hard rule: WIF only)

Per ADR-0001 and ADR-0002, **no service-account JSON key ever
touches a CI runner**. Authentication uses Workload Identity
Federation:

```
GitHub OIDC token (assertion.repository = alexanderantipov1/fusion_crm)
    | google-github-actions/auth@v2
WIF provider (projects/800777477533/locations/global/
              workloadIdentityPools/github-actions/providers/github)
    | impersonates
cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com
    | has
roles/artifactregistry.writer
roles/run.admin
roles/iam.serviceAccountUser
    | may impersonate
fusion-api-sa / fusion-worker-sa (runtime SAs, narrower scope)
```

The WIF pool + provider + bindings are provisioned by
`infra/scripts/provision_cloud_run_foundation.sh` (ENG-114). The
provider's `attribute.repository` condition is pinned to
`alexanderantipov1/fusion_crm`; no other repo (and no fork) can
mint tokens against the pool even if they steal a workflow file.

The workflow declares `permissions: id-token: write` on the
top-level so `google-github-actions/auth@v2` can request the OIDC
JWT. **Do not remove this line.**

## Forward deploy — `deploy-prod.yml`

Trigger: every push to `main`. The shape is:

```
verify (python: lint + typecheck + tests)
   |
   +-- detect-changes (paths-filter -> api / web / worker booleans)
   +-- auth (WIF preflight, fails fast if the OIDC binding is broken)
   +-- build-api    (only if apps/api/** or packages/** changed)
   +-- build-web    (only if apps/web/** changed)
   +-- build-worker (only if apps/worker/** or packages/** changed)
   |
   +-- alembic-migrate (one-shot Cloud Run Job; gates deploys)
          |
          +-- deploy-api    (--no-traffic, then --to-latest)
          +-- deploy-web    (--no-traffic, then --to-latest)
          +-- deploy-worker (--no-traffic, then --to-latest)
                 |
                 +-- post-deploy-comment (commit comment on github.sha)
```

Key behaviours:

- **`verify` is required.** It runs `make verify` (ruff + mypy +
  pytest). If it fails, `alembic-migrate` is skipped, and no service
  deploys.
- **`alembic-migrate` is the critical data-safety gate.** It
  retargets the pre-provisioned `fusion-job-alembic-upgrade`
  Cloud Run Job to the freshly built API image (falling back to
  `:latest` if `apps/api` did not change this push) and runs it
  with `--wait`. Non-zero exit fails the workflow and blocks every
  `deploy-*` job downstream.
- **`--no-traffic` then `--to-latest`** is the zero-downtime path:
  the new revision must report healthy before any user traffic
  reaches it. Cloud Run's built-in health probes are the gate; we
  do not add an extra polling step.
- **Path-filtered builds** keep CI fast. If you push a docs-only
  change, all three build jobs are skipped (and the alembic gate
  is too, since there's nothing to migrate against). The
  workflow_dispatch input `force_rebuild_all=true` overrides this
  for emergencies.
- **`environment: production`** is set on every job that mints a
  WIF token. The operator can require manual approval per
  environment, which is the recommended setting for the first few
  deploys after this workflow lands.

### Workflow inputs

| Trigger | Input | Default | Use |
|---------|-------|---------|-----|
| `push` to `main` | — | — | normal post-merge deploy |
| `workflow_dispatch` | `force_rebuild_all` | `false` | rebuild all three services even if their source did not change |

### Environment variables (workflow-level)

| Name | Value | Source |
|---|---|---|
| `PROJECT_ID` | `fusioncrm-494201` | ADR-0001 |
| `PROJECT_NUMBER` | `800777477533` | `gcloud projects describe` (ENG-114) |
| `REGION` | `us-west1` | ADR-0001/2 |
| `ARTIFACT_REPO` | `fusion-containers` | ENG-114 |
| `ARTIFACT_HOST` | `us-west1-docker.pkg.dev` | ENG-114 |
| `DEPLOYER_SA` | `cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com` | ENG-114 |
| `WIF_PROVIDER` | `projects/800777477533/locations/global/workloadIdentityPools/github-actions/providers/github` | ENG-114 |
| `ALEMBIC_JOB` | `fusion-job-alembic-upgrade` | ENG-115 (provisioned, retargeted here) |
| `API_SERVICE` / `WEB_SERVICE` | `fusion-api` / `fusion-web` | ENG-115 (worker Service decommissioned in ENG-172) |

All values are non-secret. Secrets are accessed only at runtime by
the Cloud Run service via Secret Manager (`gcp-secret://...`); the
CI workflow never reads them.

## Rollback — `deploy-prod-rollback.yml`

When a freshly promoted revision misbehaves and you need traffic
back on the previous one:

1. Find the target revision in Cloud Console -> Cloud Run -> service
   -> "Revisions" tab. Copy the full name (e.g.
   `fusion-api-00042-abc`).
2. Open GitHub Actions -> "deploy-prod-rollback" -> "Run workflow".
3. Pick `service` (`api` / `web` / `worker`), paste the
   `revision`, and type `ROLLBACK` (case-sensitive) in `confirm`.
4. The workflow:
   - Sanity-checks the revision exists.
   - Routes 100% of traffic to it (`gcloud run services
     update-traffic ... --to-revisions=<rev>=100`).
   - Prints the resulting traffic split.

The bad revision is **not deleted** — it stays as a Cloud Run
revision so a forward-fix can rebase from it. Delete only after
the incident review.

### CLI equivalent

```bash
gcloud run services update-traffic fusion-api \
  --to-revisions=fusion-api-00042-abc=100 \
  --region=us-west1 \
  --project=fusioncrm-494201
```

`workflow_dispatch` exists because the operator may not have
`gcloud` configured on whichever machine they happen to be on
during an incident. Both paths are first-class.

## Adding a new service

1. Provision the Cloud Run service in ENG-115's deploy scripts
   (runtime SA, VPC connector, env vars, secrets).
2. Add the service's image name to `env:` (e.g. `NOTIFIER_SERVICE:
   fusion-notifier`).
3. Add a `detect-changes` path filter for the source directory.
4. Mirror the existing `build-*` and `deploy-*` blocks. Keep the
   `--no-traffic` then `--to-latest` shape.
5. Add the service row to the `post-deploy-comment` markdown table.
6. Add a `service` choice to `deploy-prod-rollback.yml` and extend
   the `case` in "Resolve Cloud Run service name".
7. Update this file's service list.

## Granting a new repo branch deploy rights

The WIF provider currently restricts to
`assertion.repository == "alexanderantipov1/fusion_crm"`. The
attribute mapping also exposes `attribute.ref`, so you can layer
additional bindings on the deployer SA without touching the
provider itself:

```bash
# Allow workflows running on a long-lived release branch to deploy:
gcloud iam service-accounts add-iam-policy-binding \
  cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/800777477533/locations/global/workloadIdentityPools/github-actions/attribute.ref/refs/heads/release/v1"
```

The repo-wide binding created by the foundation script (`principalSet
.../attribute.repository/alexanderantipov1/fusion_crm`) is broader
and covers every branch and PR by default — only narrow it if the
operator explicitly asks. For PR builds that should NOT have
deploy rights, prefer (a) keeping the broad binding but (b)
gating the `production` GitHub environment with manual approval,
which is the model in use today.

## Forbidden patterns

- Writing a service account JSON key to the runner (`echo
  $SA_KEY > sa.json`).
- Re-implementing production Cloud Run deploy flags in workflow YAML
  when the canonical deploy script can be called instead.
- Leaving GitHub Actions with a different deploy path than operators
  use from the CLI.
- Calling `gcloud run deploy` outside `deploy-prod.yml` /
  `deploy-prod-rollback.yml`.
- Running `alembic upgrade head` inside the API container's
  startup command — migrations are operator-driven (or here,
  workflow-driven via a one-shot Cloud Run Job), never on boot.
  See `infra/CLAUDE.md` and root `CLAUDE.md` for the underlying
  rule.
- Promoting a Cloud Run revision without going through
  `--no-traffic` first. Even hotfixes go through the
  no-traffic -> promote handshake.
- Storing PHI, patient names, DOB, etc. in workflow logs. Only
  identifiers, action codes, request ids are allowed — same rule
  as application logging.

## Troubleshooting

- **`Permission 'iam.serviceAccounts.getAccessToken' denied`** —
  WIF binding lost or the `attribute.repository` condition does
  not match. Re-run
  `infra/scripts/provision_cloud_run_foundation.sh` — it
  re-applies the binding idempotently.
- **`docker push` returns 403** — runner did not run `gcloud auth
  configure-docker us-west1-docker.pkg.dev`. Each `build-*` job
  re-auths from scratch; check the step ran.
- **`gcloud run jobs execute` exits non-zero** — open the Cloud
  Run Job logs in Cloud Console; the alembic stack trace is
  there. The forward workflow stops here on purpose — fix the
  migration, push a new commit. Never re-run a "skip migration"
  variant of the workflow.
- **`paths-filter` says nothing changed but you expected a
  rebuild** — the action diffs against the previous tip of
  `main`. If the previous tip is missing (very deep `fetch-depth`
  pruning or a force-push), it falls back to the merge-base, which
  can over-include. Use `workflow_dispatch` +
  `force_rebuild_all=true` to bypass.
- **Deploy completes but traffic still goes to the old
  revision** — Cloud Run only auto-promotes when
  `update-traffic --to-latest` runs. Check the job log for that
  step; if the no-traffic deploy succeeded but the promote step
  is missing or skipped, run the rollback workflow with the new
  revision name to force the split.
