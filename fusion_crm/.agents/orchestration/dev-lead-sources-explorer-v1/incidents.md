# Incidents — dev-lead-sources-explorer-v1

(none yet)

- 2026-06-11 | ENG-400 | Correlated consultation subquery (tenant via Lead.tenant_id) re-executed per lead row and hung the explorer aggregates; uvicorn kept serving the stale hung version until PG backends (pids 930/966, 5+ min) were pg_terminate_backend'ed. Fix: bind tenant_id as a literal so the IN-subquery stays uncorrelated (0.15s). Lesson: never correlate tenant scoping of IN-subqueries through the outer row.

- 2026-06-12 | ENG-401 | Prod dup-cleanup executions (kb6xt, kwspp) terminate at the Cloud Run task timeout (10800s) before finishing the 1.6M-row dedup; batches commit so progress persists and each rerun resumes. kwspp cleared salesforce.task.upsert fully and died 30k/236k into opportunity.upsert. Mitigation: relaunch until clean. Consider a --task-timeout bump on fusion-job-backfill (deploy-contract change, DEPLOYMENT_RULES applies) if more reruns are needed.
