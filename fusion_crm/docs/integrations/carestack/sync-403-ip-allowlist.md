# CareStack Sync API 403 — "Security Policy" IP allowlist

**Status:** known/expected failure mode. Diagnosed 2026-06-21, recurs whenever
our egress IP changes. **If CareStack sync suddenly stops and you see a 403,
read this FIRST — do not re-investigate from scratch.**

## Symptom

- Integration card shows `Last run · 0 records · failed` with an error like
  `carestack GET api/v1.0/sync/accounting-transactions failed: 403`
  (the named endpoint varies — it's whichever `/sync/*` leg the run hit).
- The `/project-manager/payments` page keeps showing data — it reads our DB,
  not live CareStack — but **no new** CareStack data arrives.

## Root cause

CareStack protects the **Sync API (`/sync/*`) behind an IP allowlist / WAF**
("Security Policy"). When our outbound IP is **not** on CareStack's allowlist,
**every** `/sync/*` call returns:

```
403  Request blocked due to CareStack Security Policy!
```

This is **NOT** a credentials problem and **NOT** a disabled billing feature:

- the password-grant **token still issues** (200),
- `GET /api/v1.0/locations` and `GET /api/v1.0/providers` **still return 200**
  (they are not behind the Sync-API security policy),
- only `/sync/*` is blocked.

It recurs ("опять временно заблокировали") because home/dev egress IPs are
dynamic; CareStack says it works from their whitelisted IPs ("напротив говорят
работает"). The block lifts once the IP is (re)whitelisted.

## How to confirm in 30 seconds

Run the read-only probe — issues one token, GETs each `/sync/*` with
`pageSize=1`, prints the exact status:

```python
import asyncio
from datetime import UTC, datetime, timedelta
from packages.integrations.carestack import CareStackClient
from packages.integrations.carestack.exceptions import CareStackApiError

async def main():
    c = CareStackClient.from_env()
    await c._ensure_token()                      # 200 => creds OK
    ms = {"modifiedSince": (datetime.now(UTC) - timedelta(days=1))
          .replace(microsecond=0).isoformat().replace("+00:00", "Z"), "pageSize": 1}
    for label, path in [
        ("locations", "api/v1.0/locations"),
        ("sync/patients", "api/v1.0/sync/patients"),
        ("sync/accounting-transactions", "api/v1.0/sync/accounting-transactions"),
    ]:
        try:
            await c.get(path, query=None if "sync" not in path else ms)
            print("200", label)
        except CareStackApiError as e:
            print(e.details.get("status"), label, str(e.details.get("body"))[:60])
    await c.close()

asyncio.run(main())
```

- token OK + `/locations` 200 + all `/sync/*` 403 "Security Policy" → **IP block.**
- Check prod the same way via the job logs:
  `gcloud logging read 'resource.labels.job_name="fusion-job-cs-pull"' --limit=40`
  — look for `Request blocked due to CareStack Security Policy` vs the healthy
  `ingest_scheduled.carestack.ok` / `carestack.accounting_transaction.import_done`.

## Fix

1. **Immediate:** send CareStack the current egress IP(s) and ask them to add
   to the **Sync API allowlist**. Local dev IP: `curl https://api.ipify.org`.
   Prod IP: the Cloud Run egress IP (see below).
2. **No manual re-pull needed:** the feed resumes from the `lastUpdatedOn`
   watermark (`packages/ingest/sync_window.py`), so the next scheduled
   `fusion-job-cs-pull` tick automatically catches up the backlog.

## Deferred durable fix — static prod egress IP (NOT done)

Today prod Cloud Run runs `--vpc-egress=private-ranges-only`, so CareStack
traffic leaves via Google's **dynamic** egress — there is no stable IP to
whitelist, so prod can fall off the allowlist at any time.

Durable fix = give prod a **static egress IP**:

1. reserve a regional static external IP,
2. create Cloud Router + Cloud NAT on `fusion-vpc` using it,
3. switch the CareStack callers (`fusion-job-cs-pull`, `fusion-job-backfill`,
   `fusion-job-cs-procedure-codes`, **and** the API service for manual
   "Sync now") to `--vpc-egress=all-traffic`,
4. whitelist that one stable IP with CareStack.

**Why deferred:** step 3 reroutes ALL outbound traffic (Salesforce, Google
APIs, GCS, prod Mattermost) through the new NAT — a material prod-networking
change governed by `docs/DEPLOYMENT_RULES.md`, with real blast radius if the
NAT is misconfigured. Decision (2026-06-22): **do it only if the block recurs
soon**; until then accept the manual re-whitelist. Before building the NAT,
check whether CareStack can allowlist a wider CIDR — that may be far cheaper.

## What the code already does (resilience)

`apps/worker/jobs/ingest_scheduled.py::pull_carestack_for_tenant` isolates each
CareStack leg: a provider 403 on one feed (or the whole `/sync/*` family) is
caught per-leg, recorded in `meta.failed_legs`, and the run closes `partial` —
the legs that DID succeed still commit. A Sync-API block no longer rolls back
the entire tick to "0 records". (The operator-triggered deep `backfill_*`
deliberately keeps fail-fast so a manual backfill surfaces the block loudly.)
