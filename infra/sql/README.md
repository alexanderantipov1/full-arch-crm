# Infrastructure SQL migrations

This directory holds SQL files that change **database permissions / roles**
rather than schema DDL. Schema changes go through Drizzle (`npm run db:push`);
anything that's a `GRANT` / `REVOKE` / `CREATE ROLE` lives here.

These are applied manually as a DB superuser, once per environment, and
tracked by filename order. Idempotent — safe to re-run.

## Catalog

| File | Purpose |
|---|---|
| `001_audit_lockdown.sql` | Revokes UPDATE/DELETE/TRUNCATE on `audit_logs` from the app role. Append-only audit per HIPAA §164.312(b). |

## How to apply

```bash
psql "$DATABASE_URL" -f infra/sql/001_audit_lockdown.sql
```

For each new infra migration, append a row to the catalog and document
prerequisites in the file's header comment.
