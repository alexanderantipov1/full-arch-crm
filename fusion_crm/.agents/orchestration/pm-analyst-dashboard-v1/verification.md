# PM/Analyst Dashboard V1 Verification

## Required Verification

Run the repository verification loop before integration:

```bash
make lint
mypy .
make test
cd packages/db && alembic check
```

If any check cannot run, the worker or verifier report must state the exact
blocker and residual risk.

## Focused Checks

- Backend filter/query tests for dashboard read models.
- Frontend schema, hook, and render tests for dashboard filters, search, and
  drilldowns.
- Person detail test proving the operational timeline endpoint is used.
- Salesforce enrichment tests for new allowlisted fields.
- CareStack treatment/payment classification tests before exposing dashboard
  aggregates.
- No raw provider payload, clinical note, or unreviewed clinical free text in
  dashboard API responses.
- Tenant isolation for dashboard queries.
- Read-only guarantee: no Salesforce or CareStack write path added.
