"""arq worker entry point.

Run locally: ``arq apps.worker.main.WorkerSettings``
Run via docker: see ``infra/docker/docker-compose.yml`` (service: worker)

All jobs receive an ``ctx`` dict from arq. We attach a fresh AsyncSession via
``packages.db.session.async_session()`` inside each job — never share sessions
across jobs.

Cron jobs:

- ``drain_outbound_queue`` (ENG-132) — every 10 seconds. Drains the
  ``outreach.outbound_queue`` table; sends through Gmail / Graph
  adapters. Per ADR-0004 decision #1 the schedule cadence is poll-
  driven; bumping cadence is fine — the row lock is held only briefly.

- ``poll_bounces`` (ENG-134) — every 15 minutes. For each active
  mailbox credential (Gmail / Graph), pulls the last 24h of NDR
  messages, matches by ``Message-ID``, marks the matched send as
  ``bounced`` and adds the recipient to ``outreach.suppression``
  with reason ``bounce_hard``. Provider push (Pub/Sub / Graph
  change-notifications) is out of scope for Stage 1 — we poll.
"""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from packages.core.config import get_settings
from packages.core.logging import configure_logging, get_logger

from .jobs.backfill_lead_identifiers import (  # ENG-542 one-shot identifier backfill
    backfill_lead_identifiers,
)
from .jobs.backup import run_backup
from .jobs.bounce_poll import poll_bounces
from .jobs.chat_inbound_map import map_chat_inbound  # ENG-438
from .jobs.consultation_reminders import scan_consultation_reminders  # ENG-486
from .jobs.email_send import drain_outbound_queue
from .jobs.example import process_unprocessed_events
from .jobs.fact_patient_journey_enablement import (  # ENG-510 — gated, on-demand only
    link_carestack_providers_for_all_tenants,
    link_carestack_providers_to_actors,
)
from .jobs.fact_patient_journey_refresh import (  # ENG-506 — gated, on-demand only
    refresh_fact_patient_journey,
    refresh_fact_patient_journey_for_all_tenants,
)
from .jobs.ingest_scheduled import (  # ENG-222
    backfill_carestack_for_tenant,  # ENG-351
    ingest_scheduled_fanout,
    pull_carestack_for_tenant,
    pull_salesforce_for_tenant,
    refresh_carestack_schemas_for_all_tenants,  # ENG-429
    refresh_carestack_schemas_for_tenant,  # ENG-429
    refresh_salesforce_schemas_for_all_tenants,  # ENG-428
    refresh_salesforce_schemas_for_tenant,  # ENG-428
)
from .jobs.marketing_backfill import (  # ENG-492 one-shot historical backfill
    backfill_marketing_history,
)
from .jobs.marketing_pull import (  # marketing ad-spend + web analytics
    pull_ga4_for_tenant,
    pull_google_ads_for_tenant,
    pull_gsc_for_tenant,
    pull_marketing_for_all_tenants,
    pull_meta_ads_ads_for_tenant,
    pull_meta_ads_for_tenant,
)
from .jobs.notification_dispatch import drain_notification_outbox  # ENG-436
from .jobs.replay_identity_matches import (  # ENG-544 one-shot replay/dedup-merge
    replay_identity_matches,
)
from .jobs.salesforce_token_keepalive import (
    refresh_salesforce_token_for_tenant,
    refresh_salesforce_tokens,
)
from .jobs.shared_contact_reuse import scan_shared_contact_reuse  # ENG-555

log = get_logger("worker")


async def startup(_ctx: dict) -> None:
    configure_logging()
    log.info("worker.start")


async def shutdown(_ctx: dict) -> None:
    log.info("worker.stop")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(str(get_settings().redis_url))


class WorkerSettings:
    """arq picks this up via ``arq apps.worker.main.WorkerSettings``."""

    redis_settings = _redis_settings()
    functions = [
        run_backup,
        process_unprocessed_events,
        drain_outbound_queue,
        drain_notification_outbox,
        scan_consultation_reminders,
        scan_shared_contact_reuse,
        map_chat_inbound,
        poll_bounces,
        ingest_scheduled_fanout,
        pull_carestack_for_tenant,
        backfill_carestack_for_tenant,
        pull_salesforce_for_tenant,
        refresh_carestack_schemas_for_all_tenants,
        refresh_carestack_schemas_for_tenant,
        refresh_salesforce_schemas_for_all_tenants,
        refresh_salesforce_schemas_for_tenant,
        refresh_salesforce_tokens,
        refresh_salesforce_token_for_tenant,
        pull_marketing_for_all_tenants,
        pull_google_ads_for_tenant,
        pull_meta_ads_for_tenant,
        pull_meta_ads_ads_for_tenant,
        pull_ga4_for_tenant,
        pull_gsc_for_tenant,
        # ENG-492: one-shot historical backfill. On-demand only — NO cron entry
        # (the daily rolling pull above is the recurring job).
        backfill_marketing_history,
        # ENG-542: one-shot lead-person identifier backfill from hints.
        # On-demand only — NO cron entry; idempotent + collision-safe.
        backfill_lead_identifiers,
        # ENG-544: one-shot replay of open match candidates under the current
        # (ENG-543) policy + dedup-merge. On-demand only — NO cron entry.
        # dry_run defaults to True; the live pass is operator-enqueued.
        replay_identity_matches,
        # ENG-506: analytics fact_patient_journey refresh. Gated OFF — registered
        # for on-demand enqueue only, NO cron entry (the analytics read-model is
        # rebuilt deliberately, never on a silent prod schedule).
        refresh_fact_patient_journey,
        refresh_fact_patient_journey_for_all_tenants,
        # ENG-510: B1 enablement — link CareStack providers → actors (doctor
        # dimension). Same gated, on-demand-only posture as the refresh above.
        link_carestack_providers_to_actors,
        link_carestack_providers_for_all_tenants,
    ]
    cron_jobs = [
        # Poll the outbound queue every 10 s. The drain pass is cheap
        # when the queue is empty (one indexed SELECT) and bounded by
        # BATCH_SIZE when it's not.
        cron(
            drain_outbound_queue,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=False,
            unique=False,
        ),
        # ENG-436: drain the notification outbox every 10 s, offset from
        # the email dispatcher's {0,10,...} so the two drains do not
        # contend for the same tick. Cheap when empty (one partial-index
        # SELECT) and bounded by BATCH_SIZE when busy.
        cron(
            drain_notification_outbox,
            second={5, 15, 25, 35, 45, 55},
            run_at_startup=False,
            unique=False,
        ),
        # ENG-438: map captured Mattermost inbound raw events → actors
        # every 10 s, offset to {8,18,...} so it does not contend with the
        # email drain ({0,10,...}) or the notification drain ({5,15,...}).
        # Cheap when empty (one indexed unprocessed SELECT). Deep domain
        # mapping (annotations / HITL) is deferred to Block F/G.
        cron(
            map_chat_inbound,
            second={8, 18, 28, 38, 48, 58},
            run_at_startup=False,
            unique=False,
        ),
        # ENG-486: scan for CONFIRMED consultations starting within 15 min and
        # post a T-15m reminder. Fires once a minute at :02 (off the {0,10,...}
        # / {5,15,...} / {8,18,...} drains). At-most-once is guaranteed by the
        # dedupe ledger (key = consultation id), so unique=True is enough to
        # avoid two workers double-scanning the same minute. Cheap when empty
        # (one indexed SELECT per tenant).
        cron(
            scan_consultation_reminders,
            second={2},
            run_at_startup=False,
            unique=True,
        ),
        # ENG-555: shared-contact-reuse alert scan. Local dev / docker compose
        # only — prod runs it as a Cloud Run Job + Scheduler (ENG-172), see
        # ``shared_contact_reuse_scan.py``. Every 5 min; the scan is a cheap
        # cutoff-bounded indexed SELECT per tenant and is a no-op until
        # NOTIFICATIONS_CUTOFF_AT + NOTIFICATIONS_ENABLED are set. At-most-once
        # via the dedupe ledger (key = candidate id), so unique=True is enough.
        cron(
            scan_shared_contact_reuse,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            second=7,
            run_at_startup=False,
            unique=True,
        ),
        # Poll inbound NDRs every 15 minutes. The poller iterates
        # every active mailbox credential per tenant; the cost scales
        # with mailbox count, not user count. ``unique=True`` so two
        # workers do not duplicate the same poll tick.
        cron(
            poll_bounces,
            minute={0, 15, 30, 45},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
        # ENG-222: scheduled CareStack + Salesforce ingestion. Fires
        # every hour at :13. Per-tenant pull is idempotent on its
        # natural key so overlapping ticks no-op safely. Production
        # uses Cloud Scheduler (SF every 15min, CS every 30min);
        # this arq cron covers local dev and docker compose.
        cron(
            ingest_scheduled_fanout,
            minute={13},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
        # ENG-233: proactively refresh Salesforce OAuth access tokens so
        # idle connections stay warm. ``invalid_grant`` is marked expired
        # by the job and surfaced as reconnect-needed in the integrations UI.
        cron(
            refresh_salesforce_tokens,
            hour={0, 6, 12, 18},
            minute={7},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
        # ENG-428: refresh the Salesforce schema registry once a day at
        # 04:23. Cheap (one describe + one Tooling query per object) and
        # low-cadence by design — newly-added SF fields are detected and
        # absorbed into the next pull. Production runs it via Cloud
        # Scheduler; this arq cron covers local dev / docker compose.
        cron(
            refresh_salesforce_schemas_for_all_tenants,
            hour={4},
            minute={23},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
        # ENG-429: snapshot the CareStack schema registry from observed
        # payload keys once a day at 04:33. Reads our own raw events only —
        # no CareStack HTTP — so it is cheap and credential-free.
        cron(
            refresh_carestack_schemas_for_all_tenants,
            hour={4},
            minute={33},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
        # Marketing ad-spend pull. Ad data has ~1-day latency, so a daily
        # cadence is enough; the pull re-reads a rolling 7-day window and
        # dedupes on captured-payload identity. Fires at 04:43, after the
        # schema-registry refreshes. Production runs it via Cloud Scheduler;
        # this arq cron covers local dev / docker compose.
        cron(
            pull_marketing_for_all_tenants,
            hour={4},
            minute={43},
            second=0,
            run_at_startup=False,
            unique=True,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = get_settings().worker_concurrency
    job_timeout = 60 * 30  # 30m — backups can be long
    keep_result = 60 * 60  # 1h
