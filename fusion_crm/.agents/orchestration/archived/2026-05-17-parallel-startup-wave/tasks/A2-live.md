# Terminal Agent Task Brief

Task ID: A2-live
Linear issue: ENG-178 / ENG-180
Agent role: Claude Code explorer
Mission folder: `.agents/orchestration/20260517-113000-parallel-startup-wave`
Report path: `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/A2-live.md`
Branch: read-only
Worktree: primary repo

## Objective

Collect live read-only evidence for the latest failed `deploy-prod.yml` run, especially run `25982799094`, and identify the real blocker for ENG-178 / ENG-180 acceptance.

## Context

Read first:
- Root `CLAUDE.md`
- `.github/CLAUDE.md`
- `docs/DEPLOYMENT_RULES.md`
- Mission `contract.md`
- Mission `ownership.md`
- Prior report: `.agents/orchestration/20260517-103524-eng-178-eng-180-deploy-smoke-recovery/reports/A2.md`

Known context:
- ENG-178 acceptance is not complete.
- ENG-180 pinned `IAP_OAUTH_CLIENT_ID` landed on `main`, but deploy-prod is still red.
- The latest known failed deploy-prod run is `25982799094`.
- A1 in the deploy-smoke mission restored future smoke diagnostics, but this task investigates the existing failed run and available Cloud logs.

## Ownership

Allowed write scope:
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/A2-live.md`

Allowed read scope:
- Repository files.
- GitHub Actions run metadata/logs using read-only `gh run list/view` and narrow Actions `gh api` if needed.
- Cloud Logging via `gcloud logging read`.
- Cloud Run service/revision describe/list commands.

Do not touch:
- Source files.
- Linear issue state.
- GitHub workflow rerun/dispatch/cancel/approval.
- Cloud Run service/job/traffic/env/secrets/IAM state.
- `.env*`, secrets, or production config.

## Suggested Commands

Use only read-only commands. Start with:

```bash
gh run view 25982799094 --json conclusion,status,createdAt,updatedAt,headSha,event,url
gh run view 25982799094 --log
```

Then inspect nearby runs if needed:

```bash
gh run list --workflow deploy-prod.yml --branch main --limit 10
```

For Cloud Logging, use timestamps from the run:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="fusion-api" AND timestamp>="<failure_iso>"' --project fusioncrm-494201 --limit=200 --order=desc --format=json
gcloud logging read 'resource.type="http_load_balancer" AND resource.labels.url_map_name="fusion-lb-url-map" AND timestamp>="<failure_iso>"' --project fusioncrm-494201 --limit=200 --order=desc --format=json
```

Sanitize all output. Do not include secrets, tokens, service-account JSON, PHI, OAuth secrets, or tenant credential payloads.

## Questions To Answer

- Which job/step failed in run `25982799094`?
- What commit SHA and Cloud Run revision were involved?
- Did token minting and pinned IAP audience work?
- Did the smoke reach `/healthz`, and if yes, what failure class is visible?
- Which Cloud Logging filter actually returns relevant logs?
- Is ENG-180 blocked only by ENG-178 smoke acceptance, or is there a remaining audience/client-id issue?

## Stop Conditions

Stop and report if:
- A command would mutate GitHub or Google Cloud state.
- Access is denied.
- Logs contain sensitive material that cannot be safely summarized.

## Required Report

Use `reports/TEMPLATE.md`. Include commands run, run IDs, timestamps, sanitized findings, blockers, and suggested next tasks.
