# Mattermost — local bring-up (ENG-434, Block A)

Self-hosted Mattermost is the **interactive corporate messenger layer**
(ENG-433). It is treated as an **external provider** — like Salesforce or
CareStack — reached only through our `ChatProvider` adapter. We do **not** fork
Mattermost; we run the official image and integrate via its bot API + webhooks.

Doctrine: `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`.

## What Block A provides

Two compose services in `infra/docker/docker-compose.yml`, gated behind the
compose **profile `chat`** (so a normal `docker compose up` never starts them):

- `mattermost` — official `mattermost/mattermost-team-edition` (Team Edition,
  free), bound to `127.0.0.1:8065`.
- `mattermost-db` — a **dedicated** Postgres for Mattermost only, physically
  separate from the canonical 8-schema database. Mattermost manages its own
  schema and migrations; it must never live in our canonical DB (invariant #1).

The local Mattermost and the local `api` container share the compose network, so
inbound webhooks (buttons / thread replies) reach `http://api:8000` directly —
**no public tunnel is needed** for local inbound development.

## Bring it up

```bash
docker compose -f infra/docker/docker-compose.yml --profile chat up -d mattermost
# (mattermost-db starts automatically as a dependency)
```

Then open http://127.0.0.1:8065 and:

1. Create the first admin account (local only).
2. Create a **Team** (this represents one client company — multi-tenant model;
   per-tenant config lives in `tenant.integration_credential`).
3. Create a **bot account** (System Console → Integrations → Bot Accounts), name
   it e.g. `fusion`, and copy its **access token**.
4. Store the token + base URL in `tenant.integration_credential`
   (`provider_kind="mattermost"`) — wired in Block B (ENG-435). Never commit the
   token; never put it in `.env` long-term.

Tear down (keeps volumes/data):

```bash
docker compose -f infra/docker/docker-compose.yml --profile chat stop mattermost mattermost-db
```

Remove data too:

```bash
docker compose -f infra/docker/docker-compose.yml --profile chat down
docker volume rm fusion-crm_mmdata fusion-crm_mmdbdata   # etc., if a full reset is wanted
```

## Version pin policy

The image tag is **pinned** (`mattermost/mattermost-team-edition:10.5`) on
purpose. Operator lesson: do not chase releases — the v7 built-in-AI feature
spiked CPU and took ~1.5 years to fully remove (resolved in v9). Stay on a
current, stable major.

To bump:

1. Pick the latest **stable** tag from Docker Hub
   (`mattermost/mattermost-team-edition`) — avoid `latest` and avoid brand-new
   majors until they have settled.
2. Update the tag in `docker-compose.yml` (and, later, the prod compose, ENG-442)
   in a single deliberate change.
3. Bring up locally, verify login + bot post + an inbound webhook round-trip,
   then promote.

## Postgres locale

Keep the Mattermost DB locale **English**. Switching Mattermost's default locale
to a non-English value disables half of Mattermost's own indexes and forces
table scans. English is the default; the compose sets `LANG: C` on
`mattermost-db` and we do not override Mattermost's locale settings.

## Local inbound testing (Block E)

For Mattermost to call our inbound endpoint (`/integrations/chat/mattermost/*`)
two local-only settings matter — both are already in `docker-compose.yml`:

1. **Rosetta** (Apple Silicon) — see the version-pin note above; without it the
   amd64 image crashes under qemu.
2. **`MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS`** — Mattermost
   blocks outgoing integrations (outgoing webhooks, slash commands) from calling
   internal/private/loopback addresses by default. Our local API lives on the
   host at `host.docker.internal`, a private address, so the webhook dispatcher
   refuses it with `"address forbidden ... AllowedUntrustedInternalConnections"`
   in the Mattermost log — even though the trigger fired. The compose allowlists
   `host.docker.internal 127.0.0.1 localhost api`. LOCAL DEV ONLY; production
   uses a public `chat.*` host + the real API host.

To wire an outgoing webhook (thread replies / messages → our endpoint):
Main Menu → Integrations → Outgoing Webhooks → Add. Channel `leads`, Content
Type `application/x-www-form-urlencoded`, Callback URL
`http://host.docker.internal:8000/integrations/chat/mattermost/webhook`. Copy the
generated Token and store it as the tenant's `mattermost` / `webhook_secret`
credential (the inbound secret; separate from the `api_key` bot token).

## Not in Block A

- Outbound send / adapter — Block B (ENG-435).
- Outbox + rules schema + dispatch worker — Block C (ENG-436).
- Signed inbound endpoints — Block E (ENG-438).
- Production deployment (separate DB, GCS files, `chat.*` + TLS) — Block I
  (ENG-442), gated by ADR-0006 + `docs/DEPLOYMENT_RULES.md`.
