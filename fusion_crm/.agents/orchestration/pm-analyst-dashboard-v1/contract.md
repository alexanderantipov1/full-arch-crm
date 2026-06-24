# PM/Analyst Dashboard V1 Contract

## Architecture Contract

- Keep `identity.person.id` as the canonical `person_uid`.
- Provider payloads stay in `ingest.raw_event`.
- Dashboard data must come from canonical services/read models, not raw
  provider payloads or hot-path provider calls.
- No business logic in API routes.
- `ops` remains PHI-free. If treatment/payment data requires a new canonical
  domain or gated service access, make that explicit before implementation.
- Salesforce and CareStack remain read-only in this mission.
- No deployment, environment variable, secret, OAuth URL, Cloud Run, or GitHub
  Actions changes unless explicitly re-scoped after reading
  `docs/DEPLOYMENT_RULES.md`.

## Dashboard Contract

The first dashboard must support:

- Date range filter.
- Business unit filter.
- Location/center filter.
- Lead source or UTM filter.
- Owner/TC owner filter when available.
- Normalized stage filter.
- Consultation status filter.
- Treatment/payment status filter where available.
- Source provider filter.
- Authenticated staff search by name, phone, email, Salesforce id, and
  CareStack patient id.
- KPI row.
- Lead-to-consult funnel.
- Business unit, center, and lead-source breakdowns.
- Risk list.
- Sync health.
- Recent activity / operational timeline entry points.
- Drilldowns from metric counts to the rows behind the count.

## Treatment/Payment Contract

Treatment/payment visibility is required for PMs and analysts. It must be
implemented as a read-only, classified slice:

- Verify CareStack endpoint availability and payload shapes first.
- Decide canonical domain and service boundary before schema changes.
- Expose dashboard-safe aggregates before row-level detail.
- Keep raw payloads and clinical free text out of dashboard responses.
- Record any PHI/billing-sensitive access boundary in docs and tests.

## Worker Gate

Every execution task needs a Linear issue id and URL before assignment. If
Linear remains unavailable, the Orchestrator must keep the mission blocked or
obtain explicit human approval for a no-Linear exception.
