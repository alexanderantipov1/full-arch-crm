# Shared Contract

## Purpose

- Coordinate deploy-prod smoke stabilization without allowing agents to mutate production state or mix unrelated product changes.

## API Contract

- Public smoke base URL remains `https://fusioncrm.app/api`.
- Deep smoke endpoints remain:
  - `GET /healthz`, expected HTTP 200 and JSON `commit_sha == github.sha`.
  - `GET /readyz`, expected HTTP 200.
  - `GET /dashboard/summary`, expected HTTP 200.
  - `GET /integrations`, expected HTTP 200 and at least two items.
- The smoke token audience remains the pinned `IAP_OAUTH_CLIENT_ID` workflow environment value unless a later orchestrator-approved contract change says otherwise.
- API error envelope rules are unchanged.

## Data / Schema Contract

- No database schema or migration changes are in scope.
- No app data mutation is in scope.
- Cloud Run logs may be read; Cloud Run services, jobs, traffic, secrets, and env vars must not be changed.

## UI / UX Contract

- No frontend/UI changes are in scope.

## Acceptance Criteria

- Workflow diagnostics:
  - Any smoke failure message emitted by `fail()` is visible in GitHub Actions logs.
  - HTTP status and first body lines emitted by `check()` are visible in GitHub Actions logs when a check fails inside `BODY=$(check ...)`.
  - Successful `check()` calls still return only the response body on stdout so `BODY=...` and JSON parsing keep working.
- ENG-178:
  - Not accepted until a deploy-prod run proves the smoke endpoints pass through the public LB/IAP path and `/healthz.commit_sha` matches `github.sha`.
- ENG-180:
  - Not accepted until the pinned IAP OAuth client ID audience participates in a green deploy-prod run.

## Non-Negotiable Constraints

- Do not change this contract inside a worker task.
- If the contract is incomplete or wrong, stop and report to the orchestrator.
- Do not log secrets, tokens, PHI, service account JSON, OAuth secrets, or tenant credential payloads.
- Do not change production traffic, deploy services, roll back, push branches, or close Linear issues from worker tasks.
