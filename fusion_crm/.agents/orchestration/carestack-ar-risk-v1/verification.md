# Verification — ENG-266 (AR-risk count)

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift — this slice adds no migration
```

Focused checks:
- AR-risk count uses ONLY the latest snapshot per patient (not every snapshot).
- Threshold boundary: a patient exactly AT the threshold is excluded; strictly
  above is counted (or document the chosen inclusive/exclusive rule).
- Tenant scoping: a tenant only counts its own patients.
- Dashboard: `ar_risk_count` is an int (not None) when carestack data exists and
  provider filter is None/carestack; stays None/0 for a salesforce-only filter
  per the existing pattern.
- No patient identifiers / PHI in the dashboard response or logs.
