# CLAUDE.md — `packages/outreach`

Operator-account email outreach. Per
`docs/decisions/ADR-0004-operator-account-email-outreach.md` and the
ENG-132 / ENG-133 / ENG-134 specs.

## Tables (schema `outreach`)

- **`template`** — operator-edited Mustache+MJML email templates.
  Versioned (`version` int monotonic), categorised (`category ∈
  {marketing, clinical, transactional, operational}`), and gated for
  tracking (`tracking_enabled boolean`, default false; permitted
  `true` only when `category = 'marketing'`). `body_format ∈
  {markdown, mjml}` is the Stage 1 surface — `html` is enum-reserved
  but rejected at the service layer.
  UNIQUE `(tenant_id, name)`.
- **`campaign`** — a scheduled or immediate batch send referencing one
  template + one mailbox credential (or `auto_route`). The full
  enqueue + dispatcher pipeline lives in ENG-132.
- **`send`** — one row per recipient per campaign; the durable source
  of truth for "what we attempted to send and what happened". Indexed
  on `(campaign_id, status)` and `(tenant_id, recipient_email)`.
  `campaign_id` is NULLABLE as of ENG-132 (migration `d7e9f5b3c1a8`)
  so transactional sends via `SendService.enqueue_single` can land
  without a campaign row.
- **`suppression`** — per-tenant unsubscribe / bounce list. Composite
  PK `(tenant_id, recipient_email_normalised)` so a recipient
  suppressed for tenant A is NOT suppressed for tenant B.
- **`outbound_queue`** — Postgres-backed work queue for the
  `outreach.dispatcher` arq worker (ADR-0004 decision #1). Indexed
  partial on `(status, scheduled_for) WHERE status = 'pending'` so the
  worker's `SELECT … FOR UPDATE SKIP LOCKED` pull stays cheap.

Tenant scoping: every per-tenant row carries a `tenant_id UUID NOT
NULL` cross-schema FK to `tenant.tenant.id`. Repositories take
`tenant_id` first and filter every read on it.

## Service surface

- **`TemplateService`** — `create_template`, `update_template` (bumps
  `version` on actual change), `delete_template` (soft via
  `status='archived'`), `render` (composes a `PersonRenderContext`
  from identity + ops, calls the renderer, audits), `validate`
  (dry-run for the operator UI; informational, no audit row).
- **`CampaignService`** — `create_campaign`,
  `preview_recipient_query` (returns the first N matches for the UI
  preview pane). The full enqueue + send pipeline lives in ENG-132.
- **`SuppressionService`** — `add_suppression`, `is_suppressed`,
  `remove_suppression`, `list_for_tenant` (ENG-134, paginated). The
  send service calls `is_suppressed` before enqueuing; tracking +
  bounce handlers call `add_suppression`; operator UI calls
  `remove_suppression` + `list_for_tenant`.
- **`PickMailboxService`** (ENG-132, in `send_service.py`) — resolves
  which mailbox credential to use. Routing order: location+tag → tag
  → provider_hint+default → default → `NoMailboxAvailable`. Filters
  to `provider_kind in {google_workspace, microsoft_365}` only. Audit
  every pick with `strategy_step`.
- **`SendService`** (ENG-132, in `send_service.py`) — enqueue surface.
  `enqueue_campaign` materialises send + outbound_queue rows for a
  campaign; `enqueue_single` writes one transactional send (campaign-
  less). Neither calls a provider — the worker drains the queue.

## Send pipeline (ENG-132)

The operator-account send pipeline lives across three layers:

1. **`packages.outreach.email_builder`** — `build_rfc822(...)`
   produces RFC 5322 bytes from rendered subject/body, with
   `multipart/alternative` + RFC 8058 one-click unsubscribe headers.
   ENG-134 adds an optional `tracking_pixel_url` parameter — when
   supplied (the dispatcher only passes it when
   `template.tracking_enabled = true`), the builder appends a 1x1
   `<img>` tag at the end of `body_html`. Stdlib only.
2. **`packages.outreach.rate_limiter`** — `RateLimiter` Redis
   sliding-window counter per `(credential_id, window_seconds)`.
   Default policy: Gmail 2 000/day; MS Graph 10 000/day + 30/minute.
   Tenant overrides come from `tenant.setting` key
   `outreach.rate_limits.<provider_kind>`.
3. **`packages.integrations.<provider>.send`** — `GmailSendAdapter`
   / `GraphSendAdapter` wrap the provider clients and translate
   provider errors into a shared taxonomy (`RateLimitError`,
   `TransientError`, `PermanentError`, `SendResult`). The outreach
   service never imports adapters directly — the worker does.

The dispatcher (`apps.worker.jobs.email_send.drain_outbound_queue`)
runs every 10 s via `cron`, pulls with `FOR UPDATE SKIP LOCKED`,
resolves the credential + adapter, gates on the rate limiter,
checks suppression, renders, mints HMAC tokens for the per-send
unsubscribe + tracking URLs (ENG-134), and dispatches. Each terminal
outcome writes an `outreach.email.sent` / `outreach.email.failed` /
`outreach.email.rate_limited` / `outreach.email.suppressed` audit
row.

## Tracking + unsubscribe (ENG-134)

`packages.outreach.tracking_tokens` exposes HMAC token helpers:

- `mint_open_token(send_id)` — minted by the dispatcher when
  `template.tracking_enabled = true`, embedded as the 1x1 pixel URL.
  Namespaced by `"open:"`.
- `mint_unsubscribe_token(tenant_id, send_id, recipient_email)` —
  minted for every send, embedded in the `List-Unsubscribe` URL
  pair. Namespaced by `"unsubscribe:"`. Carries
  `(tenant_id, send_id, email_h)` so the endpoint can verify the
  token was minted for THIS recipient before applying suppression.

The token verification + suppression handling live in the API
package (`apps/api/routers/outreach_tracking.py`); the outreach
service exposes only the audit constants:

- `AUDIT_EMAIL_OPENED` — written by the pixel endpoint when the
  template's `tracking_enabled = true`. Pixel always returns the
  43-byte transparent GIF regardless; the audit row is the
  side-effect.
- `AUDIT_EMAIL_UNSUBSCRIBED` — written by the one-click endpoint
  (RFC 8058 POST) AND the manual GET form's confirmation.
- `AUDIT_EMAIL_BOUNCED` — written by the bounce poller
  (`apps.worker.jobs.bounce_poll`) when an NDR matches a send by
  `Message-ID`.

The bounce poller is a separate cron job (every 15 min) that runs
inside `apps/worker` rather than the outreach domain — it crosses
the integrations seam (Gmail / Graph clients) which the outreach
domain itself cannot import.

## Render engine

`packages.outreach.render` is dependency-free w.r.t. the DB. Callers
pass a `PersonRenderContext` (a small dataclass) and a `TemplateOut`;
the engine substitutes Mustache placeholders, runs Markdown → HTML
(or wraps in the curated MJML envelope), and returns a `RenderedEmail`
plus a `RenderTrace` (unknown placeholders, empty subject flag).

Allowed merge fields are listed in `merge_fields.ALLOWED_MERGE_FIELDS`.
Anything outside the allowlist renders as the empty string and the
service writes one `outreach.template.merge_field_unknown` audit row
per occurrence.

## Hard rules

- **Body content is NEVER logged.** Render audit rows carry
  `template_id`, `person_uid`, `version`, `category`, `body_format`,
  `unknown_field_count`, `empty_subject` — never the resolved subject
  or body. This is enforced by the audit `extra` dict shape; reviewers
  must reject any change that adds rendered content to `extra`.
- **Recipient emails are NEVER logged as plaintext.** ENG-132 audit
  rows carry `recipient_hash` (HMAC-SHA256 truncated to 64 bits under
  `INTERNAL_CREDENTIAL_TOKEN`) instead. The hash is irreversible at
  human-inspection time and stable across the deployment so an
  investigator can correlate "all audit rows about this recipient"
  without persisting the address. ENG-134 audit rows follow the same
  rule — open / unsubscribe / bounce audit rows carry `send_id` +
  `credential_id` + outcome, never PII.
- **Tracking pixel never reveals tracking state.** The pixel route
  ALWAYS returns 200 + the 43-byte GIF (with `Cache-Control:
  no-store`), regardless of token validity, gate state, or
  already-opened status. Differential responses would let recipients
  detect tracking by side-channel.
- **`body_format = 'html'` is rejected.** The enum value is reserved
  for a future stage where the operator UI gains a sanitised HTML
  editor; until then, the service raises `ValidationError`.
- **Tracking gate is type-level.** Categories in
  `TRACKING_FORBIDDEN_CATEGORIES` (`clinical`, `transactional`,
  `operational`) cannot have `tracking_enabled = true`. The service
  rejects on create AND on update. The dispatcher re-checks
  defensively before injecting the pixel.
- **Tenant isolation.** Repository methods take `tenant_id` first and
  use it as a hard filter. There is no cross-tenant admin surface in
  this domain; that lives at the audit / ops-tooling level. The
  tracking pixel + unsubscribe endpoints derive `tenant_id` from the
  HMAC-validated send row, never from the request — recipient
  routes have no tenant context on the wire.
- **No PHI here.** This domain stores marketing copy, sends, and
  recipient state — not clinical data. Adding a clinical field is a
  schema bug.
- **No imports of `phi`, `auth`, `actor`, `integrations`, or the
  tenant ORM models.** Cross-domain references go through service
  reads (`identity`, `ops`, `tenant.credential_service`) or stay as
  plain UUIDs (mailbox credential ids, location ids). The ENG-132
  dispatcher imports `packages.integrations.*` because the worker is
  the seam between domains; the outreach domain itself does not. The
  ENG-134 bounce poller follows the same pattern — it lives in
  `apps.worker.jobs.bounce_poll`, NOT in this package.

## Audit action codes

| action                                  | written by                                       |
|-----------------------------------------|--------------------------------------------------|
| `outreach.template.create`              | `TemplateService.create_template`                |
| `outreach.template.update`              | `TemplateService.update_template`                |
| `outreach.template.archive`             | `TemplateService.delete_template`                |
| `outreach.template.render`              | `TemplateService.render`                         |
| `outreach.template.merge_field_unknown` | `TemplateService.render` (one per unknown)       |
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

## MJML block library

`_mjml_blocks.py` is internal. Operators do not edit MJML directly in
Stage 1; the renderer wraps the substituted body in
`DEFAULT_ENVELOPE` (or the inline-CSS HTML fallback when the MJML
toolchain is absent). New blocks are added via PR review, not at
runtime.
