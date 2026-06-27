# Morning Report — Interactive Corporate Messenger Layer (Mattermost) V1

**Run:** autonomous overnight, 2026-06-15. **Epic:** ENG-433.
**Result: 6 of 9 blocks code-done and verified.** Nothing git-committed (per "never commit unless asked"). All work is in the working tree on branch `eng-425-full-fidelity-ingestion-v1`.

## Status by block

| Block | Issue | State | Verified |
| --- | --- | --- | --- |
| A — local infra (compose profile `chat`) | ENG-434 | In Progress | compose config + profile gating ✅ (operator must run `up` + create bot) |
| C — outbox + rules schema + dispatch worker | ENG-436 | In Review | migration `a7b8c9d0e1f2` round-trip, no drift; tests ✅ |
| B — ChatProvider + MattermostAdapter + provider_kind | ENG-435 | In Review | migration `4fe9f2b9f55a`; tests ✅; **live send unverified (needs bot token)** |
| D — rule engine + de-id renderer + emit + `lead.created` | ENG-437 | In Review | 41 tests; PII-never-leaks proven; no migration |
| H — ADR-0006 + audit taxonomy + CLAUDE.md | ENG-441 | In Review | all ADR artifacts grep-verified |
| E — signed inbound + capture + actor-link worker | ENG-438 | In Review | 22 tests; fail-closed reject proven; no migration |
| **D2** — wire 3 deferred events | ENG-443 | Backlog | not started (exact call-sites documented) |
| F — record_annotation (enrichment) | ENG-439 | Backlog | not started (needs decision #1) |
| G — agent human-in-the-loop | ENG-440 | Backlog | not started (depends on E + F) |
| I — production infra | ENG-442 | Backlog | deferred (ADR-0006 ✅; needs DEPLOYMENT_RULES preflight + decisions #3/#4/#6) |

**Cumulative gate (orchestrator-run):** `pytest tests/integrations` → **165 passed**; `mypy` on the messenger surface → **clean**. Local Postgres (5434) + Redis were up, so migrations and integration tests ran for real.

## What works now (verified offline)

- Outbound: a domain event → `NotificationEventService.emit()` → rule match (field conditions) → **de-identified** render (`person_uid` + deep link only; names/phones → `[redacted]`, proven) → `integrations.notification_outbox` row → `drain_notification_outbox` worker → `MattermostAdapter` → Mattermost posts API. `lead.created` is wired at `apps/api/routers/ops.py::create_lead` (transactional outbox; `ops` can't import `integrations`, so the boundary is correct).
- Inbound: public `POST /integrations/chat/mattermost/{webhook,action}` → constant-time token verify (`hmac.compare_digest`), cross-tenant token→tenant resolution, **fail-closed 401** → verbatim capture to `ingest.raw_event` (`source="mattermost"`) → `map_chat_inbound` worker links the Mattermost user to an internal actor (`actor_identifier` kind `mattermost_user_id`).
- Governance: ADR-0006 (Accepted), audit action codes documented, separate Mattermost DB (invariant #1 intact).

## What is NOT done / needs you

**Operator steps (need a human):**
1. Bring up local Mattermost and create the bot (ENG-434): `docker compose -f infra/docker/docker-compose.yml --profile chat up -d mattermost` → http://127.0.0.1:8065 → admin → Team → bot account → copy token. Confirm the pinned image tag `mattermost/mattermost-team-edition:10.5` pulls (bump per README if not).
2. Store the bot token + base URL as a `mattermost`/`api_key` credential, and the inbound webhook token as a `mattermost`/`webhook_secret` credential (via `IntegrationCredentialService.upsert`). Then live outbound send + live inbound can be verified end-to-end.

**Decisions still open (block later work):**
- **#1** `record_annotation` domain — recommend a new lightweight `enrichment` domain (blocks F → G).
- **#5** canonical `event_type` taxonomy — defaulted to `lead.created` / `opportunity.stage_changed` / `ownership.changed` / `ingest.sync_failed`; confirm.
- **#3/#4/#6** prod host + `chat.*`/TLS, prod Mattermost DB placement, retention/backup — block I.

**Queued work:**
- **D2 (ENG-443):** wire `opportunity.stage_changed`, `ownership.changed`, `ingest.sync_failed` at the documented call-sites.
- **F (ENG-439) → G (ENG-440):** annotations store, then agent approve/reject resolving from inbound button actions (E captures them; G consumes them).
- **I (ENG-442):** production, strictly per DEPLOYMENT_RULES, isolated from feature PRs.

## Migrations added (chained on this branch)
- `a7b8c9d0e1f2` — `integrations.notification_outbox` + `integrations.notification_rule` (down_revision `e6f7a8b9c0d1`).
- `4fe9f2b9f55a` — add `mattermost` to `ck_integration_credential_provider_kind` (down_revision `a7b8c9d0e1f2`).

Both applied to the LOCAL dev DB during verification (dev DB head is now `4fe9f2b9f55a`).

## Notes / risks for review
- **Cross-runtime (Codex) review pending** for all `contract_change` blocks before merge (durable schema, public route, provider kind, audit taxonomy).
- The work shares the working tree with the **pre-existing uncommitted full-fidelity changes**; `apps/api/dependencies.py` now carries both. A clean branch/PR split is advisable before merge.
- Pre-existing lint debt (import-sort) exists in a few unrelated files (`packages/actor/service.py`, `funnel.py`, some tests) — NOT introduced by this work; flagged so it isn't attributed here.
- **Dev trap recorded:** the canonical `cd packages/db && alembic …` fails because `Settings` loads `.env` relative to cwd; workers drove alembic via its Python API from repo root with an absolute `script_location`. No `.env` was read or edited.
