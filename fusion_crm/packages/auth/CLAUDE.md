# CLAUDE.md — `packages/auth`

The auth domain owns credentials, sessions, and API keys for **two subject
types**: staff/AI Actors and (future) patient PortalAccounts. Polymorphism
via the `subject_type` column — same shape, different policies.

## Tables (schema `auth`)

- **`credential`** — polymorphic password/MFA/OAuth/SSO/WebAuthn record.
  - `subject_type ∈ ('actor','portal_account')` (full CHECK from day one;
    portal_account row creation comes in M11 but the value is reserved in
    CHECK now to avoid expensive ALTER CHECK later — same rationale as
    `actor.actor_type` and `auth.session.subject_type`).
  - `credential_kind ∈ ('password','mfa_totp','oauth_external','sso_subject','webauthn')`.
  - `secret_hash` — argon2 for passwords; encrypted MFA secret; SSO
    subject id (no hash) for `sso_subject`.
  - `status ∈ ('active','revoked','expired')`, default `active`.
  - **Partial unique:** `(subject_type, subject_id, credential_kind)` is
    UNIQUE WHERE `status='active'` — one active password / one active TOTP
    per subject. Rotation = insert new active + flip old to revoked.
- **`session`** — bearer-token sessions; polymorphic same way.
  - `token_hash` is sha256 of the bearer token (the raw token never lives
    in DB). Globally unique.
  - `expires_at NOT NULL`, `revoked_at NULL`-on-active, `last_seen_at`
    refreshed on each request.
  - **Partial indexes** on `(subject_type, subject_id)` and `expires_at`
    WHERE `revoked_at IS NULL` — keep active-session lookups cheap.
- **`api_key`** — service-to-service auth (MCP, Codex, CI). ALWAYS linked
  to an `actor.actor` (FK).
  - `token_hash` sha256 of the bearer; UNIQUE.
  - `token_prefix` first ~8 chars of plaintext for display
    (`fcrm_abc12345...`); the plaintext is shown ONCE on issue.
  - `scopes` JSONB array of capability strings (runtime denial in M8).

## Deferred (NOT in this package yet)

- **`auth.portal_account`** — M11 patient portal. The `subject_type='portal_account'`
  CHECK value is already accepted; the table itself ships in M11.
- **`auth.permission_grant`** — M8 HIPAA runtime gating. Will hold
  per-(subject, capability, resource) ACL rows. M8 also wires
  `Principal.can_read_phi()` to consult this table.

## Service responsibilities

`AuthService` is the public surface. Anything that touches credentials,
sessions, or API keys goes through it.

- `set_password(subject_type, subject_id, plaintext)` — argon2 hash; flips
  any prior active password to `revoked`; inserts new active row.
- `verify_password(subject_type, subject_id, plaintext) -> bool` — silent
  failure (returns False); does NOT raise on bad password (avoid timing
  side-channel between "no such subject" and "wrong password").
- `issue_session(subject_type, subject_id, ttl_seconds, ip?, user_agent?)`
  → `(raw_token, Session)`. Caller (boundary) sets the cookie/header from
  `raw_token`; the row stores only `token_hash`.
- `revoke_session(session_id)` — idempotent.
- `find_session_by_token(raw_token) -> Session | None` — for the auth
  middleware to resolve cookies.
- `issue_api_key(actor_id, name, scopes, ttl_days?, created_by_actor_id?)`
  → `(raw_token, ApiKey)`. Plaintext shown ONCE; the row stores
  `token_hash` + `token_prefix`.
- `revoke_api_key(api_key_id)` — idempotent.
- `find_api_key_by_token(raw_token) -> ApiKey | None` — for the MCP
  bearer-token validator.

**Runtime permission denial is OUT of scope for M1.** Methods do not
consult `auth.permission_grant`; that lands in M8.

## Cross-package imports

Per `docs/plans/2026-04-30-full-schema-v0_2.md` §1 matrix:

- **Allowed:** `identity` (no direct usage today, but FK destination in
  `auth.portal_account` when M11 lands), `actor` (FK destination for
  `api_key.actor_id`), `audit`, `core`.
- **Forbidden:** everything else.

## Hard rules

- **Plaintext passwords / tokens NEVER persist.** `secret_hash` /
  `token_hash` only.
- **Plaintext API key shown ONCE on issue.** Caller must surface it
  immediately; rotation = new key + revoke old.
- **Argon2 for passwords**, not bcrypt or scrypt or PBKDF2. Single
  algorithm, single config, fewer migration paths.
- **sha256 for token hashes.** Bearer tokens are high-entropy random;
  brute-force resistance comes from token length, not from a slow hash.
- **No PHI in logs**, including `principal_id`/`subject_id` if they appear
  alongside clinical fields. Auth code itself is PHI-free, but consumer
  code that logs auth events must respect the rule.
- **Audit:** every state change (set_password, issue_session,
  revoke_session, issue_api_key, revoke_api_key) writes an
  `audit.access_log` row at the **boundary** (router/job), not here.
  Service returns the entity; caller audits.
- **Idempotency:** `revoke_*` methods accept already-revoked rows without
  raising.

## Token format

- Sessions: `fcrm_sess_<32-char-base64-urlsafe>`. The `fcrm_sess_` prefix
  helps secret-scanners flag the token as auth material.
- API keys: `fcrm_<32-char-base64-urlsafe>`. The `fcrm_` prefix is the
  external bearer convention (the `fcrm_` namespace appears in
  `audit.agent_tool_call` and MCP connection guides).

## Adding a new credential kind

1. Add the value to the CHECK constraint via a new alembic revision
   (additive — Postgres CHECK doesn't support ALTER ADD VALUE without
   drop+recreate, but adding a new value to an `IN (...)` set is doable
   via DROP CONSTRAINT + ADD CONSTRAINT in one transaction).
2. Add a service method (e.g. `setup_webauthn`).
3. Add a schema for input.
4. Update this CLAUDE.md.
