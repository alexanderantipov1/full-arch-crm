# Insurance Manager — CareStack API

Insurance Manager is a large sub-module of the CareStack Developer API
that covers the full insurance-configuration surface: account-wide
insurance settings, insurance plans (benefits, coverages, AMB codes,
missing-tooth clauses, pre-authorization codes, fee-schedule
assignments), payors (addresses, AMB codes, eligibility rules,
pre-authorization codes, provider-insurance links, payor types,
payor coverage), and reusable templates (coverage, AMB, eligibility
rule, pre-authorization).

**Source:** CareStack Developer API v1.0.45 — section "Insurance
Manager" (covers TOC items 1 through 11). Extracted from
`_source/carestack-v1.0.45.txt`.

## Index

| Group | File | Spec section |
|---|---|---|
| Insurance Settings | `settings.md` | 1.1 – 1.2 |
| Insurance Plan Coverages | `plan-coverages.md` | 2.1 – 2.2 |
| Insurance Plan AMB Codes | `amb-codes.md` | 3.1 – 3.2 |
| Missing Tooth Clause | `missing-tooth-clause.md` | 4.1 – 4.2 |
| Plan Pre-Auth Codes | `pre-auth-codes.md` | 5.1 – 5.2 |
| Insurance Plan | `plans.md` | 6.1 – 6.11 |
| Payors | `payors.md` | 7.1 – 7.28 |
| Coverage Templates | `coverage-templates.md` | 8.1 – 8.6 |
| AMB Code Templates | `amb-templates.md` | 9.1 – 9.6 |
| Eligibility Rule Templates | `eligibility-rule-templates.md` | 10.1 – 10.6 |
| Pre-Authorization Templates | `pre-auth-templates.md` | 11.1 – 11.6 |

## Fusion positioning

This entire module belongs to a future `billing` domain (see the root
`glossary.md`). It is **not** required for MVP. Defer until after the
CareStack patient and appointment synchronisation flows land and the
clinic actually needs insurance-aware estimation, claims, or
eligibility checking inside Fusion.

When `billing` eventually lands, these groups will most likely become:

- `billing.insurance_settings` (singleton account-level record)
- `billing.insurance_plan`, `billing.insurance_plan_benefit`,
  `billing.insurance_plan_coverage`
- `billing.payor`, `billing.payor_address`, `billing.payor_type`
- `billing.*_template` tables for coverage / AMB / eligibility / pre-auth

Exact column layout is TBD — plan by plan, after live CareStack data
is inspected.

## PHI stance

Most of this module is **directory-like configuration**: insurance
plans, payors, payor types, payor addresses, coverage / AMB /
eligibility / pre-auth templates. These are clinic-wide reference data
and are **not PHI** on their own.

The PHI boundary inside Insurance Manager is narrow:

- None of the 11 groups below are patient-scoped. They all operate on
  `planId`, `payorId`, `templateId` — never a `patientId`.
- Patient-scoped coverage (a patient's actual insurance subscription)
  is handled in the `Patient Insurance` resource and is documented
  under `resources/`, not here.

So for this sub-module the PHI answer is uniformly **no** — configuration
only. If a future CareStack version adds patient-bound endpoints in
this section, update the affected file's PHI header.

## Paths and versioning

All endpoints in this module use the prefix
`insurance/api/v1.0/...` (note: `insurance/api`, not just `api/`).
Permissions listed per endpoint are CareStack role permission codes
and must be granted to the integration user.
