# CLAUDE.md — `packages/audit`

Append-only access log. The HIPAA accountability surface.

## Table (schema `audit`)

- **`access_log`** — one row per audited action. Indexed by
  `principal_id`, `person_uid`, `action`.
- **`agent_runtime_run`** — safe summary rows for agent runtime executions.
  This is not a trace store and must not contain prompts, secrets, raw provider
  payloads, PHI, raw SQL, or unmasked row-level data.
- **`agent_runtime_approval_request`** — safe human approval boundary rows for
  agent-proposed actions. These rows record review posture and human decisions,
  not downstream business truth or sensitive payloads.

## Service surface

`AuditService` exposes:

- `record_phi_access(...)` — used by `PhiService` on every read/write.
- `record_tool_call(...)` — used by `packages.tools.*` on every call.
- `record(...)` — generic; used by API middleware and ad-hoc paths.
- `log_oauth_event(...)` — used by `packages.integrations.*` for
  OAuth lifecycle events (`connect`, `refresh`, `revoke`, `error`).
- `log_sync_run_summary(...)` — used by sync workers when an
  `integrations.sync_run` row terminates.

## Hard rules

- **Append-only.** Never `UPDATE` or `DELETE` an `access_log` row in
  application code. In production the DB role does not have those
  privileges; do not work around it.
- **Best-effort writes are NOT acceptable for PHI access.** If a PHI
  audit row fails to insert, the user-facing operation must fail too.
  Today both are inside the same UoW — keep them together.
- **No PII bloat.** Store `principal_id`, `principal_email`,
  `person_uid`, `action`, `reason`, and a small `extra` dict. Do not
  dump request bodies in here.
- **`action` is a stable taxonomy**, not free text. Use dotted names:
  `phi.snapshot`, `phi.profile.upsert`, `tool.resolve_person`,
  `tool.invoke.<name>`. Adding a new action → add it to the taxonomy
  table below.

## Action taxonomy (current)

| action                                  | written by                                       |
|-----------------------------------------|--------------------------------------------------|
| `phi.snapshot`                          | `PhiService.snapshot`                            |
| `phi.profile.upsert`                    | `PhiService.upsert_profile`                      |
| `tool.<name>`                           | individual tool functions                        |
| `tool.invoke.<name>`                    | `POST /tools/call` middleware                    |
| `oauth.connect`                         | `AuditService.log_oauth_event`                   |
| `oauth.refresh`                         | `AuditService.log_oauth_event`                   |
| `oauth.revoke`                          | `AuditService.log_oauth_event`                   |
| `oauth.error`                           | `AuditService.log_oauth_event`                   |
| `integrations.sync_run.complete`        | `AuditService.log_sync_run_summary`              |
| `identity.identifier.backfill`          | `IngestService.backfill_lead_person_identifiers` |
| `tenant.create`                         | `TenantService.create_tenant`                    |
| `tenant.setting.upsert`                 | `TenantService.upsert_setting`                   |
| `tenant.credential.record`              | `TenantService.record_credential`                |
| `tenant.credential.revoke`              | `TenantService.revoke_credential`                |
| `tenant.location.create`                | `LocationService.upsert_location`                |
| `tenant.location.update`                | `LocationService.upsert_location`                |
| `tenant.location.upsert_from_carestack` | `LocationService.import_locations_from_carestack`|
| `outreach.template.create`              | `TemplateService.create_template`                |
| `outreach.template.update`              | `TemplateService.update_template`                |
| `outreach.template.archive`             | `TemplateService.delete_template`                |
| `outreach.template.render`              | `TemplateService.render`                         |
| `outreach.template.merge_field_unknown` | `TemplateService.render`                         |
| `outreach.campaign.create`              | `CampaignService.create_campaign`                |
| `outreach.suppression.add`              | `SuppressionService.add_suppression`             |
| `outreach.suppression.remove`           | `SuppressionService.remove_suppression`          |
| `outreach.mailbox.routed`               | `PickMailboxService.pick` (ENG-132)              |
| `outreach.send.enqueued`                | `SendService.enqueue_*` (ENG-132)                |
| `outreach.email.sent`                   | dispatcher worker on success (ENG-132)           |
| `outreach.email.failed`                 | dispatcher worker on permanent/exhausted (ENG-132)|
| `outreach.email.rate_limited`           | dispatcher worker on RL deferral (ENG-132)       |
| `outreach.email.suppressed`             | enqueue + dispatcher (ENG-132)                   |
| `outreach.email.opened`                 | tracking pixel endpoint (ENG-134)                |
| `outreach.email.unsubscribed`           | one-click unsubscribe endpoint (ENG-134)         |
| `outreach.email.bounced`                | bounce poller worker (ENG-134)                   |
| `semantic_catalog.review.approve`       | `AuditService.log_catalog_review_action`         |
| `semantic_catalog.review.edit`          | `AuditService.log_catalog_review_action`         |
| `semantic_catalog.review.reject`        | `AuditService.log_catalog_review_action`         |
| `semantic_catalog.review.unresolved`    | `AuditService.log_catalog_review_action`         |
| `semantic_catalog.version.change`       | `AuditService.log_catalog_version_change`        |
| `integrations.notification.enqueued`    | `NotificationService.enqueue` (ENG-436)          |
| `integrations.notification.rule.create` | `NotificationService.upsert_rule` insert (ENG-436)|
| `integrations.notification.rule.update` | `NotificationService.upsert_rule` update (ENG-436)|
| `notification.dispatch.sent`            | `drain_notification_outbox` on success (ENG-436) |
| `notification.dispatch.failed`          | `drain_notification_outbox` on failure (ENG-436) |
| `enrichment.annotation.add`             | `EnrichmentService.add_annotation` (ENG-439)     |
| `agent.action.proposed`                 | `AgentActionService.propose` (ENG-440)           |
| `agent.action.decided`                  | `AgentActionService.record_decision` (ENG-440)   |
| `agent.action.executed`                 | `AgentActionService.mark_executed` (ENG-440)     |
| `agent.action.failed`                   | `AgentActionService.{mark_failed,propose}` (ENG-440)|

`log_oauth_event` puts `provider`, `account_id`, and `outcome` into
`extra`; `log_sync_run_summary` puts `provider`, `sync_run_id`,
`outcome` (`success`, `partial`, `failure`, or `skipped_credential`),
and the `entity_kind` / `item_count` / `error_count` counters when
supplied.

Outreach actions write `tenant_id`, `template_id` (or `campaign_id`),
and outcome counters (`unknown_field_count`, `empty_subject`,
`changed`) into `extra`. They NEVER write rendered subject or body
content — body protection is enforced at code-review time.

ENG-132 send-pipeline rows additionally carry `credential_id`,
`recipient_hash` (HMAC-SHA256 of normalised recipient under
`INTERNAL_CREDENTIAL_TOKEN`, truncated to 64 bits), `provider_kind`,
and result-shape metadata (`has_message_id`, `status_code`,
`reason`). Raw recipient addresses NEVER appear in `extra`.

ENG-134 tracking rows (`outreach.email.opened`,
`outreach.email.unsubscribed`, `outreach.email.bounced`) carry
`send_id` + `credential_id` + outcome metadata (`match_strategy`,
`source`) — no recipient plaintext. The bounce row additionally
includes `recipient_hash` so an investigator can correlate the
bounce with the preceding ENG-132 send-attempt audit row without
re-deriving the hash. Tokens used by the open / unsubscribe routes
(HMAC-SHA256 namespaced by `"open:"` / `"unsubscribe:"`) reuse
`INTERNAL_CREDENTIAL_TOKEN` and never appear in `extra`.

Semantic catalog review rows carry proposal/catalog version IDs, review action,
target status, changed field names, affected analytics IDs, and short change
summaries/reasons. They never carry raw source values, raw provider payloads,
reviewer notes, secrets, or plaintext PII-like fields; helper-level redaction
replaces sensitive `extra` keys before insert.

Agent HITL rows (`agent.action.proposed` / `.decided` / `.executed` /
`.failed`; ENG-440, Block G) carry ONLY identifiers and outcome metadata in
`extra`: `tenant_id`, `proposal_id`, `proposal_ref`, `kind`, `channel`,
`decision`, `posted`, `actor_id`, and an `error_type` enum (e.g.
`post_failed`, `execution_error`). They NEVER carry the bound annotation
`value`, free-text notes, the rendered card body, the inbound token, or any
PII / payload value — the proposal `payload.value` (which may hold free text /
PII) never enters the audit row.

Messenger-layer rows (`integrations.notification.*`,
`notification.dispatch.*`; ENG-436, ADR-0006) carry `tenant_id`, the
outbox/rule row id, `event_type`, and dispatch outcome metadata. They NEVER
carry rendered message bodies — de-identification at render time
(`packages/integrations/chat/render.py`, `phi_mode="deidentified"` default)
keeps PHI out of the chat post, and the audit row stays metadata-only. Note:
the renderer's `notification.render.redacted_variable` is a structlog WARNING
key (it logs the redacted variable name, never the value), not an
`access_log` action.

Add a row when you introduce a new audited operation.
