---
title: "Full-Arch CRM Knowledge Wiki — Index"
last_updated: 2026-06-27
total_pages: 18
total_source_events: 0
---

# Full-Arch CRM Knowledge Wiki

> **Architecture note:** This wiki lives in **full-arch-crm**, not in any individual clinic's database.
> It learns from ALL connected clinics (via their DatabaseAdapter implementations) and feeds
> anonymized intelligence back to each clinic's backend via the `/api/v1/intelligence/` endpoints.
> No real PHI ever enters this wiki — only aggregated, anonymized patterns.

## Quick Stats
- **Total pages:** 18
- **Last ingest:** 2026-06-27 00:00 UTC (bootstrap)
- **Highest-confidence category:** insurance (seeded)
- **Stalest page:** n/a — just bootstrapped

## Patient Intelligence
| Page | Confidence | Last Updated | Source Count |
|------|------------|--------------|--------------|
| [[patients/implant-consult]] | medium | 2026-06-27 | 3 |
| [[patients/treatment-decline]] | medium | 2026-06-27 | 2 |
| [[patients/financial-barrier]] | medium | 2026-06-27 | 2 |
| [[patients/insurance-issue]] | medium | 2026-06-27 | 2 |
| [[patients/recall-overdue]] | medium | 2026-06-27 | 2 |
| [[patients/new-patient]] | low | 2026-06-27 | 1 |
| [[patients/emergency]] | low | 2026-06-27 | 1 |
| [[patients/dso-referral]] | low | 2026-06-27 | 1 |

## Clinical Intelligence
| Page | CDT | Confidence | Source Count |
|------|-----|------------|--------------|
| [[clinical/all-on-4-protocol]] | D6010, D6056, D6114 | medium | 1 |

## Insurance Intelligence
| Page | Payer Type | Confidence | Source Count |
|------|------------|------------|--------------|
| [[insurance/ppo-general]] | PPO (all payers) | medium | 2 |
| [[insurance/delta-dental]] | PPO — Delta Dental | medium | 1 |
| [[insurance/appeals/ppo-d6010]] | Appeal Template | medium | 2 |

## DSO Intelligence
| Page | Confidence | Last Updated |
|------|------------|--------------|
| _(populated as clinics connect)_ | — | — |

## Agent Self-Improvement Logs
| Page | Avg Score | Last Updated |
|------|-----------|--------------|
| [[agents/InsuranceAgent]] | 31/40 | 2026-06-27 |
| [[agents/TreatmentPlanAgent]] | 27/40 | 2026-06-27 |
| [[agents/SchedulingAgent]] | 30/40 | 2026-06-27 |
| [[agents/FinancialCounselorAgent]] | 27/40 | 2026-06-27 |
| [[agents/RecallAgent]] | 27/40 | 2026-06-27 |
| [[agents/PatientAcquisition]] | 26/40 | 2026-06-27 |

## Competitor Intelligence
| Page | Threat Level | Last Updated |
|------|--------------|--------------|
| _(populated by competitive research)_ | — | — |

## Lint Status
- Last lint: 2026-06-27 00:00 UTC (bootstrap — no issues)
- Orphan pages: 0
- Contradiction flags: 0
- Stale pages (>90 days): 0
