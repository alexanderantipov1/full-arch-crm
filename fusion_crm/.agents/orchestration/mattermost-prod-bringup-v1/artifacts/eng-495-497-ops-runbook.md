# Mattermost Prod Bring-up — Operator Runbook (ENG-495 / ENG-496 / ENG-497)

> **PREREQUISITE — do not start until BOTH are true:**
> **ENG-494 host reachable at `https://chat.fusioncrm.app`** (TLS valid, admin
> login works) **AND ENG-501 = GO** (deploy-gate / go-no-go sign-off).
>
> This runbook is executed BY HAND by the operator (doctor). It covers three
> sequential Linear tasks. Do them in order; each depends on the previous.
> Everything you type into the system is English.

References used to build this runbook (read-only):
`docs/integrations/mattermost/RUNBOOK.md` §3 (credential shapes) + §4 (local
steps mirrored here), `packages/integrations/chat/seeds.py` (the hardcoded
LOCAL channel IDs), `packages/integrations/chat/resolver.py`,
`packages/tenant/credential_service.py` (`IntegrationCredentialService`),
`packages/integrations/notification_service.py`
(`NotificationService.create_rule` / `upsert_rule`),
`packages/integrations/chat/mattermost.py` (`resolve_channel_id`).

---

## 0. Values to capture during the run (fill this FIRST, it feeds every step)

Keep this block in a scratch note as you go. ENG-496 and ENG-497 consume it.

| Key | Where it comes from | Value (fill in) |
|---|---|---|
| `base_url` | The API process's reachable URL for the MM server | `https://chat.fusioncrm.app` |
| `action_callback_base` | The URL the MM SERVER calls back into our API | `https://<prod-api-host>` (the FastAPI Cloud Run host, NOT chat.*) |
| `bot_token` | ENG-495 step 3 (bot account token) | `__________________________` |
| `webhook token` | ENG-495 outgoing-webhook / action token | `__________________________` |
| **PROD tenant id** | See §4 "Resolving the PROD tenant id" — CONFIRM, do not assume | `__________________________` |
| channel id `leads` | ENG-495 step 6 | `__________________________` (26 chars) |
| channel id `leads-missing-info` | ENG-495 step 6 | `__________________________` |
| channel id `scheduls` | ENG-495 step 6 | `__________________________` |
| channel id `opportunities` | ENG-495 step 6 | `__________________________` |
| channel id `ownership` | ENG-495 step 6 | `__________________________` |
| channel id `ingest-alerts` | ENG-495 step 6 | `__________________________` |
| channel id `today` | ENG-495 (per ticket; see note below) | `__________________________` |
| channel id `consult-reminders` | ENG-495 (per ticket; see note below) | `__________________________` |

> **Channel-list reconciliation note.** ENG-495's text lists
> `leads`, `leads-missing-info`, `scheduls`, `today`, `consult-reminders`.
> The CODE (`seeds.py` `_DEFAULT_RULES`) actually routes to:
> `leads`, `leads-missing-info`, `scheduls`, `opportunities`, `ownership`,
> `ingest-alerts`. The authoritative source for the notification pipeline is
> `seeds.py` — those six channels MUST exist or the matching rule fails at
> dispatch. Create all of them. `today` and `consult-reminders` from the
> ticket are NOT referenced by any current rule in `seeds.py`; create them too
> (harmless, likely earmarked for future digest/reminder rules) but understand
> **no rule points at them today** — capturing their IDs is forward-looking,
> not load-bearing for ENG-497.

---

## ENG-495 — Prod workspace: team, bot account, token, channels, channel IDs

This mirrors `RUNBOOK.md` §4.1 but against the PROD host. All clicks are in the
Mattermost admin web UI at `https://chat.fusioncrm.app`.

### Step 1 — Log in as the System Admin
- Open `https://chat.fusioncrm.app`, sign in with the admin account created
  during ENG-494 host bring-up.

### Step 2 — Create the team
- Top-left **+ → Create a team** (or **Main Menu → Create a Team**).
- Name it (e.g. `Fusion`). Note: the bot resolves channels against its
  **first team** (`GET /api/v4/users/me/teams`, see
  `mattermost.py::_first_team_id`), so keep the bot in exactly ONE team to make
  channel-name resolution deterministic.

### Step 3 — Create the bot account + mint its token
- **Product menu (top-left grid) → Integrations → Bot Accounts → Add Bot
  Account**.
  - Username: e.g. `fusion-notifier`.
  - Role: **Member** is enough for posting; grant System Admin only if a later
    feature needs it. (Posting + channel resolution need only membership.)
- **Create** → Mattermost shows the **token ONCE**. Copy it into the table
  above as `bot_token`. You cannot retrieve it again — if lost, regenerate.

### Step 4 — (recommended) enable bot/integration settings if blocked
- If "Bot Accounts" is greyed out: **System Console → Integrations →
  Bot Accounts → Enable Bot Account Creation = true**, save, retry step 3.

### Step 5 — Create each channel
For EACH channel name in the table (`leads`, `leads-missing-info`, `scheduls`,
`opportunities`, `ownership`, `ingest-alerts`, plus `today`,
`consult-reminders`):
- In the team, **+ next to channel category → Create new channel**.
- **Channel name** = the exact slug above (the URL handle must equal the slug;
  Mattermost lowercases/handles it — verify the URL handle matches).
- Type: Private is fine (this is a PHI surface — see §SECURITY below); the bot
  must be a member regardless.

### Step 6 — Add the bot to EVERY channel + capture the 26-char channel ID

> **TRAP (the local 403/404 trap).** The dispatcher posts by **channel id**,
> and Mattermost returns **403 (not a member)** / **404** if the bot is not a
> member of the target channel. A channel that exists but has no bot member
> still fails every notification routed to it. Add the bot to ALL of them.

- Add the bot: open the channel → **Channel name dropdown → Add Members** →
  add `fusion-notifier`. Repeat for every channel.
- Capture the channel id (26-char base62). Two ways:
  1. **UI:** open the channel → **Channel name dropdown → View Info** → the
     panel shows the **Channel ID** (26 chars). Copy it.
  2. **API (more reliable, scriptable):**
     ```
     # team id:
     curl -s -H "Authorization: Bearer <BOT_TOKEN>" \
       https://chat.fusioncrm.app/api/v4/users/me/teams | jq '.[0].id'
     # channel id by name:
     curl -s -H "Authorization: Bearer <BOT_TOKEN>" \
       https://chat.fusioncrm.app/api/v4/teams/<TEAM_ID>/channels/name/leads \
       | jq '.id'
     ```
     This is the exact endpoint `MattermostAdapter.resolve_channel_id` uses
     (`/api/v4/teams/{team_id}/channels/name/{name}`), so if curl returns an id
     here, ENG-497 Option (a) below will resolve the same way.
- Record each id in the §0 table.

### Step 7 — Configure the inbound outgoing-webhook (for the inbound token)
Mirror `RUNBOOK.md` §4.2 but with PROD URLs:
- **Integrations → Outgoing Webhooks → Add Outgoing Webhook**:
  - Channel: `leads` (or the channel inbound replies come from).
  - Content-Type: `application/x-www-form-urlencoded`.
  - **Callback URL:** `https://<prod-api-host>/integrations/chat/mattermost/webhook`
    (the public FastAPI host = `action_callback_base`, NOT `chat.*`).
- **Save** → copy the generated **Token** into the §0 table as `webhook token`.
- Prereq on the MM server (ENG-494 config): `AllowedUntrustedInternalConnections`
  must permit the API host so MM can call it (prod uses the public host, not
  `host.docker.internal`).

**ENG-495 done when:** all 8 channels exist, bot is a member of each, the §0
table has 8 channel IDs + bot_token + webhook token + base_url.

---

## ENG-496 — Store the prod credential in the prod DB (encrypted, via the service)

> **HARD RULE.** Credentials go into `tenant.integration_credential`,
> **Fernet-encrypted**, written ONLY through `IntegrationCredentialService.upsert`
> (it wraps the payload in `{"ciphertext": ..., "alg": "fernet"}` via
> `packages.integrations.crypto.encrypt_str`). NEVER hand-write the encrypted
> envelope. NEVER `INSERT` raw SQL into the table. NEVER put `bot_token` /
> `webhook token` in Cloud Run env vars. The Fernet key lives in the prod app
> env, so this MUST run inside the prod app's runtime (a Cloud Run Job / shell
> with the prod `Settings`), not on your laptop with a different key.

Two credential rows are needed (shapes from `RUNBOOK.md` §3 +
`resolver.py`):

| provider_kind | credential_kind | payload | consumed by |
|---|---|---|---|
| `mattermost` | `api_key` | `{base_url, bot_token}` (+ optional `action_callback_base`) | outbound — `resolver.py::resolve_chat_provider` reads `base_url` + `bot_token` |
| `mattermost` | `webhook_secret` | `{token}` | inbound — token verification in `chat_inbound` |

`resolver.py` reads the outbound row with exactly:
`credentials.read_for(tenant_id, "mattermost", "api_key")` and requires non-empty
string `base_url` and `bot_token` (else `InvalidChatCredentialError`).

### The exact way to store them (run in the prod app runtime)

`PROD_TENANT_ID` is the value you confirmed in §4. `principal` must be a
`Principal` (any non-None subject is fine — this is the documented
single-operator posture; use the system principal).

```python
# Run inside the PROD app environment (correct Settings → correct Fernet key).
# e.g. a one-off Cloud Run Job, or `python -c` in a shell that loads prod env.
import asyncio
from uuid import UUID

from packages.core.types import TenantId
from packages.core.security import Principal
from packages.db.session import async_session            # the worker/script boundary
from packages.tenant.credential_service import IntegrationCredentialService

PROD_TENANT_ID = TenantId(UUID("REPLACE-WITH-CONFIRMED-PROD-TENANT-ID"))

BASE_URL = "https://chat.fusioncrm.app"
ACTION_CALLBACK_BASE = "https://<prod-api-host>"          # the public FastAPI host
BOT_TOKEN = "REPLACE-WITH-BOT-TOKEN"                      # from ENG-495 step 3
WEBHOOK_TOKEN = "REPLACE-WITH-WEBHOOK-TOKEN"             # from ENG-495 step 7


async def main() -> None:
    principal = Principal.system()  # or the documented operator principal
    async with async_session() as session:
        svc = IntegrationCredentialService(session)

        # 1) Outbound bot credential (api_key).
        await svc.upsert(
            PROD_TENANT_ID,
            "mattermost",
            "api_key",
            {
                "base_url": BASE_URL,
                "bot_token": BOT_TOKEN,
                "action_callback_base": ACTION_CALLBACK_BASE,
            },
            principal=principal,
            display_name="Mattermost prod bot",
            is_default=True,
        )

        # 2) Inbound webhook secret (webhook_secret).
        await svc.upsert(
            PROD_TENANT_ID,
            "mattermost",
            "webhook_secret",
            {"token": WEBHOOK_TOKEN},
            principal=principal,
            display_name="Mattermost prod inbound webhook",
        )

        await session.commit()   # the boundary commits; the service never does


asyncio.run(main())
```

Notes / guard-rails:
- `provider_kind="mattermost"` is already in `PROVIDER_KINDS` and the DB CHECK
  constraint (migration `4fe9f2b9f55a`); `upsert` validates both enums and will
  raise `ValidationError` on a typo.
- `credential_kind` must be exactly `api_key` and `webhook_secret` (both in
  `CREDENTIAL_KINDS`).
- Confirm the import path for the session boundary in this repo before running
  (`async_session` lives in the worker boundary; if the symbol differs, use the
  same boundary that `apps/worker/jobs/*` use — they call `async_session()`).
- Do NOT set `mailbox_email` — that's email-OAuth only; the service rejects it
  for `mattermost`.

**Verify (read-only):**
```python
payload = await IntegrationCredentialService(session).read_for(
    PROD_TENANT_ID, "mattermost", "api_key"
)
assert payload["base_url"] == BASE_URL and payload["bot_token"]
```
The audit row is `tenant.credential.upsert.insert` with NO payload bytes
(by design).

**ENG-496 done when:** both rows exist (`api_key` + `webhook_secret`) for the
confirmed prod tenant, and `read_for(..., "mattermost", "api_key")` returns the
correct `base_url`/`bot_token`.

---

## ENG-497 — Configure prod notification rules with prod channel IDs

### The seeds.py LOCAL-channel-ID trap (in full)

`packages/integrations/chat/seeds.py` defines channels TWO different ways:

1. **By NAME** (resolved per-environment, prod-safe):
   - `DEFAULT_LEAD_CREATED_CHANNEL = "leads"`
   - `LEADS_MISSING_INFO_CHANNEL = "leads-missing-info"`
   - `OPPORTUNITY_CHANNEL = "opportunities"`
   - `OWNERSHIP_CHANNEL = "ownership"`
   - `INGEST_ALERTS_CHANNEL = "ingest-alerts"`

2. **By a HARDCODED LOCAL channel ID** (the trap):
   - `SCHEDULS_CHANNEL_ID = "uap18hmdkbbqmm6sg1msapjjur"`  ← this is the id of
     the LOCAL dev `#scheduls`. The `consultation.scheduled` rule in
     `_DEFAULT_RULES` uses this literal as its `channel`.

`seed_all_notification_rules()` writes the rules with `channel` set to **exactly
the value in the tuple** — it does NOT resolve names→ids. So:
- Running the default seed unmodified on prod creates a `consultation.scheduled`
  rule whose `channel` = the LOCAL id `uap18hmdkbbqmm6sg1msapjjur`, which does
  not exist on the prod MM server → the dispatcher's post returns **403/404**
  and the outbox row goes `failed`.
- The other five rules carry channel **names**, not ids. The dispatch path
  expects a channel **id** (see `seeds.py` comment ENG-457 and the post-by-id
  contract). So even the name-based rules are only safe if something resolves
  the name to an id before/at dispatch.

Therefore the default seed is NOT prod-safe as-is. Two options:

### Option (a) — operational: write the rules via the rule service with resolved prod IDs (RECOMMENDED)

Use `NotificationService.create_rule(...)`. It calls
`provider.resolve_channel_id(channel)` (the `MattermostAdapter`, built from the
prod credential you stored in ENG-496) which:
- returns a 26-char id unchanged, OR
- resolves a NAME against the bot's first team via
  `GET /api/v4/teams/{team_id}/channels/name/{name}` → id,
- raising `ChannelResolutionError` if the bot can't see the channel (catches the
  "bot not a member" trap loudly instead of failing silently at dispatch).

So you can feed it the channel NAMES (or the captured IDs) and it stores the
resolved **id** every time. This is idempotent on `(event_type, channel)` and
needs NO code change.

```python
import asyncio
from uuid import UUID

from packages.core.types import TenantId
from packages.core.security import Principal
from packages.db.session import async_session
from packages.integrations.chat.resolver import resolve_chat_provider
from packages.integrations.notification_service import NotificationService
from packages.integrations.notification_schemas import NotificationRuleIn
from packages.integrations.chat.seeds import (
    LEAD_CREATED_RICH_TEMPLATE,
    LEAD_MISSING_INFO_RICH_TEMPLATE,
    CONSULTATION_SCHEDULED_RICH_TEMPLATE,
)
from packages.integrations.chat.events import (
    EVENT_LEAD_CREATED, EVENT_CONSULTATION_SCHEDULED,
    EVENT_OPPORTUNITY_STAGE_CHANGED, EVENT_OWNERSHIP_CHANGED,
    EVENT_INGEST_SYNC_FAILED,
)

PROD_TENANT_ID = TenantId(UUID("REPLACE-WITH-CONFIRMED-PROD-TENANT-ID"))

# (event_type, channel NAME, conditions, template, description) — authoritative
# rule set, derived 1:1 from seeds._DEFAULT_RULES, with the LOCAL scheduls id
# replaced by the channel NAME so the resolver maps it to the PROD id.
RULES = [
    (EVENT_LEAD_CREATED, "leads", [], LEAD_CREATED_RICH_TEMPLATE,
     "Default: notify on new lead"),
    (EVENT_LEAD_CREATED, "leads-missing-info",
     [{"field": "has_phone", "op": "eq", "value": False}],
     LEAD_MISSING_INFO_RICH_TEMPLATE, "Field control: new lead with no phone"),
    (EVENT_CONSULTATION_SCHEDULED, "scheduls", [],
     CONSULTATION_SCHEDULED_RICH_TEMPLATE,
     "Default: notify on newly-scheduled consultation"),
    (EVENT_OPPORTUNITY_STAGE_CHANGED, "opportunities", [],
     {"text": "Opportunity {{person_uid}} stage → {{stage}} — {{deep_link}}"},
     "Default: notify on opportunity stage change"),
    (EVENT_OWNERSHIP_CHANGED, "ownership", [],
     {"text": "Ownership changed for {{person_uid}} ({{owner_role}}) — {{deep_link}}"},
     "Default: notify on ownership change"),
    (EVENT_INGEST_SYNC_FAILED, "ingest-alerts", [],
     {"text": "Sync failed: {{provider}} {{object}} ({{sync_status}})"},
     "Default: alert on failed ingest sync run"),
]


async def main() -> None:
    principal = Principal.system()
    async with async_session() as session:
        provider = await resolve_chat_provider(PROD_TENANT_ID, "mattermost", session)
        svc = NotificationService(session)
        for event_type, channel_name, conds, template, desc in RULES:
            await svc.create_rule(
                PROD_TENANT_ID,
                NotificationRuleIn(
                    event_type=event_type,
                    channel=channel_name,          # resolved to a PROD id by the adapter
                    conditions=conds,
                    template=template,
                    provider_kind="mattermost",
                    enabled=True,
                    description=desc,
                ),
                principal=principal,
                provider=provider,
            )
        await session.commit()


asyncio.run(main())
```
(Confirm `NotificationRuleIn`'s exact field set in
`packages/integrations/notification_schemas.py` before running; the names above
match `upsert_rule`'s reads.)

### Option (b) — make seeds.py channel IDs configurable so the seed is prod-safe

Replace the hardcoded `SCHEDULS_CHANNEL_ID` (and ideally all channel refs) with
env / tenant-config lookups so `seed_all_notification_rules` reads per-env IDs.
This is a code change + migration of how rules are seeded, must ship through a
PR, and still doesn't solve name→id resolution for the other five rules unless
it ALSO resolves names. More moving parts, more deploy surface.

### Recommendation: Option (a)

Use **Option (a)**. Reasons:
- Zero code change, zero deploy — pure operational data write, fits the
  "operator executes by hand once the host is up" framing of these tickets.
- It uses the SAME resolver path the dispatcher trusts
  (`MattermostAdapter.resolve_channel_id`), so a resolved rule is guaranteed
  postable; a bot-not-in-channel mistake surfaces immediately as
  `ChannelResolutionError` instead of silently failing later.
- It fixes BOTH halves of the trap at once (the hardcoded local scheduls id AND
  the name-vs-id mismatch on the other rules) because every stored `channel`
  ends up a resolved prod id.
- Option (b) is the right long-term cleanup (file it as a follow-up to delete
  `SCHEDULS_CHANNEL_ID`), but it is not required to bring prod up and adds
  deploy risk now.

### Authoritative rule set that MUST exist on prod (event_type → channel → template)

| event_type | channel (name → resolve to prod id) | template | conditions |
|---|---|---|---|
| `lead.created` | `leads` | `LEAD_CREATED_RICH_TEMPLATE` (rich card, name/phone) | none |
| `lead.created` | `leads-missing-info` | `LEAD_MISSING_INFO_RICH_TEMPLATE` | `has_phone == False` |
| `consultation.scheduled` | `scheduls` | `CONSULTATION_SCHEDULED_RICH_TEMPLATE` | none |
| `opportunity.stage_changed` | `opportunities` | `{text: "Opportunity {{person_uid}} stage → {{stage}} — {{deep_link}}"}` | none |
| `ownership.changed` | `ownership` | `{text: "Ownership changed for {{person_uid}} ({{owner_role}}) — {{deep_link}}"}` | none |
| `ingest.sync_failed` | `ingest-alerts` | `{text: "Sync failed: {{provider}} {{object}} ({{sync_status}})"}` | none |

**ENG-497 done when:** six rules exist for the prod tenant, every rule's
`channel` is a resolved 26-char PROD channel id (verify via
`NotificationService.list_rules(PROD_TENANT_ID)` — no value should equal the
local `uap18hmdkbbqmm6sg1msapjjur`), and a smoke `lead.created` emit posts to
the prod `#leads`.

---

## SECURITY (do not skip)

With `Settings.messenger_phi_full` defaulting True, notification cards carry the
patient's REAL name / phone. The prod Mattermost server is therefore a **PHI
system**: TLS in transit (done at ENG-494), access control on the team/channels,
encrypted backups, and a retention policy. Application logs stay PHI-free
regardless — only `person_uid` / event codes are logged, never the rendered
card. Confirm the `messenger_phi_full` posture with the doctor before enabling
emits in prod.

---

## §4 — Resolving the PROD tenant id (CONFIRM — do not assume)

- Code resolves the request tenant by **slug**, not a hardcoded UUID:
  `apps/api/dependencies.py` → `TenantService.resolve_default(settings.tenant_default_slug)`,
  where `tenant_default_slug` defaults to **`fusion-dental-implants`**
  (`packages/core/config.py`, alias `TENANT_DEFAULT_SLUG`).
- **KNOWN TRAP (do not copy the local UUID):** the local dev tenant is the seed
  UUID `11111111-1111-4111-8111-111111111111` (hardcoded in
  `infra/scripts/*full_fidelity*.py`). That is the LOCAL bootstrap id. Prod's
  `fusion-dental-implants` tenant has its OWN UUID created by the prod bootstrap
  migration — it is almost certainly NOT `1111...`. A second related trap
  (marketing): some jobs iterate `list_tenants()` (multiple registered tenants)
  while the dev principal resolves the seed tenant — so "which tenant" is genuinely
  ambiguous in this codebase. For ENG-496/497 you MUST target the ONE tenant the
  prod API serves.
- **How to confirm the real prod tenant id** (run in the prod app runtime,
  read-only):
  ```python
  from packages.tenant.service import TenantService
  from packages.core.config import get_settings   # confirm accessor name
  async with async_session() as session:
      t = await TenantService(session).resolve_default(
          get_settings().tenant_default_slug    # "fusion-dental-implants" unless overridden
      )
      print(t.id, t.slug)
  ```
  Use the printed `t.id` as `PROD_TENANT_ID` in ENG-496 and ENG-497.
- Also confirm `TENANT_DEFAULT_SLUG` is not overridden in the prod Cloud Run env
  to a different slug; if it is, resolve that slug instead. **Flag any mismatch
  to the operator before writing credentials/rules** — pointing them at the
  wrong tenant means notifications silently never fire.

---

## Final operator checklist

- [ ] ENG-494 host up at `https://chat.fusioncrm.app`, ENG-501 = GO.
- [ ] §0 table fully filled (base_url, action_callback_base, bot_token,
      webhook token, prod tenant id, 8 channel IDs).
- [ ] Bot is a MEMBER of every channel (no 403/404 trap).
- [ ] ENG-496: `mattermost`/`api_key` + `mattermost`/`webhook_secret` rows
      stored via `IntegrationCredentialService.upsert` (encrypted) — NOT in env,
      NOT raw SQL. `read_for` verify passes.
- [ ] ENG-497: 6 rules created via `NotificationService.create_rule` (Option a);
      every `channel` is a resolved PROD id, none equal the local scheduls id.
- [ ] Smoke test: a `lead.created` emit lands in prod `#leads`.
- [ ] Follow-up filed to delete `seeds.SCHEDULS_CHANNEL_ID` (Option b cleanup).
- [ ] `messenger_phi_full` posture confirmed with the doctor.
