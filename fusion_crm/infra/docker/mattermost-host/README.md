# Mattermost production host — operator runbook (ENG-494 / Block I)

Production deployment of the **interactive corporate messenger layer** (ENG-433,
ADR-0006). Mattermost is treated as an external provider reached only through our
`ChatProvider` adapter; we run the official image, never a fork.

This host is a **PHI system** — prod Mattermost cards carry the real patient name
and phone (ENG-460). **ENG-501 (PHI/BAA go/no-go) = GO** (operator decision
2026-06-17), so this host is approved to stand up. Standing it up begins billing
(~$40/mo all-in) and is an outward-facing action — keep same-conversation operator
approval for each spend / hard-to-reverse step (CLAUDE.md invariant #3). Logs stay
PHI-free regardless of phase.

Related local bring-up: `infra/docker/mattermost/README.md`. Decision record:
`docs/decisions/ADR-0006-interactive-messenger-layer.md`. Deploy policy:
`docs/DEPLOYMENT_RULES.md`. Runbook: `docs/integrations/mattermost/RUNBOOK.md` §5.

## Topology

```
  Internet ──HTTPS 443──► GCE e2-small VM (us-west1-a, fusion-vpc, static IP)
                          docker compose:
                            caddy :443 (TLS, auto Let's Encrypt)
                              └─► mattermost 10.5 :8065 (websockets)
                                    ├─ DB  → fusion-mm-pg PRIVATE IP (Cloud SQL, separate)
                                    └─ files → gs://fusion-crm-mattermost (S3-compat)
  chat.fusioncrm.app ──Cloud DNS A──► static IP fusion-mm-ip
```

- **VM, not Cloud Run:** Mattermost is a stateful, long-lived websocket server
  (ADR-0006 / ADR-0002 rule out scale-to-zero Cloud Run).
- **`e2-small`:** smallest shape that comfortably runs MM + Caddy. Never
  `e2-micro` (the MM Go server stalls on shared 0.25 vCPU).

## Design decisions

### DB connectivity — private IP, not cloud-sql-proxy
The VM is in `fusion-vpc`, which is peered to the Cloud SQL servicenetworking
range, so `fusion-mm-pg` is reachable over its **private IP directly**. We
connect MM straight to that IP (`MM_DB_HOST`) with `sslmode=require` (the instance
is `--require-ssl`). This drops the cloud-sql-proxy sidecar entirely — one fewer
container to run, supervise, and reason about. The VM SA still holds
`roles/cloudsql.client` so the operator can run a break-glass Auth Proxy by hand
if ever needed. Trade-off: the DSN carries an IP rather than an instance
connection name, so if the private IP changes (rare; only on instance recreate)
the env file must be updated.

### Filestore — GCS S3-compatible (default), local-disk (documented fallback)
Default is **GCS via the S3-compatible endpoint** (`MM_FILESETTINGS_DRIVERNAME=amazons3`
pointed at `storage.googleapis.com`, bucket `gs://fusion-crm-mattermost`). This
keeps attachments off the VM disk, versioned, and inside the managed backup
contour — the right posture for PHI-adjacent files that must outlive the VM.

Caveat: Mattermost's S3 driver authenticates with **HMAC interoperability keys**,
NOT the VM's attached service account. So the bucket-scoped `objectAdmin` grant on
the VM SA (created by `provision_mattermost_host.sh`) covers `gsutil`/break-glass,
but MM itself needs HMAC keys. Generate them once at smoke time:

```bash
gcloud storage hmac keys create \
  --service-account=fusion-mm-vm-sa@fusioncrm-494201.iam.gserviceaccount.com
# store both halves in Secret Manager (mattermost-gcs-hmac-access / -secret),
# then copy into /opt/mattermost/mattermost.env (chmod 600).
```

Fallback if HMAC is undesirable: set `MM_FILESTORE_DRIVER=local`, attach a
persistent disk for `/mattermost/data`, and add a `gsutil rsync` backup cron into
`gs://fusion-crm-backups/mattermost-files/`. Trade-off: attachments then live on
the VM disk (single point of loss between backups) — acceptable only with a tight
backup cadence. Default to S3-compat unless HMAC proves blocked.

### TLS — Caddy on the VM, not the app's HTTPS LB
Caddy gets a free auto-renewing Let's Encrypt cert and proxies websockets with
zero config. A Google HTTPS LB would add a standing forwarding-rule charge
(~$18+/mo) and entangle MM (its own auth) with the IAP-gated app surface. Keep MM
on its own VM + Caddy.

## Prerequisites

- `gcloud` + `gsutil` authenticated; Owner/Editor on `fusioncrm-494201`.
- `provision_cloud_run_foundation.sh` already ran (fusion-vpc + subnet +
  servicenetworking peering exist).
- Secret `mattermost-db-password` exists with a `latest` version (hex, not
  base64 — base64 `+/=` breaks DSN parsing).
- BAA accepted for the GCP account (ADR-0001).
- `git checkout main && alembic heads` shows exactly ONE head (deploy-branch
  hygiene, RUNBOOK §5.2 — a canonical-DB concern, but the Block I PR gates on it).

## Exact ordered bring-up

Run from the repo root with `gcloud config set project fusioncrm-494201`.

**1. Create the dedicated Cloud SQL instance + DB + role.**
```bash
./infra/scripts/provision_mattermost_cloudsql.sh
# Idempotent. Creates fusion-mm-pg (POSTGRES_16, db-g1-small, ZONAL, backups +
# PITR, private IP on fusion-vpc), the `mattermost` DB, and the `mmuser` role
# (password from Secret Manager). Prints the PRIVATE IP + connection name.
```
Record the printed PRIVATE IP — it becomes `MM_DB_HOST` in the env file.

**2. Provision the host (VM + SA/IAM + bucket + static IP + firewall + DNS).**
```bash
./infra/scripts/provision_mattermost_host.sh
# Idempotent. DNS_ZONE defaults to fusioncrm-app, so the chat.fusioncrm.app
# A-record is created automatically. Prints the static IP.
```

**3. Confirm DNS resolves before bringing TLS up.**
```bash
dig +short chat.fusioncrm.app    # must equal the static IP fusion-mm-ip
```

**4. SSH into the VM (via IAP) and stage the stack.**
```bash
gcloud compute ssh fusion-mm-vm --zone=us-west1-a --tunnel-through-iap
# On the VM (Docker + compose plugin already installed by the startup script):
sudo mkdir -p /opt/mattermost && cd /opt/mattermost
# Copy these three files into /opt/mattermost:
#   docker-compose.yml   (this directory)
#   Caddyfile            (this directory)
#   mattermost.env       (built from mattermost.env.example; chmod 600)
sudo chmod 600 /opt/mattermost/mattermost.env
```
Populate `mattermost.env` from Secret Manager (never commit it):
```bash
gcloud secrets versions access latest --secret=mattermost-db-password   # → MM_DB_PASSWORD
# generate + store GCS HMAC keys (see "Filestore" above) → MM_GCS_HMAC_*
```

**5. Bring Mattermost up.**
```bash
sudo docker compose -f /opt/mattermost/docker-compose.yml \
  --env-file /opt/mattermost/mattermost.env up -d
sudo docker compose -f /opt/mattermost/docker-compose.yml ps   # all healthy
```
Caddy fetches the Let's Encrypt cert automatically once DNS resolves.

## Smoke checklist

- [ ] **TLS valid:** `curl -sI https://chat.fusioncrm.app | head -1` → `200`/`302`;
      cert is Let's Encrypt, not expired:
      `echo | openssl s_client -connect chat.fusioncrm.app:443 -servername chat.fusioncrm.app 2>/dev/null | openssl x509 -noout -dates -issuer`.
- [ ] **MM reachable:** `https://chat.fusioncrm.app` serves the Mattermost login page.
- [ ] **DB reachable:** `docker compose logs mattermost` shows a clean DB connect
      (no errors); `gcloud sql operations list --instance=fusion-mm-pg` shows the
      create succeeded; MM created its schema in the `mattermost` DB.
- [ ] **Filestore write:** upload a test attachment in MM → an object appears under
      `gs://fusion-crm-mattermost/...` (confirms the S3-compat → GCS path + HMAC keys).
- [ ] **Websocket:** open MM in a browser, confirm live message delivery (WS through Caddy).
- [ ] **Backup:** `gcloud sql backups list --instance=fusion-mm-pg` shows an automated
      backup. (Optional cold layer: weekly `pg_dump` into
      `gs://fusion-crm-backups/mattermost/<YYYY>/<MM>/` mirroring `infra/scripts/backup.sh`.)
- [ ] **No PHI in logs:** `docker compose logs` carries no patient names/phones — only
      MM operational lines (CLAUDE.md logging rule survives every phase).

## Version pin / upgrade

The image is pinned (`mattermost/mattermost-team-edition:10.5`) — the same tag as
local (`infra/docker/docker-compose.yml`). Prod and local stay on the identical
major to keep the adapter contract honest. Do not chase releases (the v7 built-in
AI CPU regression took ~1.5 years to remove, fixed v9).

To bump: pick the latest **stable** tag (never `latest`, never a brand-new major
until settled) → bump local first, verify login + bot post + inbound webhook
round-trip → then change the tag here in one deliberate compose change and
`docker compose up -d` on the VM.

## What comes after ENG-494

ENG-494 stands up the **host**; it does not make notifications flow. Sequenced next:

- **ENG-495** — admin + Team + bot account + `#leads` channel + outgoing webhook.
- **ENG-496** — store the bot token + webhook secret in `tenant.integration_credential`.
- **ENG-497** — seed prod notification rules with prod channel IDs.
- **ENG-498** — prod delivery runtime (prod has **no** always-on arq worker;
  ENG-172 paused it, so `drain_notification_outbox` + `map_chat_inbound` have
  nowhere to run yet). Standing up the host without ENG-498 = a PHI-bearing server
  that receives nothing — keep them sequenced.
- **ENG-500** — enable notifications + end-to-end smoke.
