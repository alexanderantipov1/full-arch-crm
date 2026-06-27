# CLAUDE.md — `packages/db` (database & migrations)

The single declarative `Base`, the single async engine, the single
Alembic config. Domain models live in their own packages; this
package is the glue.

## Files

- **`base.py`** — `Base` + naming convention (PK/FK/UQ/IX/CK).
  Every model inherits from this `Base`. Don't create a second one.
- **`mixins.py`** — `UUIDPrimaryKeyMixin`, `TimestampMixin`. Use both
  on every persisted entity unless you have a written reason not to.
- **`session.py`** — async engine + `SessionFactory` +
  `async_session()` context manager.
- **`registry.py`** — imports every domain's `models` module so
  Alembic autogenerate sees the full metadata. **When you add a new
  domain, add the import here.** Otherwise migrations will silently
  miss your tables.
- **`alembic.ini` / `alembic/`** — migrations.

## Schemas

One PostgreSQL schema per domain. Schemas are created ONCE by
`infra/docker/init-schemas.sql` (Postgres `initdb` hook) — Alembic
does not create them.

When adding a new schema:
1. Add it to `init-schemas.sql`.
2. Add it to `DOMAIN_SCHEMAS` in `alembic/env.py`.
3. Add the `models` import in `registry.py`.
4. `make db-revision M="add <domain>"` then `make db-upgrade`.

## Migrations — discipline

- **Never edit a migration that has been applied to any environment.**
  Add a new revision instead.
- One migration = one logical change (rename, add table, add column,
  data backfill). Splitting beats squashing.
- Data migrations belong in their own revisions, not bundled with
  schema changes.
- Always run a downgrade locally on a dev DB before merging.
- Generate via `make db-revision M="..."`; review the diff before
  committing — autogenerate is a draft, not a final answer.

## Sessions

- One engine per process; `engine` in `session.py` is it.
- `expire_on_commit=False` is intentional — service results stay
  usable after the caller commits.
- Repositories and services NEVER commit/rollback. Only the boundary
  (API dependency, worker job, script) does.
