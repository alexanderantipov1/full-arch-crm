# ENG-494 — Host prod Mattermost: provisioning bundle (DRAFTS ONLY)

> **Linear:** ENG-494 `[1] Host prod Mattermost: GCE VM + separate Postgres + GCS files + chat.fusioncrm.app TLS`
> **Epic:** ENG-433 (Interactive Corporate Messenger Layer) / **Parent:** ENG-442 (Block I, production infra)
> **ADR:** ADR-0006 (Accepted, 2026-06-15) · **Runbook:** `docs/integrations/mattermost/RUNBOOK.md` §5 · **Rules:** `docs/DEPLOYMENT_RULES.md`
> **Prepared by:** Claude Code worker (overnight session, 2026-06-16). Review-and-execute-ready. **Nothing here was executed.**

---

## ⛔ DO NOT EXECUTE UNTIL ENG-501 = GO (PHI GATE)

Per ENG-460, prod Mattermost cards carry the **real patient name + phone**. Standing up
this host stands up a **PHI system**. Bringing it online — VM create, DNS, TLS, credential
store, notification enable — is blocked behind operator decision **ENG-501 (PHI/BAA posture
go/no-go)**. Until ENG-501 is **GO**:

- Do **not** create the VM, the bucket, the static IP, the DNS record, or the firewall rules.
- Do **not** store the bot token / webhook secret in `tenant.integration_credential`.
- Do **not** flip `NOTIFICATIONS_ENABLED`.

This document is a *plan*, not an action. Every command below is a reviewable checklist item
the operator runs **by hand, in order, after ENG-501 = GO**, with the same-conversation
approval required for hard-to-reverse / outward-facing / spend actions (CLAUDE.md invariant #3).

---

## 0. Facts confirmed from the repo (no guessing)

| Fact | Value | Source |
|---|---|---|
| GCP project | `fusioncrm-494201` | `provision_cloudsql.sh`, `provision_cloud_run_foundation.sh` |
| Region | **`us-west1`** (NOT us-central1) | both provision scripts (`REGION="${REGION:-us-west1}"`) |
| Zone | `us-west1-a` | `provision_cloudsql.sh` |
| App domain | `fusioncrm.app` (Cloud IAP LB, managed cert) | `docs/DEPLOYMENT_RULES.md` §4, infra/CLAUDE.md |
| Existing VPC | `fusion-vpc` / subnet `fusion-vpc-us-west1` (`10.0.0.0/24`) | `provision_cloud_run_foundation.sh` |
| Existing backup bucket | `gs://fusion-crm-backups` (versioning on, 90-day lifecycle) | `provision_cloudsql.sh`, `backup.sh` |
| Existing Cloud SQL instance | `fusion-crm-pg` (`POSTGRES_16`, `db-custom-1-3840`) | `provision_cloudsql.sh` |
| MM image pin | `mattermost/mattermost-team-edition:10.5` | `docker-compose.yml`, `mattermost/README.md` |
| MM file dir (local) | `/mattermost/data/` (`MM_FILESETTINGS_DRIVERNAME=local`) | `docker-compose.yml` |
| Worker on prod | **paused** (ENG-172); no always-on arq runtime | `infra/CLAUDE.md`, RUNBOOK §5.2 |

> **Rosetta is LOCAL-only.** The prod VM is amd64 native — the `platform: linux/amd64` pin
> and the Rosetta toggle are dev-machine concerns and have **no role** on a GCE `e2-small`.

---

## 1. Topology decision recommendation

**Recommendation: single GCE `e2-small` VM in `us-west1-a`, running the official Mattermost
`10.5` image plus a reverse proxy via `docker compose`, with a dedicated Cloud SQL database
for Mattermost, GCS for the file store, and a Caddy reverse proxy terminating TLS for
`chat.fusioncrm.app`.**

```
                       Internet
                          │  HTTPS 443 (only public ingress)
                          ▼
        ┌─────────────────────────────────────────────┐
        │  GCE e2-small VM  (us-west1-a, amd64)         │
        │  external static IP: fusion-mm-ip             │
        │  firewall: 443 from 0.0.0.0/0; SSH via IAP    │
        │                                               │
        │   docker compose (mattermost-host-compose):   │
        │   ┌──────────┐   ┌──────────────────────────┐ │
        │   │  caddy   │──►│ mattermost 10.5 :8065     │ │
        │   │  :443    │   │  (websockets)             │ │
        │   │  (TLS,   │   └──────────────────────────┘ │
        │   │  auto    │          │ SQL (private)         │
        │   │  ACME)   │          ▼                       │
        │   └──────────┘   cloud-sql-proxy ──► Cloud SQL  │
        │                       fusion-mm-pg DB (separate)│
        │   filestore: GCS bucket fusion-crm-mattermost   │
        └─────────────────────────────────────────────┘
                          │ outbound to Cloud SQL (private IP via VPC) + GCS
                          ▼
   chat.fusioncrm.app  ──DNS A──►  fusion-mm-ip
```

**Why a VM (not Cloud Run):** Mattermost is a stateful, long-lived websocket server.
ADR-0006 and ADR-0002 both rule out scale-to-zero Cloud Run for it. A single small VM with
`min-instances=1` semantics (it just stays up) is the correct shape.

**Why `e2-small` (2 vCPU burst / 2 GB):** Team Edition for one clinic team is tiny. `e2-small`
(~$13–15/month) is the smallest shape that comfortably runs MM + Caddy + the SQL proxy. The
RUNBOOK and ENG-494 title both name `e2-small` — keep it. Do **not** use `e2-micro` (0.25 vCPU
shared) — the MM Go server stalls under the AI-removal era memory profile.

**Why Caddy (not the existing Cloud IAP LB):** see §4 TLS decision below.

---

## 2. Open decisions — recommendations

### Open decision #2 — Mattermost version pin + cadence
**Recommend: pin the prod image to the SAME tag as local — `mattermost/mattermost-team-edition:10.5`.**
- Prod and local must run the identical major to keep the adapter contract honest.
- Bump policy (already in `mattermost/README.md`): pick the latest **stable** tag, never
  `latest`, never a brand-new major until settled; bump local first, verify login + bot post +
  inbound round-trip, then bump prod in a single deliberate compose change.
- The v7 built-in-AI CPU regression (1.5 yr to remove, fixed v9) is the standing reason not to
  chase releases.

### Open decision #3 — Prod host shape + `chat.*` hostname/TLS
**Recommend: `e2-small` GCE VM + `chat.fusioncrm.app` + Caddy automatic TLS (Let's Encrypt).**
- Hostname: `chat.fusioncrm.app` (sibling of the app's `fusioncrm.app`). No localhost / no
  `http://` in any prod URL (DEPLOYMENT_RULES §4).
- TLS: Caddy on the VM gets a free Let's Encrypt cert automatically over HTTP-01/TLS-ALPN once
  DNS resolves to the static IP, and auto-renews. See §4 for why Caddy over an HTTPS LB.

### Open decision #4 — Prod Mattermost DB placement
**Recommend: a SEPARATE DEDICATED Cloud SQL database (`mattermost`) on a NEW small instance
`fusion-mm-pg`, NOT a co-located Postgres container on the VM, and NOT a second DB inside the
canonical `fusion-crm-pg` instance.**

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. New Cloud SQL instance `fusion-mm-pg`** (recommended) | Managed backups + PITR; physically separate from canonical DB (invariant #1 honored cleanly); survives VM rebuild/replace; no MM data on the VM disk | ~$10–15/month for a `db-g1-small`/`db-custom-1-3840` zonal instance; second instance to operate | ✅ **Recommended** |
| B. Co-located Postgres container on the VM | Cheapest; simplest network (loopback) | MM data lives on a single VM disk — VM loss = data loss unless we hand-roll dumps; backup/restore is bespoke (not in the Cloud SQL contour); PHI on an unmanaged disk | ❌ Rejected for a PHI store |
| C. New `mattermost` DB inside the existing `fusion-crm-pg` instance | One instance to operate; cheapest managed option | Couples MM's lifecycle/locale/upgrade to the canonical PHI DB; a noisy MM workload shares IOPS with the clinic DB; ADR-0006 wants it *physically separate* | ❌ Rejected — defeats the "own DB" intent |

**Decisive factor:** ENG-460 made the MM store a PHI system → it needs managed backups, PITR,
and encryption-at-rest that Cloud SQL gives for free. The co-located container (B) would put
PHI on an unmanaged VM disk outside the backup contour — unacceptable. The marginal cost of a
dedicated tiny instance (A) is the right trade for a PHI store that must outlive the VM.

> The dedicated instance can be sized down to `db-g1-small` (shared-core, ~$9/mo) since one
> clinic team is a trivial DB load. Keep it zonal (no HA) during this phase, matching the
> canonical instance's Phase-1 posture — promote HA only when PHI volume justifies it.

### Open decision #6 — Retention / backup policy
**Recommend: reuse the existing GCS backup contour with a MM-specific path + 90-day retention,
backed by Cloud SQL automated backups + PITR as the primary layer.**
- **Primary:** Cloud SQL automated backups on `fusion-mm-pg` (daily, 7-day retention, PITR on)
  — identical to the canonical instance config in `provision_cloudsql.sh`.
- **Secondary (cold):** a weekly `pg_dump` of the `mattermost` DB into
  `gs://fusion-crm-backups/mattermost/<YYYY>/<MM>/` via the existing `backup.sh` pattern (the
  bucket already has versioning + 90-day lifecycle). Wire it as a VM host cron.
- **File store:** the GCS filestore bucket (`fusion-crm-mattermost`) gets object versioning ON
  and a 365-day lifecycle on noncurrent versions (attachments are PHI-adjacent; keep a year).
- **Message retention:** Mattermost Team Edition has no built-in data-retention policy job
  (that's Enterprise). Messages are retained indefinitely at the DB layer; pruning, if ever
  wanted, is an operator decision recorded separately. Document "indefinite retention, no
  auto-purge" as the current state.

---

## 3. EXACT ordered command sequence (operator runs in the morning, after ENG-501 = GO)

> Each step is idempotent (describe-or-create) or read-only. Secrets are placeholders.
> Run the two draft scripts/compose in this repo — do **not** hand-type ad-hoc gcloud.
> All `gcloud`/`gsutil` assume `gcloud config set project fusioncrm-494201` first.

**Step 0 — Gate check (read-only).**
```bash
# Confirm ENG-501 = GO in Linear before anything mutating. (manual check)
# Confirm alembic single head on main (NOT the dev checkout) — RUNBOOK §5.2:
#   git fetch && git checkout main && alembic heads   # expect exactly ONE
```

**Step 1 — Create the dedicated Cloud SQL DB instance for Mattermost (managed, separate).**
```bash
# Idempotent describe-or-create. Sized small; zonal; backups + PITR on.
gcloud sql instances describe fusion-mm-pg >/dev/null 2>&1 || \
gcloud sql instances create fusion-mm-pg \
  --database-version=POSTGRES_16 --edition=ENTERPRISE \
  --tier=db-g1-small --region=us-west1 \
  --storage-type=SSD --storage-size=10 --storage-auto-increase \
  --availability-type=ZONAL --backup --backup-start-time=11:00 \
  --enable-point-in-time-recovery --retained-backups-count=7 \
  --maintenance-window-day=SUN --maintenance-window-hour=11 \
  --maintenance-release-channel=production --require-ssl --quiet

# DB + role (password from Secret Manager: create the secret first — Step 2).
gcloud sql databases describe mattermost --instance=fusion-mm-pg >/dev/null 2>&1 || \
gcloud sql databases create mattermost --instance=fusion-mm-pg --quiet
# DB locale: keep ENGLISH/C — never set a non-English MM locale (index loss).
```

**Step 2 — Create Secret Manager secrets for MM (values added by reference, never inline).**
```bash
for s in mattermost-db-password mattermost-bot-token mattermost-webhook-secret; do
  gcloud secrets describe "$s" >/dev/null 2>&1 || \
  gcloud secrets create "$s" --replication-policy=automatic --quiet
done
# Populate the DB password ONCE (hex, not base64 — base64 +/= breaks DSN parsing):
#   openssl rand -hex 32 | gcloud secrets versions add mattermost-db-password --data-file=-
# Create the MM Postgres role using that secret (idempotent):
gcloud sql users list --instance=fusion-mm-pg --format='value(name)' | grep -qx mmuser || \
gcloud sql users create mmuser --instance=fusion-mm-pg \
  --password="$(gcloud secrets versions access latest --secret=mattermost-db-password)" --quiet
# bot-token + webhook-secret are populated AFTER Step 6 (workspace exists) → handled in ENG-495/496.
```

**Step 3 — Run the host provisioning script (VM + firewall + bucket + static IP + DNS).**
```bash
# Review the draft first, then promote it into infra/scripts/ in the ENG-494 PR.
bash ./.agents/orchestration/mattermost-prod-bringup-v1/artifacts/provision_mattermost_host.sh.draft
# Idempotent. Creates: static IP fusion-mm-ip, GCS bucket fusion-crm-mattermost,
# firewall (443 ingress + IAP SSH), VM fusion-mm-vm (e2-small), DNS A record (if Cloud DNS).
# Prints the static IP for the manual DNS step if DNS is external.
```

**Step 4 — Point DNS `chat.fusioncrm.app` → static IP (operator-managed).**
```bash
# If fusioncrm.app is in Cloud DNS the script already added the A record. Otherwise add it at
# the external DNS provider:  chat  A  <fusion-mm-ip printed by Step 3>   (TTL 300)
# Verify before TLS:  dig +short chat.fusioncrm.app   # must equal the static IP
```

**Step 5 — SSH into the VM (via IAP), install Docker, copy the compose + Caddyfile + env file.**
```bash
gcloud compute ssh fusion-mm-vm --zone=us-west1-a --tunnel-through-iap
# On the VM (the startup-script in the provision draft already installs docker + compose plugin):
#   sudo mkdir -p /opt/mattermost && cd /opt/mattermost
#   # copy mattermost-host-compose.yml (from this bundle), Caddyfile, and an env file that
#   # contains ONLY references resolved on the VM (see §6). NO secrets committed to the repo.
#   # The SA-key / Cloud SQL proxy + GCS creds come from the VM's attached service account.
```

**Step 6 — Bring Mattermost up on the VM.**
```bash
# On the VM:
#   sudo docker compose -f mattermost-host-compose.yml up -d
#   sudo docker compose -f mattermost-host-compose.yml ps   # all healthy
# Caddy fetches the Let's Encrypt cert automatically once DNS resolves (Step 4).
# Then create the admin + Team + bot + #leads channel + outgoing webhook → ENG-495.
```

**Step 7 — Backup wiring (secondary cold layer).**
```bash
# On the VM, add a weekly host cron that pg_dumps the mattermost DB into the existing bucket:
#   GCS_BUCKET=fusion-crm-backups BACKUP_RETENTION_DAYS=90 \
#     pg_dump ... mattermost | gsutil cp - gs://fusion-crm-backups/mattermost/$(date +%Y/%m)/...
# (mirror infra/scripts/backup.sh conventions; never log the DSN). Primary layer = Cloud SQL PITR.
```

> Steps 8+ (store credentials, seed prod rules with prod channel IDs, prod delivery runtime,
> enable notifications + e2e smoke) are **ENG-495 → ENG-500** — out of scope for ENG-494.

---

## 4. TLS approach — Caddy on the VM (chosen) vs HTTPS LB (rejected for this case)

**Chosen: Caddy reverse proxy on the VM, automatic Let's Encrypt cert for `chat.fusioncrm.app`.**

Justification for a single small VM:
- **Websockets:** Mattermost is websocket-heavy. Caddy proxies WS transparently with zero extra
  config. A Google HTTPS LB also supports WS but adds a backend service, NEG, health check, URL
  map, target proxy, forwarding rule, and a managed-cert resource — a lot of infra for one VM.
- **Cost:** a global HTTPS LB has a standing hourly forwarding-rule charge (~$18+/month) on top
  of the VM. Caddy is free and runs in the existing VM footprint.
- **Single origin:** the app already owns `fusioncrm.app` behind the Cloud IAP LB
  (`provision_cloud_iap_lb.sh`). Adding `chat.*` as a *second backend* to that LB would entangle
  the MM host with the IAP-gated app surface (MM has its own auth; we do **not** want IAP in
  front of the Mattermost login + bot webhook). Keeping MM on its own VM + Caddy keeps the two
  surfaces cleanly separated.
- **Auto-renew:** Caddy renews silently; no 90-day manual cert chore.

Why **not** a Google-managed cert via HTTPS LB here: it's the right tool when you need global
anycast, multi-region backends, Cloud Armor, or shared cert lifecycle with other services — none
of which apply to one stateful MM VM. Reserve the LB pattern for the app; give MM the lean VM+Caddy
path. (nginx + certbot is a viable alternative but needs a cron-driven renew + reload hook; Caddy
folds that into one binary — prefer Caddy.)

Firewall: only **443/tcp from `0.0.0.0/0`** is open to the public. SSH is **IAP-only**
(`35.235.240.0/20`), never `0.0.0.0/0`. No port 80 left open except what Caddy needs for the
ACME HTTP-01 challenge (Caddy can use TLS-ALPN-01 on 443 only — prefer that and keep 80 closed;
the draft opens 80 only if TLS-ALPN proves insufficient — see the script comment).

---

## 5. Preflight + smoke checklist (specific to the MM host)

**Preflight (before Step 6 brings MM up):**
- [ ] ENG-501 = GO recorded in Linear (PHI gate).
- [ ] `alembic heads` on **main** shows exactly one head (RUNBOOK §5.2). (Canonical-DB concern;
      MM has its own DB, but the deploy branch must be clean before any prod infra lands.)
- [ ] `gcloud config get-value project` == `fusioncrm-494201`, region us-west1.
- [ ] Secrets exist with a `latest` version: `mattermost-db-password` (DEPLOYMENT_RULES §6/§7).
- [ ] No prod URL contains `localhost`/`127.0.0.1`/`http://` — `chat.fusioncrm.app` is https.
- [ ] `dig +short chat.fusioncrm.app` == static IP `fusion-mm-ip`.
- [ ] VM service account has `roles/cloudsql.client` (proxy) + `roles/storage.objectAdmin` on
      `gs://fusion-crm-mattermost` (filestore) + `roles/secretmanager.secretAccessor`.
- [ ] Firewall: 443 public; SSH IAP-only; Postgres NOT publicly reachable (Cloud SQL private/proxy).

**Smoke (after Step 6, before declaring the host done):**
- [ ] **TLS valid:** `curl -sI https://chat.fusioncrm.app | head -1` → `200`/`302`; cert issuer is
      Let's Encrypt, not expired: `echo | openssl s_client -connect chat.fusioncrm.app:443 -servername chat.fusioncrm.app 2>/dev/null | openssl x509 -noout -dates -issuer`.
- [ ] **MM reachable:** `https://chat.fusioncrm.app` serves the Mattermost login page.
- [ ] **Can create team/bot:** admin account created; one Team per tenant; a bot account exists and
      a token is issued (token goes to Secret Manager / credential service — ENG-495/496, NOT here).
- [ ] **DB reachable:** MM started clean (no DB connection errors in
      `docker compose logs mattermost`); `gcloud sql operations list --instance=fusion-mm-pg` shows
      the create succeeded; MM created its own schema in the `mattermost` DB.
- [ ] **File store on GCS:** upload a test attachment in MM → object appears under
      `gs://fusion-crm-mattermost/...` (confirms `MM_FILESETTINGS_DRIVERNAME=amazons3` S3-compat is
      pointed at GCS correctly).
- [ ] **Backup runs:** run the Step-7 cron command once by hand → a dump lands in
      `gs://fusion-crm-backups/mattermost/<YYYY>/<MM>/` and is non-empty; `gcloud sql backups list
      --instance=fusion-mm-pg` shows an automated backup.
- [ ] **Websocket:** open MM in a browser, confirm live message delivery (WS through Caddy works).
- [ ] **No PHI in logs:** `docker compose logs` and any host log carry no patient names/phones —
      only MM operational lines (DEPLOYMENT_RULES / CLAUDE.md logging rule survives this phase).

---

## 6. Secrets handling (DEPLOYMENT_RULES §6)

- **MM DB password** → Secret Manager `mattermost-db-password`. The VM resolves it at boot via its
  attached SA (`roles/secretmanager.secretAccessor`), writes it into the compose env on the VM
  only (a file with `chmod 600`, never committed). The Cloud SQL proxy connects with the VM SA, so
  the DB password is only needed for the MM `mmuser` Postgres role.
- **MM bot token + webhook secret** → these are **tenant-owned provider credentials**, not platform
  runtime secrets. They live in `tenant.integration_credential`
  (`provider_kind="mattermost"`, `credential_kind="api_key"` and `"webhook_secret"`), resolved by
  `IntegrationCredentialService`. Stored in **ENG-496**, not here. The Secret Manager placeholders
  `mattermost-bot-token`/`mattermost-webhook-secret` are an optional bootstrap-only convenience and
  must not become long-lived Cloud Run env vars (DEPLOYMENT_RULES §6, §10).
- **GCS filestore creds** → none. The VM's attached service account is granted
  `roles/storage.objectAdmin` on the filestore bucket; MM's S3-compatible driver uses GCS HMAC keys
  **or** the workload identity. (HMAC keys, if used, are Secret Manager entries
  `mattermost-gcs-hmac-access`/`-secret`, resolved on the VM — never in the repo.)
- Never log: secret values, full DSNs, tokens, SA JSON, or rendered PHI card text.

---

## 7. Repo placement note (for the ENG-494 PR)

When ENG-501 = GO and this is executed, **promote** the two draft files into the canonical infra
tree as part of the ENG-494 PR (infra-only, separate from feature PRs — DEPLOYMENT_RULES §9):
- `provision_mattermost_host.sh.draft` → `infra/scripts/provision_mattermost_host.sh`
- `mattermost-host-compose.yml.draft` → `infra/docker/mattermost/mattermost-host-compose.yml`
  (+ a `Caddyfile` next to it).

Add the new env vars / secret names to `infra/env/production.env.reference` and the preflight
expectations per DEPLOYMENT_RULES §1/§10. Update `infra/CLAUDE.md` with a "Mattermost host"
section and `docs/integrations/mattermost/RUNBOOK.md` §5 to mark the open decisions closed.

---

## 8. Blockers / open items surfaced while drafting

1. **Delivery runtime is unsolved (ENG-498).** This host serves the MM *server*. But prod has **no
   always-on arq worker** (ENG-172 paused it). `drain_notification_outbox` + `map_chat_inbound`
   have nowhere to run in prod yet. ENG-494 stands up the host; it does **not** make notifications
   flow. Flag loudly: standing up the host without ENG-498 = a PHI-bearing server that receives
   nothing. Keep them sequenced.
2. **DNS provider unknown.** The draft script handles the Cloud DNS case (auto A-record) and prints
   the IP for the external-provider case. Operator must confirm where `fusioncrm.app` DNS is hosted.
3. **GCS S3-compat driver detail.** MM uses an S3-compatible driver for object storage; GCS exposes
   an S3-compatible endpoint (`storage.googleapis.com`) with HMAC keys. The compose draft sets the
   `MM_FILESETTINGS_*` S3 keys pointed at GCS; verify HMAC vs. native at execution time (smoke item).
4. **Single-head alembic on main** is a deploy-branch prerequisite inherited from the mission goal;
   not an MM-host blocker per se but gates the broader Block I PR.
