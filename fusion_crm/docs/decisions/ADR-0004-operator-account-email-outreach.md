# ADR-0004: Operator-account email outreach

**Status:** Accepted
**Date:** 2026-05-10
**Authors:** Claude Code (drafted), eduardk (decision)
**Workstreams affected:** backend, frontend, devops
**Related Linear issues:** ENG-129 (parent), ENG-130 (this ADR),
ENG-131..135 (execution sub-issues)

---

## Context

The clinic needs to send outbound email — appointment reminders,
consult follow-ups, recall campaigns, manual one-off operator
messages. There is no email path in the platform today; every
message currently goes out manually from a staff Gmail tab.

We must choose between three structural options:

1. A third-party transactional API (SendGrid, Postmark, Mailgun).
2. AWS SES with verified domains.
3. The operator's own Google Workspace / Microsoft 365 mailboxes
   reached via OAuth (`gmail.send`, `Mail.Send`) — i.e. our worker
   sends *as* `info@galleriaoms.com` through the clinic's actual
   mailbox.

We pick option 3. Four reasons (all from ENG-129):

- **Deliverability.** Mail leaves the clinic's own domain through
  the clinic's own SPF / DKIM / DMARC alignment. No "via fusioncrm"
  header in any client. No third-party reputation drag.
- **Cost.** Zero per-email billing on top of the clinic's existing
  Workspace / 365 subscription. Marginal cost is API-quota-bound,
  not dollar-bound.
- **HIPAA.** Google Workspace Business / Microsoft 365 Business are
  BAA-eligible. Mail with PHI never leaves the BAA boundary the
  clinic already holds. A third-party transactional vendor would
  add a second BAA to maintain and a second processor to audit.
- **Trust.** Every message we send appears in the operator's own
  Sent folder and is searchable via their normal mail client. The
  clinic owner can audit what their own software sent without a
  separate dashboard.

Three reasons to make the call **now** rather than at PHI-time:

- The alpha clinic (Galleria) operates both Google Workspace and
  Microsoft 365 environments. We need OAuth flows for both before
  we can ship anything end-to-end.
- We are still in the pre-PHI window. Compliance gates (BAA-only
  domains, clinical templates with tracking off) are cheaper to
  encode now than to retrofit after live patient data lands.
- ENG-125 just made `tenant.integration_credential` the credential
  home for every external provider, with multi-mailbox columns
  (`mailbox_email`, `location_id`, `is_default`, `tags`) already in
  the schema. Email outreach is the first feature that exercises
  multi-mailbox routing; no new credential plumbing is required.

## Decision

### 1. Outbound queue substrate — Postgres table + arq polling

A new domain `outreach` is created with schema `outreach`. The
queue lives on a dedicated table, not on Redis Streams.

- Table: `outreach.outbound_queue`
  `(id UUID PK, tenant_id UUID FK NOT NULL, send_id UUID FK,
   credential_id UUID FK, scheduled_for tz-aware NOT NULL,
   status enum('pending','sending','sent','failed','cancelled'),
   last_error text, retry_count int DEFAULT 0,
   visible_after tz-aware, locked_by text NULL,
   locked_until tz-aware NULL, created_at, updated_at)`
- Queue protocol: arq worker `outreach.dispatcher` polls every 5 s
  with `SELECT … FOR UPDATE SKIP LOCKED LIMIT N` filtered by
  `status='pending' AND scheduled_for <= now() AND
  (visible_after IS NULL OR visible_after <= now())`.
- Per-mailbox rate limit lives in Redis as a sliding-window counter
  keyed on `outreach:rl:<credential_id>:<window>`. Redis is
  ephemeral; the **durable** queue is Postgres.
- Bodies stay in `outreach.send.body_rendered` (joined via
  `send_id`); the queue table itself never holds plaintext.

**Why a table over Redis Streams.** At Phase 1 expected volume
(1k–5k sends/day, peaking at ~10/min during a campaign burst),
both substrates are correct on raw throughput. The substrate
choice is decided by adjacent concerns:

- The queue row is *the* source of truth for "did we attempt this
  send and what was the outcome" — every row has a permanent
  `outreach.send` sibling. Postgres lets the enqueue and the send
  record share a transaction; with Redis we'd need a two-phase
  write and a reconciliation pass.
- Operators want to see "all queued sends for this campaign", "all
  failed sends today", "retry these three". That is a SQL query on
  a table; Redis Streams would force us to project state into
  Postgres anyway.
- A volatile broker is the wrong default for a HIPAA-shaped audit
  story. Even pre-PHI, we want to be able to answer "what did we
  attempt to send to person X yesterday" deterministically.
- We already run Postgres in prod (ADR-0001); Redis is incoming
  via ENG-112 and is **not** committed to durability semantics.

The 5 s polling cost is one indexed query against a small table.
At our scale this is below the Postgres query-cache noise floor.

### 2. Templates language — Mustache body + curated MJML block library

Templates are operator-edited (and, eventually, AI-edited). They
must be safe to render against a recipient context that may
contain unsanitised text from CareStack and Salesforce.

- **Body template language:** Mustache (logic-less). Operator-
  visible, no `{% if %}` ladders, no arbitrary Python expressions
  reachable from the template. Merge fields are `{{patient.first_name}}`
  shaped; the renderer is a pinned `chevron` (Python Mustache impl)
  binding only against a typed `RenderContext` Pydantic model.
- **Subject template:** Mustache, identical engine.
- **HTML layout:** a small **block library** of pre-vetted MJML
  partials (`hero`, `cta_button`, `footer`, `unsubscribe_block`)
  shipped with the codebase under `packages/outreach/blocks/`.
  Operators compose layouts from these blocks; the template
  references blocks by name. New blocks are added by engineering
  via PR review, not by operators at runtime.
- **No Liquid.** Liquid's tag system gives operators (or a
  prompt-injecting input) too many escape hatches into the render
  loop.
- **Plaintext fallback:** every template has a parallel plaintext
  Mustache body. The send pipeline produces `multipart/alternative`
  (RFC 2046).
- **Versioning:** `outreach.template.version` is a monotonic int;
  edits create a new version, never mutate. `outreach.send` carries
  `template_version` so a re-render N months later produces the
  same bytes.

### 3. Open / click tracking — opens off by default, no click tracking

This is the HIPAA-sensitive decision; we resolve it conservatively.

- **Open tracking is OFF by default.** Per-template flag
  `tracking_enabled bool NOT NULL DEFAULT false`. Operators can
  flip it on for **marketing** templates only.
- **Clinical / appointment templates default OFF and the UI blocks
  flipping it on.** The template carries a `category` enum; values
  in `{appointment_reminder, recall, consult_followup,
  treatment_plan, billing}` force tracking off. `category =
  marketing` allows opt-in.
- **Pixel implementation.** When tracking is enabled, the send
  pipeline injects a 1×1 transparent PNG served from
  `https://<our-prod-domain>/t/o/<send_id>.png`. The pixel
  endpoint records `opened_at` on `outreach.send` once and
  returns the PNG. The pixel is served **from our own domain**,
  never from a third party.
- **Click tracking is NOT implemented.** No redirector at
  `https://<our-domain>/t/c/<send_id>?u=…`. Direct links only. If
  an operator wants UTM tagging or attribution, they add it via
  Mustache merge fields in the template body (`?utm_source=…`).
  This trades attribution power for a smaller HIPAA surface.

**Why we say no to a redirector.** A click redirector necessarily
logs `(send_id, url, timestamp)` for every recipient interaction.
On a clinical email — even one without explicit PHI in the URL —
the **fact that this recipient clicked this link** is metadata
about treatment under HIPAA. We can't draw a clean line between
"marketing redirector" and "clinical redirector" in code that an
operator could subvert by reusing a marketing template for an
appointment reminder. The simplest enforcement is to not build the
redirector.

The pixel survives the same scrutiny only because it is
opt-in-per-template, blocked for clinical categories at the type
level, and served from our own domain (no third-party seeing the
recipient's IP / user-agent).

### 4. Unsubscribe — per-tenant suppression list, HMAC tokens, no auto-removal

- **Scope:** suppression is **per-tenant**. A recipient who
  unsubscribes from Galleria is not unsubscribed from Cosmo (they
  are different practices with different relationships, even if
  both end up in the same Fusion deployment).
- **Table:** `outreach.suppression`
  `(tenant_id UUID, email_normalised text, reason enum
  ('user_unsubscribe','bounce','manual','complaint'), source_send_id UUID NULL,
  created_at, PRIMARY KEY (tenant_id, email_normalised))`.
- **Token format.** Every send embeds a one-click unsubscribe URL
  carrying `send_id` + an HMAC-SHA256 signature over
  `(tenant_id, send_id, email_normalised)`. The HMAC key is the
  existing `INTERNAL_CREDENTIAL_TOKEN` (from ENG-125) namespaced
  by `"unsubscribe:"` — no new secret to provision.
- **Compliance.** The mail carries:
  - `List-Unsubscribe: <https://<our-domain>/u/<token>>, <mailto:unsubscribe@<our-domain>?subject=unsub-<send_id>>`
  - `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
  per RFC 8058. The endpoint accepts the POST without confirmation
  page and records the suppression.
- **No auto-removal.** Once an email is on the suppression list, it
  stays there. An operator can manually remove an entry through
  the UI (audit-logged) — typically only when the recipient
  re-confirms by other channels. No "expire after N days" rule, no
  "auto-clear when bounced address gets a successful delivery".
- **Send-time check.** The send service refuses to enqueue a send
  whose `recipient_email_normalised` matches a suppression row for
  the tenant. Refusals are recorded as `outreach.send.status =
  'suppressed'` for auditability — never silently dropped.

### 5. Mailbox routing — explicit-by-default, auto-route as a service

A campaign / send picks its mailbox in one of two ways. Both end
up writing the chosen `credential_id` and the chosen strategy to
the send row.

- **Explicit (default in UI):** the operator selects a specific
  connected mailbox when configuring a campaign. The send is
  pinned to that `credential_id`.
- **Auto-route:** the operator can select "auto-route" instead.
  `PickMailboxService.pick(tenant_id, intent_tag, location_id) ->
  credential_id` resolves in this order:
  1. Tenant has a credential with `location_id == location_id` and
     status=active → use it.
  2. Tenant has a credential whose `tags` array contains
     `intent_tag` (e.g. `"marketing"`) and status=active → use it.
  3. Tenant has a credential with `is_default = true` for
     `provider_kind in {google_workspace, microsoft_365}` and
     status=active → use it.
  4. No match → raise `NoMailboxAvailable`; the campaign cannot
     start, and the UI surfaces the reason.
- **Per-send audit.** `outreach.send.mailbox_strategy enum
  ('explicit','auto:location','auto:intent','auto:default')` and
  `outreach.send.credential_id` are written at enqueue time. The
  strategy is opaque to the send pipeline — once enqueued, the
  pipeline only sees `credential_id`.
- **No round-robin in Stage 1.** If a chosen mailbox is rate-
  limited, the send waits in the queue (`scheduled_for` advanced
  past the rate-limit window). Round-robin spillover across
  mailboxes is Stage 2.

## Consequences

### What this enables

- Sender reputation, deliverability, and audit story all inherit
  from the clinic's existing Workspace / 365 posture.
- Zero per-email third-party billing — outreach scales on quota,
  not invoice line items.
- HIPAA boundary stays inside one BAA (Google's or Microsoft's)
  rather than spanning two.
- Multi-mailbox per tenant (Galleria front desk vs Cosmo marketing
  vs Roseville consults) without code changes per mailbox.
- A natural extension path to inbound — the same OAuth grants that
  authorise `gmail.send` can be extended to `gmail.readonly` for
  the Stage 2 inbound-sync feature without a re-consent.
- Operator can audit anything in their own Sent folder with their
  own mail client.

### What this costs

- Two new domains to maintain — `outreach` (templates, sends,
  campaigns, suppression) and the OAuth surface inside
  `packages/integrations/google_workspace` and
  `packages/integrations/microsoft_365`.
- OAuth refresh churn — Workspace refresh tokens last ~6 months of
  inactivity, Microsoft tokens shorter. The system needs a daily
  background refresh sweep and a UI affordance for "reconnect this
  mailbox".
- NDR (bounce) parsing fragility — Gmail and Microsoft return
  Non-Delivery Reports in different formats; we must parse both
  and the formats drift. Stage 1 ships best-effort parsers and
  surfaces unparseable NDRs to the operator as raw events.
- Rate-limit ceilings — a Workspace account is capped at
  500–2000 sends/day; Microsoft 10000/day. A campaign that exceeds
  the ceiling is paced across days, not split across mailboxes
  (Stage 2 work).

### Risks

- **OAuth scope drift.** Google and Microsoft adjust scope grants
  and consent screens occasionally. A grant that worked yesterday
  may need re-consent tomorrow. Mitigation: on every refresh,
  compare returned `scope` against expected; if the set shrank,
  mark the credential `status='expired'` and surface a reconnect
  prompt. No silent functional degradation.
- **Mustache template lookalike attacks.** If we ever accept
  externally-authored templates (e.g. an AI agent producing a
  template based on operator chat), a malicious context could
  inject something that *renders correctly* but reads like a
  phishing prompt to the recipient. Mitigation: every template
  state change is audit-logged with `created_by_actor_id`; AI-
  authored templates are flagged in the UI; deliveries from a
  template marked `created_by_kind='ai'` require operator
  approval before send (Stage 1.5).
- **NDR parsing fragility.** Bounce parsing will produce false-
  negatives (a hard bounce we fail to classify). Mitigation:
  every unparseable NDR creates a row in `outreach.send_event`
  with the raw RFC 822 attached; operators can flag and we
  improve the parser. We never silently mark a send "delivered"
  on the basis of the absence of an NDR — we mark it "sent" only.
- **Pixel served from our domain.** When PHI lands and we point a
  prod hostname at the system, the pixel URL is on our domain.
  Mitigation: the pixel endpoint is the only public surface that
  doesn't require IAP (ADR-0002 carve-out), and it never returns
  anything other than the PNG bytes — no JSON, no tenant data
  in errors.

## Alternatives considered

### Option A: SendGrid / Postmark / Mailgun (third-party transactional)

- **Approach:** A managed transactional API. Body and recipient
  list go to the vendor; vendor signs and sends.
- **Pros:** Mature deliverability tooling. Built-in bounce /
  webhook plumbing. Lower engineering effort per feature.
- **Cons:** Adds a second BAA to maintain (vendor's). Some
  clients show "via sendgrid.net" / "via spmailtechnol.com" in
  the From header. Per-email cost. Mail leaves the clinic's BAA
  boundary and enters the vendor's. Operator does not see the
  message in their Sent folder.
- **Why rejected:** Each "pro" loses to operator-account on the
  four reasons cited above. The cons compound at HIPAA-time.

### Option B: Domain-authenticated relay (operator points MX to us)

- **Approach:** The clinic delegates DNS / MX so that mail to
  `@clinic.example` flows through Fusion. We become their mail
  provider for inbound *and* outbound.
- **Pros:** Total control of the mail stream. Inbound and
  outbound unified.
- **Cons:** Fusion becomes a HIPAA processor for the clinic's
  entire mail stream — every message they send and receive,
  including those wholly unrelated to Fusion features. Massive
  scope creep. The clinic loses their existing Workspace /
  365 features (calendar, drive, chat) if we replace MX.
- **Why rejected:** We want a feature, not a mail provider
  replacement. The blast radius of a Fusion incident under this
  model would extend to every email the clinic touches.

### Option C: AWS SES with verified identities

- **Approach:** Operator verifies their own domain in our SES
  account (or their own SES account). We send via SES API.
- **Pros:** AWS BAA is available. Cheaper than SendGrid /
  Postmark. Direct DKIM signing.
- **Cons:** Even with verified identities, headers commonly
  include `via amazonses.com`. AWS is still a third party in the
  BAA chain. Operator does not see sent messages in their own
  Sent folder. Domain-verification setup is a multi-step
  operator chore.
- **Why rejected:** Operator-account OAuth gives the four reasons
  for free without an extra BAA in the chain and without making
  the clinic learn SES.

### Option D: SMTP relay through operator's own SMTP server

- **Approach:** Store the clinic's SMTP credentials, connect via
  SMTP submission to their server.
- **Pros:** Works with non-Workspace / non-365 mail (GoDaddy
  hosting, Zoho, etc.).
- **Cons:** SMTP credentials are higher-risk than OAuth — they
  carry the entire mailbox scope (read, send, delete) with no
  scope-limited tokens, no incremental authorisation, and no
  refresh story. Storing live SMTP creds in
  `tenant.integration_credential.payload` is technically fine
  (Fernet-wrapped) but the *authority* the credential represents
  is too broad for the use case.
- **Why rejected:** OAuth grants narrow scopes (`gmail.send`,
  `Mail.Send`) and revocable refresh tokens. SMTP credentials
  grant the keys to the entire mailbox. We pick the scope-limited
  surface every time it's available.

## Open questions to resolve in implementation

1. **Tracking-pixel hostname.** When the system goes to a real
   production hostname (ADR-0002 left this as a placeholder), the
   pixel + unsubscribe endpoints live there too. Decide hostname
   together with the ADR-0002 follow-up; until then, dev pixels
   live on `app.fusioncrm.local` via the dev tunnel.
2. **Suppression-list import.** Operators may arrive with an
   existing suppression CSV from a previous mail tool. Stage 1
   has no import; operators add suppressions one at a time
   through the UI. CSV import is a Stage 2 ticket.
3. **Multi-mailbox round-robin under rate-limit.** When the
   chosen mailbox is rate-limited and the operator has another
   mailbox tagged for the same intent, Stage 1 just delays the
   send. Stage 2 may auto-spill to the next mailbox; needs a
   policy decision (silent spillover vs operator-visible
   "switched mailbox" event).
4. **Inbound (Stage 2).** Reading replies, threading them onto
   the original send, surfacing them in the operator UI — all
   deferred. The OAuth scopes we request in Stage 1 are
   send-only; inbound requires re-consent for read scopes. We
   note this so operators are not surprised by a second consent
   screen later.
5. **Personal-mailbox compliance gate.** ENG-131 will block
   personal `@gmail.com` / `@outlook.com` connections at OAuth
   callback time. This ADR confirms the policy: BAA-required
   tenants reject personal accounts; non-BAA dev tenants accept
   them with a banner. The list of tenant-flag values that flip
   this gate is a `tenant.setting` key documented in ENG-131.

## References

- Linear: ENG-129 (parent), ENG-130 (this), ENG-131..135
  (Foundation, Send service, Templates, Tracking, Settings UI).
- Related ADRs: ADR-0001 (Cloud SQL prod, Secret Manager pattern),
  ADR-0002 (Cloud Run prod runtime, IAP carve-outs),
  ADR-0003 (`tenant.integration_credential` is the credential home;
  multi-mailbox columns).
- Memory: `feedback_marketing_first_phase.md`,
  `feedback_solo_dev_no_iteration.md`,
  `feedback_hipaa_runtime_deferred.md`.
- Code: `packages/tenant/credential_service.py` (encryption-aware
  surface), `apps/web/lib/sf/oauth.ts` and `apps/web/lib/cs/auth.ts`
  (existing OAuth patterns the new providers will mirror).
- External: Gmail API `users.messages.send`
  (developers.google.com/gmail/api/reference/rest/v1/users.messages/send),
  Microsoft Graph `POST /me/sendMail`
  (learn.microsoft.com/graph/api/user-sendmail),
  Google Workspace BAA
  (workspace.google.com/terms/2015/1/hipaa_baa.html),
  Microsoft 365 BAA (microsoft.com/licensing/docs/customeragreement),
  RFC 5322 (Internet Message Format),
  RFC 8058 (One-Click List-Unsubscribe),
  RFC 6376 (DKIM Signatures),
  RFC 2046 (multipart/alternative).
