# CareStack Developer API — local reference (v1.0.45)

Offline, searchable mirror of the CareStack Developer API spec,
rewritten into per-resource markdown so agents and developers don't
need to open the PDF. See `CLAUDE.md` in this folder for the usage
contract and editing rules.

- **Source:** `_source/carestack-v1.0.45.pdf`
- **Text dump:** `_source/carestack-v1.0.45.txt` (6366 lines, grep-friendly)
- **Version:** `v1.0.45` (dated Aug 04, 2025)

## Meta

- [`00-overview.md`](./00-overview.md) — transport, base URL, versioning
- [`01-authentication.md`](./01-authentication.md) — OAuth2 password grant
- [`02-conventions.md`](./02-conventions.md) — pagination, IDs, dates
- [`03-errors.md`](./03-errors.md) — error codes and response envelope
- [`glossary.md`](./glossary.md) — PHI tagging + CareStack → Fusion domain map
- [`NOTES.md`](./NOTES.md) — integration plan, open questions

## Resources

Each resource is one file under `resources/`. PHI column shows whether
any field of this resource carries protected health information in our
classification (see `glossary.md`).

| # | Resource | File | PHI |
|---|----------|------|-----|
| 1 | Location | [resources/locations.md](./resources/locations.md) | no |
| 2 | Referral source | [resources/referral-sources.md](./resources/referral-sources.md) | no |
| 3 | Patient | [resources/patients.md](./resources/patients.md) | **yes** |
| 4 | Appointment | [resources/appointments.md](./resources/appointments.md) | **yes** |
| 5 | Provider | [resources/providers.md](./resources/providers.md) | no |
| 6 | Payment summary | [resources/payment-summary.md](./resources/payment-summary.md) | mixed |
| 7 | Operatory | [resources/operatories.md](./resources/operatories.md) | no |
| 8 | Periodontal charting | [resources/periodontal-charting.md](./resources/periodontal-charting.md) | **yes** |
| — | *(Resource 9 absent in spec numbering)* | — | — |
| 10 | Procedure code | [resources/procedure-codes.md](./resources/procedure-codes.md) | no |
| 11 | Referral document | [resources/referral-documents.md](./resources/referral-documents.md) | **yes** |
| 12 | Insurance | [resources/insurance.md](./resources/insurance.md) | mixed |
| 13 | Medical alerts (allergies/conditions) | [resources/medical-alerts.md](./resources/medical-alerts.md) | **yes** |
| 14 | Patient medications | [resources/medications.md](./resources/medications.md) | **yes** |
| 15 | User | [resources/users.md](./resources/users.md) | no |
| 16 | Find slot | [resources/slots.md](./resources/slots.md) | no |
| 17 | Document | [resources/documents.md](./resources/documents.md) | **yes** |
| 18 | Vital monitor | [resources/vital-monitor.md](./resources/vital-monitor.md) | **yes** |
| 19 | Facility | [resources/facility.md](./resources/facility.md) | no |
| 20 | Adjustment | [resources/adjustments.md](./resources/adjustments.md) | mixed |
| 21 | Treatment plan | [resources/treatment-plans.md](./resources/treatment-plans.md) | **yes** |
| 22 | Patient notes / memo | [resources/patient-notes.md](./resources/patient-notes.md) | **yes** |
| 23 | Payment types | [resources/payment-types.md](./resources/payment-types.md) | no |

## Search APIs

Filtered one-shot lookups. See `search/`.

- [search/patients.md](./search/patients.md)
- [search/appointments.md](./search/appointments.md)

## Sync APIs — polling

All sync endpoints take `modifiedAfter` + pagination. Worker cron
jobs consume these and write into `ingest.raw_event`.

- [sync/README.md](./sync/README.md) — strategy, cadence, idempotency
- [sync/patients.md](./sync/patients.md)
- [sync/appointments.md](./sync/appointments.md)
- [sync/treatment-procedures.md](./sync/treatment-procedures.md)
- [sync/existing-treatment-procedures.md](./sync/existing-treatment-procedures.md)
- [sync/invoices.md](./sync/invoices.md)
- [sync/accounting-procedures.md](./sync/accounting-procedures.md)
- [sync/accounting-transactions.md](./sync/accounting-transactions.md)

## Insurance Manager (separate module)

Large sub-system for insurance plans, payors, coverage templates.
Defer to after MVP; own domain when we tackle billing.

- [insurance-manager/README.md](./insurance-manager/README.md)
- [insurance-manager/settings.md](./insurance-manager/settings.md)
- [insurance-manager/plan-coverages.md](./insurance-manager/plan-coverages.md)
- [insurance-manager/amb-codes.md](./insurance-manager/amb-codes.md)
- [insurance-manager/missing-tooth-clause.md](./insurance-manager/missing-tooth-clause.md)
- [insurance-manager/pre-auth-codes.md](./insurance-manager/pre-auth-codes.md)
- [insurance-manager/plans.md](./insurance-manager/plans.md)
- [insurance-manager/payors.md](./insurance-manager/payors.md) (28 endpoints)
- [insurance-manager/coverage-templates.md](./insurance-manager/coverage-templates.md)
- [insurance-manager/amb-templates.md](./insurance-manager/amb-templates.md)
- [insurance-manager/eligibility-rule-templates.md](./insurance-manager/eligibility-rule-templates.md)
- [insurance-manager/pre-auth-templates.md](./insurance-manager/pre-auth-templates.md)

## Counts (for reference)

- 52 markdown files, ~3500 lines total.
- 22 per-resource files, 2 search, 7 sync + sync README, 11 insurance-manager + README.
- Meta files: `CLAUDE.md`, `00-overview.md`, `01-authentication.md`,
  `02-conventions.md`, `03-errors.md`, `glossary.md`, `NOTES.md`.

## Known spec ambiguities (follow-ups)

See `NOTES.md → Open questions` for the full list. High-impact ones:
- Patient sync field shape — not listed in the sync section, cross-
  check with Resource 3.
- How deletions surface in sync feeds (no `isDeleted` flag seen).
- Soft-delete semantics across Patient / Appointment.
- Search vs Sync base paths inconsistencies (`/scheduler/`, `/billing/`).
- Several enum dictionaries missing (Provider type, Document type,
  Plan status/type, etc.).
