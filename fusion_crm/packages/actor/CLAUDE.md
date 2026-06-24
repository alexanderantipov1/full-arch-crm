# CLAUDE.md — `packages/actor`

Actor is the first-class executor of work. Humans, AI agents, system jobs,
and external services all live here under one shape so that flow / action
assignment can target any executor type uniformly.

## Tables (schema `actor`)

- **`actor`** — one row per executor.
  - `actor_type ∈ ('human','ai','system','external_service')` (full CHECK
    from day one — adding values to a CHECK is expensive; M1 actively uses
    only `human` + `external_service` but the others are reserved).
  - `status ∈ ('active','inactive','retired')`, default `active`.
  - `availability_status ∈ ('available','busy','offline','oncall')`,
    default `available`.
  - `person_uid` — optional FK to `identity.person`, set when an actor IS
    also a Person (e.g. a coordinator who is also a contact in our CRM).
- **`actor_identifier`** — maps an Actor to N external IDs.
  - `(kind, value)` is UNIQUE workspace-wide.
  - Used kinds: `salesforce_user_id`, `carestack_provider_id`,
    `carestack_coordinator_id`, `carestack_user_id`, `vapi_agent_id`,
    `email`, `phone`. Add a row in CATALOG.md before introducing a new kind.

## Deferred (NOT in this package yet)

- `actor.actor_capability` — Phase 5+ (workflow engine routing).
- `actor.actor_availability` — Phase 5+ (time-based availability).

When these land, they get their own alembic revision; add models here
without breaking the existing table layout.

## Service responsibilities

`ActorService` is the public surface. Anything that wants to find / create
an Actor goes through it:

- `upsert_actor(payload)` — idempotent on `(actor_type, name)`. Used by
  the `make mcp-key` CLI when creating an `external_service` actor for an
  MCP client, by Salesforce sync to mirror SF Users, etc.
- `get_actor(actor_id)` — raises `NotFoundError`.
- `attach_identifier(actor_id, kind, value)` — adds an external ID
  mapping; idempotent on `(kind, value)`.
- `find_by_identifier(kind, value)` — resolve an Actor by external ID.

## Cross-package imports

Per `docs/plans/2026-04-30-full-schema-v0_2.md` §1 matrix:

- **Allowed:** `identity` (for the optional `person_uid` FK), `audit`, `core`.
- **Forbidden:** everything else. Other packages reach Actor via
  `ActorService` only.

## Hard rules

- **Never store credentials here.** Passwords / tokens / API keys live in
  `auth.credential` / `auth.api_key`, linked back via `subject_id = actor.id`.
- **Always normalise `email` and `phone`** before insert (lowercase email,
  E.164 phone). Reuse `packages.identity.service.normalise_email/phone`
  via cross-package service call (NOT a direct repo import).
- **Audit on Actor creation/retirement** is the consumer's responsibility,
  not this package's. Service returns the entity; boundary writes audit.
- This package is allowed to be imported by every other domain (read-only
  via `ActorService`); the inverse is **not** allowed — `actor` does NOT
  import from `ops`, `phi`, `interaction`, etc.

## Identifier `kind` values in use

| kind                       | format                | source                |
|----------------------------|-----------------------|-----------------------|
| `salesforce_user_id`       | 18-char SF Id (005…)  | Salesforce sync       |
| `salesforce_group_id`      | 18-char SF Id (00G…)  | Salesforce sync       |
| `carestack_provider_id`    | as-supplied           | CareStack sync        |
| `carestack_coordinator_id` | as-supplied           | CareStack sync        |
| `carestack_user_id`        | as-supplied           | CareStack sync        |
| `carestack_user_detail_id` | integer-as-string     | CareStack provider → user join |
| `vapi_agent_id`            | as-supplied           | Vapi config           |
| `sofia_ai`                 | constant `sofia_ai`   | SF Task subject "sofia ai call" |
| `email`                    | lowercase             | manual + sync         |
| `phone`                    | E.164 digits          | manual + sync         |

Add a row above when introducing a new kind.

## Cross-domain resolution (ENG-415)

`ActorService.resolve_actor_from_source(tenant_id, source_provider,
source_instance, external_id, *, name_hint=None, role_hint=None)`
maps an external party id to an `actor.actor` idempotently:

- `source_provider="salesforce"` + `external_id` starts with `005` →
  human, kind `salesforce_user_id`.
- `source_provider="salesforce"` + `external_id` starts with `00G` →
  system (queue / group, NOT a person), kind `salesforce_group_id`.
- `source_provider="carestack"` + integer string → human, kind
  `carestack_provider_id`.
- `source_provider="sofia"` + `external_id == "sofia_ai"` → ai actor,
  kind `sofia_ai`.

Same human as both SF user and CareStack provider stays as TWO actors
unless a reliable join key (e.g. email) is later merged. Over-merging
is worse than duplication — names alone are not enough.
