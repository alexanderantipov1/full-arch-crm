# CLAUDE.md — Fusion CRM platform (root)

> This file is the entry point for any Claude Code session in this repo.
> Sub-areas have their own `CLAUDE.md`. Read the relevant ones when you
> work on a specific area; do not assume root-only context is enough.

## Mission

Internal system for a dental clinic. Must operate as if HIPAA were
enforced today: PHI lives in a dedicated PostgreSQL schema, every PHI
access is audited, and AI agents never touch the database directly.

## Languages

- **Conversation with the user is in Russian.**
- **Everything written into the repository is in English** — code,
  identifiers, comments, docstrings, READMEs, CLAUDE.md files, log
  keys, error messages, commit messages, API field names.

If the user pastes Russian text destined for the codebase, translate
it unless they explicitly say to keep it.

## Tech stack

- Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg / psycopg
- PostgreSQL 16, Redis 7
- Alembic for migrations
- arq for background jobs
- Pydantic v2 + pydantic-settings
- structlog for structured logs
- Docker / docker compose for local + office deployment
- Google Cloud Storage for offsite backups (BAA in place)

## Hard architectural invariants

These do not change without explicit user approval:

1. **One canonical PostgreSQL database** with eight schemas (M1
   vertical-slice set):
   `identity`, `ops`, `phi`, `audit`, `ingest`, `actor`, `auth`,
   `integrations`. Later milestones (M3-M7) add `interaction`,
   `context`, `workflow`, `encounter`, `segmentation`, `insight`.
   The `analytics` schema (added 2026-06-18, ENG-504/ENG-505, ADR-0007)
   is an **operator-approved read-model layer**: a rebuildable projection
   (`fact_patient_journey` + derived analytics), **never a source of
   truth**. It is derived from the canonical schemas and may be dropped
   and rebuilt at any time; nothing writes to it except the fact builder.
2. **One global entity:** `identity.person.id` is the `person_uid`
   referenced by every other domain via plain UUID columns.
3. **Strict domain separation.** No cross-domain imports except:
   - any domain → `packages.core`
   - any domain → `packages.identity` (read-only via `IdentityService`)
   - any domain → `packages.audit` (write-only via `AuditService`)
   - `ops` MUST NOT import `phi` (and vice versa).
4. **PHI is gated.** All PHI access goes through `PhiService`, which
   checks `Principal.can_read_phi()` and writes an audit row.
5. **No business logic in API routes.** Routes wire DTO → service.
6. **No DB access from AI agents.** Tools call services only.
7. **Data flow:** route/job → service → repository → DB. Never skip
   layers. Repositories are data-only; services hold logic.
8. **UUID primary keys everywhere.**
9. **Append-only audit.** Never `UPDATE` or `DELETE` `audit.access_log`
   in code (DB role privileges enforce this in production).
10. **Secrets are env-only.** Never hardcode credentials.
11. **Full-fidelity ingestion.** Every external object is captured with 100%
    of the fields it exposes at pull time; new fields are absorbed
    automatically. Completeness lives at the RAW layer only (`ingest.raw_event`
    is the complete forensic copy); domain mapping stays curated and
    on-demand. The schema registry `ingest.source_object_field` records what
    fields exist. See ADR-0005 and
    `.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`.

## Folder map

```
platform/
├── apps/
│   ├── api/        FastAPI HTTP surface          → apps/api/CLAUDE.md
│   └── worker/     arq background jobs            → apps/worker/CLAUDE.md
├── packages/
│   ├── core/         config, logging, exceptions, security primitives
│   ├── db/           Base, async session, mixins, alembic
│   ├── identity/     global Person + identifiers
│   ├── actor/        first-class actors (human / AI / system)
│   ├── auth/         credentials, sessions, API keys, portal accounts
│   ├── ops/          non-PHI CRM (leads, follow-ups)
│   ├── phi/          protected health data (gated)
│   ├── integrations/ external provider state (Salesforce, CareStack, …);
│   │                 chat/ = messenger layer (Mattermost, ADR-0006)
│   ├── audit/        append-only access log
│   ├── ingest/       raw external events
│   ├── insight/      semantic analytics catalog proposals + versions
│   ├── tools/        AI-agent tool layer (services-only)
│   └── agent_runtime/ application-owned agent orchestration + guardrails
├── infra/
│   ├── docker/     docker-compose + init SQL      → infra/CLAUDE.md
│   ├── scripts/    backup.sh, restore.sh
│   └── env/        per-environment guidance
├── pyproject.toml, Makefile, README.md, .env.example
```

Each area's `CLAUDE.md` contains the rules specific to that area.
**When you add a new top-level area (e.g. `apps/web`, a new
microservice, a `services/<svc>/` directory), create a `CLAUDE.md`
inside it before the first feature lands there.**

## Workflow rules

- **At-a-glance:** `docs/DEV_WORKFLOW.md` is the one-page operator-facing
  summary of the rules below — two environments (local vs production), what
  needs permission (local: none but signal it; prod merge=deploy: explicit
  per-session approval), parallel-agent isolation, and secrets (env vs DB).
  Read it for the map; the rules below and the linked policies are the detail.
- **Parallel sessions: one worktree per session.** Multiple Claude/Codex
  terminals collide on shared Git HEAD. Interactive feature work MUST run in its
  own `git worktree` (off `origin/main`), never the canonical checkout
  `~/dev/Fusion_crm`. Run the pre-flight + HEAD-race guard first; if the tree is
  dirty with files you did not create, STOP — that is another session's work.
  Full procedure: `.agents/orchestration/PARALLEL_WORK_POLICY.md` →
  "Interactive Sessions (Hand-Opened Terminals)".
- **Interactive small fixes / debugging go in the fix-lane**, not the canonical
  checkout: `/fix-lane` (or
  `.agents/skills/agent-orchestrator/scripts/fix_lane.py [area]`), tracked under
  the standing umbrella issue **ENG-537** (issue = unit of mergeable intent).
  **STOP and reclassify** as a `normal`/`contract_change` task (own worktree +
  cross-runtime review for contracts) the moment it crosses a tripwire: a 3rd
  file, a 2nd domain, a shared contract/DTO/schema/migration/env/metric/
  date-time/PHI/audit change, or a dependency chain. See
  `.agents/orchestration/PARALLEL_WORK_POLICY.md` → "The interactive fix-lane"
  and `.agents/orchestration/RUNBOOK_OPERATOR.md`.
- **Never commit unless the user explicitly asks.** Pause and ask if
  unclear.
- **Never push, force-push, drop, or destroy without explicit
  confirmation in the same conversation.**
- **Before structural changes** (new domain, new schema, new service,
  altering an architectural invariant): propose first, implement after
  approval.
- **Migrations are immutable once shipped.** New change → new
  Alembic revision. Never edit a merged migration file.
- **Run order for first-time setup** is in the root `README.md`.
- **Tests:** when you add tests, mirror the package layout under
  `tests/`. Integration tests must use a real PostgreSQL (test DB),
  not a mock.
- **Deployment/env changes:** before changing `Settings`, env vars,
  secrets, OAuth/CORS URLs, Cloud Run services/jobs, deploy scripts,
  or GitHub Actions deployment workflow, read and follow
  `docs/DEPLOYMENT_RULES.md`.

## Error / response shape

API errors follow a single envelope:
```json
{ "error": { "code": "...", "message": "...", "details": {} } }
```
Raise `packages.core.exceptions.PlatformError` subclasses; the
middleware translates to JSON. Do NOT raise raw `HTTPException` for
domain errors.

## Logging

Use `packages.core.logging.get_logger(name)`. Never use the stdlib
`logging` module directly. **Never log PHI.** Allowed: `person_uid`,
action codes, request id. Forbidden: names, DOB, allergies, notes,
clinical text.

## Data visibility & access posture (single-user phase)

> Operator decision. One user today (the doctor, full provider access).
> Applies on **every environment, production included**. Full rationale and
> the authoritative version: `docs/governance/ACCESS_POSTURE.md`.

We are **pre-access-control**:

- **Show everything.** Staff UI, staff-facing API, and MCP read surfaces MAY
  display any captured data (PHI/PII, verbatim provider payloads) with no
  redaction and no env gate. Do not refuse to render or env-hide a field.
- **No authn/authz gating on any endpoint, read OR write.** `Principal`
  defaults to `ANONYMOUS` (see `apps/api/CLAUDE.md`); that stub is the
  intentional, documented state for **every** endpoint on every environment,
  including mutations that touch PHI routing/config — **not a defect**.
- **Access control is a later, uniform layer.** Do not pre-build redaction or
  per-endpoint auth now; build surfaces so that layer can wrap them later.
- **Reviewers (including automated cross-runtime / Codex review):** a missing
  authn/authz check or an unauthenticated mutation is **NOT a merge blocker** in
  this phase — at most a *pre-multi-user / pre-public follow-up*.

This does **NOT** relax three structural things: logs stay PHI-free (see
Logging above), the hard architectural invariants stand, and hard-to-reverse /
outward-facing actions still require operator confirmation. Details in the doc.

## When in doubt

Ask the user — in Russian — before guessing. The system will be used
on real patient data; "let's just try it" is not an acceptable mode.
