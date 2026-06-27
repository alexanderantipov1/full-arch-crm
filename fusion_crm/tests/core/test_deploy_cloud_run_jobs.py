from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "infra" / "scripts" / "deploy_cloud_run.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-prod.yml"


def test_salesforce_keepalive_cloud_run_job_is_wired() -> None:
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "JOB_SF_KEEPALIVE" in content
    assert "fusion-job-salesforce-token-keepalive" in content
    assert "SCHED_SF_KEEPALIVE" in content
    assert "fusion-sched-salesforce-token-keepalive" in content
    assert "refresh_salesforce_tokens" in content
    assert '"7 */6 * * *"' in content
    assert 'grant_job_invoker "$JOB_SF_KEEPALIVE" "$WORKER_EMAIL"' in content


def test_cloud_run_jobs_receive_required_settings_env() -> None:
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'JOB_ENV_VARS="APP_ENV=production,LOG_LEVEL=INFO,REDIS_URL=${REDIS_URL}"' in content


def test_integration_pull_cloud_run_jobs_are_enabled_by_default() -> None:
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'SCHEDULE_INTEGRATION_PULL="${SCHEDULE_INTEGRATION_PULL:-1}"' in content
    assert '"python" "-m,apps.worker.jobs.salesforce_pull"' in content
    assert '"python" "-m,apps.worker.jobs.carestack_pull"' in content
    assert 'upsert_scheduler "$SCHED_SF_PULL" "*/15 * * * *" "$JOB_SF_PULL"' in content
    assert 'upsert_scheduler "$SCHED_CS_PULL" "*/30 * * * *" "$JOB_CS_PULL"' in content


def test_carestack_procedure_codes_cloud_run_job_is_wired() -> None:
    """ENG-420 — the weekly catalog refresh Cloud Run Job and Scheduler
    entry are deployed by the same script and gated behind the shared
    ``SCHEDULE_INTEGRATION_PULL`` flag."""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Job name + scheduler name are configurable but default to the
    # production-locked spelling.
    assert "JOB_CS_PROCEDURE_CODES" in content
    assert "fusion-job-cs-procedure-codes" in content
    assert "SCHED_CS_PROCEDURE_CODES" in content
    assert "fusion-sched-cs-procedure-codes" in content

    # The deploy_job call invokes the Python entry point we ship.
    assert '"python" "-m,apps.worker.jobs.carestack_procedure_codes_pull"' in content

    # IAM: the worker SA gets run.invoker on the new job so the
    # scheduler can fire it.
    assert 'grant_job_invoker "$JOB_CS_PROCEDURE_CODES" "$WORKER_EMAIL"' in content

    # The scheduler entry is the weekly Monday 11:23 UTC cadence — the
    # CareStack CDT catalog updates annually, so weekly is generous and
    # off the busy */15 / */30 slots.
    assert (
        'upsert_scheduler "$SCHED_CS_PROCEDURE_CODES" "23 11 * * 1" '
        '"$JOB_CS_PROCEDURE_CODES"'
    ) in content


def test_worker_changes_rebuild_api_image_for_cloud_run_jobs() -> None:
    content = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "- 'apps/worker/**'" in content


def test_cloud_sql_private_ip_strips_gcloud_quotes() -> None:
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'tr -d "[]\'\\""' in content
