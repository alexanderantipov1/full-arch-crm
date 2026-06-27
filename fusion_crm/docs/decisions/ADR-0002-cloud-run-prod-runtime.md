# ADR-0002: Production app runtime — Cloud Run + Cloud IAP

**Status:** Accepted
**Date:** 2026-05-08
**Authors:** Claude Code (drafted), eduardk (decision)
**Workstreams affected:** backend, frontend, mcp, devops
**Related Linear issues:** (filed alongside this ADR)

---

## Context

ADR-0001 stood up the production database (Cloud SQL `fusion-crm-pg` in
project `fusioncrm-494201`). The application code itself
(`apps/api`, `apps/worker`, `apps/web`) still has no production
runtime — it lives only in local Docker on the operator workstation.

The system needs a real prod runtime that:

1. Hosts three workloads with different shapes:
   - `apps/api` — FastAPI HTTP service, request-driven, latency-sensitive
   - `apps/web` — Next.js HTTP service (operator dashboard), SSR + static
   - `apps/worker` — arq listener consuming a Redis queue, long-running
   - cron-driven jobs (SF lead pull, CareStack sync) that run on a schedule
2. Is reachable from **two physical locations** — the operator's laptop
   (anywhere) and the clinic office (different city). Public internet is
   the only common transport.
3. Is **not exposed to the public internet** in the "URL is enough" sense.
   Only authenticated members of the team should reach the UI/API at all.
4. Runs entirely under the existing Google BAA. No third-party SaaS
   between users and PHI-bearing endpoints.
5. Stays small / cheap during Phase 1–2 (marketing data, no PHI yet),
   with a clear scale-up path for the PHI-heavy phases to come.
6. Matches the team shape: solo dev + AI-generated code; operational
   toil is the highest-cost category per memory
   `feedback_solo_dev_no_iteration.md`.

The runtime decision is the precondition for several deferred items:
- ENG-112 (Memorystore migration) — needs a VPC and a known runtime
- ENG-110 (HA + CMEK) — gated by the same VPC and prod app posture
- Future patient portal (`apps/portal`, schema-reserved) — same posture

## Decision

### Runtime: **Cloud Run** for all three services

Each app builds a container, ships to Artifact Registry, runs as a
Cloud Run service in project `fusioncrm-494201`, region `us-west1`.

| App | Cloud Run shape | Why |
|---|---|---|
| `apps/api` | Service, `min-instances=0`, autoscale | request-driven, scale-to-zero saves cost outside hours |
| `apps/web` | Service, `min-instances=0`, autoscale | same |
| `apps/worker` | Service, **`min-instances=1`**, single instance | arq listener needs to be always running to drain Redis |
| Cron tasks (SF pull, CS pull) | **Cloud Run Jobs** triggered by Cloud Scheduler | discrete batch work; no idle cost |

### Access control: **Cloud IAP** in front of all services

Every Cloud Run service is fronted by an HTTPS Load Balancer with
**Identity-Aware Proxy** turned on. Reaching any URL requires:

1. A live Google session under the `drantipov.com` Workspace org
2. Membership in `roles/iap.httpsResourceAccessor` for the resource

No public access, no VPN, no certificates to distribute. Audit logs
record every authenticated session.

Initial allow-list:
- `drantipov@drantipov.com` (Owner)
- `eduard@drantipov.com` (Owner)
- Clinic staff added per onboarding policy

For the worker — there is no public surface (it doesn't take HTTP),
so no IAP. It connects out to Cloud SQL and Redis only.

### Network: VPC + Serverless VPC Access connector

Single VPC `fusion-vpc` in `us-west1` with a serverless VPC connector.
Cloud Run services attach to it. This unlocks:

- **Private IP for Cloud SQL** (replaces Auth Proxy in prod). The Auth
  Proxy stays as the operator-laptop pattern; Cloud Run uses Private IP.
- **Memorystore for Redis** — Memorystore has no public IP option and
  requires VPC peering anyway (per ENG-112 scope).
- A clean perimeter for future VPC Service Controls (PHI go/no-go gate).

### Custom domain: `app.fusioncrm.example` → HTTPS LB → Cloud Run

A managed Cloud DNS zone for whatever final domain the clinic picks.
HTTPS LB terminates TLS with a Google-managed certificate. Both
`apps/web` and `apps/api` live under the same hostname with path-based
routing:
- `/` → web (Next.js)
- `/api/*` → api (FastAPI)

This keeps cookies single-origin and simplifies the IAP attachment.

### Secrets and config

App secrets (DB password, OAuth client secrets, encryption key) stay
in Secret Manager and are mounted into Cloud Run as environment
variables. The `gcp-secret://` URL scheme from ADR-0001 still works
locally and in CI; in Cloud Run direct env injection is faster and
removes a runtime dependency on `google-cloud-secret-manager` for the
hot path.

`SECRET_KEY`, `DB_PASSWORD`, `ENCRYPTION_KEY`, etc. → Cloud Run
"Reference a secret" bindings, projecting Secret Manager versions as env
at boot. Cloud Run rotates pods when a secret version changes (with
`--update-secrets ...:latest`).

### CI/CD

GitHub Actions on push to `main`:
1. Run lint + tests (existing CI job)
2. Build container, push to Artifact Registry
3. `gcloud run deploy` for the affected service
4. Run `alembic upgrade head` via a one-shot Cloud Run Job before any
   API deploy — never inside the API container at boot
   (preserves the `infra/CLAUDE.md` rule)

GitHub Actions authenticates to GCP via Workload Identity Federation
(no downloaded SA-key — same posture as ADR-0001).

### Costs (Phase 1–2)

| Item | $/mo |
|---|---|
| Cloud Run (3 services, mostly idle) | $5–15 |
| Cloud Run worker `min-instances=1` (e2-small equivalent) | $10–15 |
| Cloud Run Jobs (cron) | $1–3 |
| Serverless VPC connector | ~$10 |
| Cloud SQL (already running) | $50 |
| Memorystore basic 1GB (when ENG-112 lands) | $45 |
| HTTPS LB | $18 |
| Cloud DNS managed zone | <$1 |
| Cloud IAP | $0 (free under 1M reqs) |
| **Subtotal Phase 1 (no Memorystore yet)** | **~$100/mo** |
| **Subtotal Phase 2 (with Memorystore)** | **~$145/mo** |

If the worker isn't always on (cron-only design), drop `min-instances`
and save $10–15/mo. Decided when arq workload shape is clear.

## Consequences

### What this enables

- A working production deployment that two distant locations can both
  reach safely, with one allow-list to maintain.
- Audit logs of every login (IAP) and every deploy (Cloud Build /
  GitHub Actions).
- A clear path to PHI: VPC + Private IP + Memorystore make the
  CMEK / VPC Service Controls work in ENG-110 mostly mechanical.
- Workload Identity for GitHub Actions and Cloud Run — closes the
  gap left by `iam.disableServiceAccountKeyCreation` in ADR-0001.

### What this costs

- ~$100/mo recurring during Phase 1, growing to ~$145/mo with
  Memorystore. Acceptable for a real product but visible.
- Operational complexity: VPC, Load Balancer, IAP, and DNS are four
  new GCP surfaces beyond Cloud SQL.
- Dev/prod drift: locally we still use Docker compose; Cloud Run has
  different env, secret, networking models. We standardise on
  containers (already true) and document the difference in the runbook.

### Risks / open questions

- **Cold start latency** — Cloud Run `min-instances=0` adds ~1–2s on
  first request after idle. Acceptable for staff dashboard; revisit
  with `min-instances=1` if user-perceived.
- **arq on Cloud Run** — `min-instances=1` plus a health-check
  endpoint is a workable pattern but not the canonical arq deployment.
  If queue volume grows, migrate worker to GKE or a Compute Engine VM.
- **Custom domain** not yet picked — placeholder
  `app.fusioncrm.example` in this ADR; final DNS update is part of
  the bring-up tickets.
- **Cloud IAP and Workspace MFA** must align — IAP enforces what
  Workspace policy says about MFA. Confirm Workspace requires 2FA on
  `drantipov.com` org before going live.
- **Long-running connections** (websockets, server-sent events,
  streaming responses >60min) — Cloud Run has request timeouts. Not
  needed today; flag if interaction-engine work goes streaming.

## Alternatives considered

### Option A: Compute Engine VM with `docker compose up`

- **Approach:** Single e2-small VM, `infra/docker/docker-compose.prod.yml`
  runs the same compose we have today.
- **Pros:** 1:1 mental model with dev. Lower infra cognitive load.
- **Cons:** OS patching is the operator's responsibility. No
  scale-to-zero — you pay for idle cycles. Single host = no HA.
  No automatic TLS / IAP — would need nginx + OAuth2 Proxy bolted on.
  When PHI lands and CMEK + VPC SC come up, the VM model gets
  awkward fast.
- **Why rejected:** Trades short-term simplicity for long-term toil
  on the path the project is already committed to. The cost gap
  ($25/mo vs $100/mo) does not justify the operational gap.

### Option B: GKE Autopilot

- **Approach:** Managed Kubernetes; same containers, deployed as
  Deployments + Services with Ingress.
- **Pros:** Industry standard, future-proof, every PaaS pattern
  available, including sophisticated network policy and PHI gates.
- **Cons:** $75/mo control plane fee even with zero workloads.
  Significant Kubernetes learning curve for solo dev. Manifest
  maintenance overhead.
- **Why rejected:** Premature scale-up for a single-clinic Phase 1
  product. Re-evaluate if we move to multi-tenant SaaS.

### Option C: App Engine Standard / Flexible

- **Approach:** Google's older PaaS.
- **Pros:** Mature, automatic scaling, IAP integration.
- **Cons:** App Engine Standard has restrictive runtimes (Python 3.12
  is only just supported, with caveats). Flexible is essentially
  Compute Engine with extra steps. Google's own docs now point new
  workloads at Cloud Run.
- **Why rejected:** Cloud Run is the modern equivalent and the
  documented Google recommendation.

### Option D: Cloud Run service-only, Redis on the same host

- **Approach:** Skip VPC + Memorystore. Run Redis as a sidecar in
  the worker Cloud Run service.
- **Pros:** Cheaper. No VPC connector needed.
- **Cons:** Redis state lost on every container recycle. arq job
  state goes too. We re-enqueue jobs but UI gets temporary
  inconsistency. Not viable once multiple worker instances are needed.
- **Why rejected:** False economy — Memorystore is part of the
  runtime story, deferring it just postpones the same work.

### Option E: A self-hosted reverse proxy (Caddy / Cloudflare Tunnel)
on a VM, services behind it

- **Approach:** Cloudflare Zero Trust / Tailscale, with services
  on a private VM not exposed to the internet.
- **Pros:** Powerful access policies (per-app, per-time-of-day).
  Familiar if anyone already runs Tailscale.
- **Cons:** Adds a third party to the auth path (Cloudflare /
  Tailscale). For HIPAA-aware workloads we want fewer parties between
  users and PHI, not more. BAA coverage with Cloudflare is possible
  but adds an annual review item.
- **Why rejected:** Cloud IAP gives us "only authenticated Workspace
  members" with zero added vendors and a single BAA already in place.

## Open questions to resolve in implementation

1. **Final domain** — clinic decides; CNAME later.
2. **Worker shape** — `min-instances=1` Cloud Run service vs hybrid
   (cron-only via Cloud Run Jobs + Cloud Scheduler). Decide after
   first arq workload runs in prod and we measure idle volume.
3. **TLS policy** — Google-managed cert is fine for Phase 1.
   Customer-managed cert when EV / specific issuer is required.
4. **Cloud Build vs GitHub Actions** — both work; GitHub Actions
   wins on developer ergonomics (CI already there). Pick GHA.

## References

- Linear issue(s): filed alongside this ADR (parent + ~5 sub-issues)
- Related ADRs: ADR-0001 (Cloud SQL prod) — depends on
- Source whitepapers / docs:
  - `infra/CLAUDE.md`
  - `infra/env/PRODUCTION.md`
  - `apps/api/`, `apps/worker/`, `apps/web/` Dockerfiles
- External references:
  - Cloud Run + IAP recipe (cloud.google.com/iap/docs/enabling-cloud-run)
  - Serverless VPC Access connector (cloud.google.com/vpc/docs/serverless-vpc-access)
