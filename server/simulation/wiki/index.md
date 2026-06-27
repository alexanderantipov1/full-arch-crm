---
title: "Full-Arch CRM Knowledge Wiki — Index"
last_updated: 2026-06-27
total_pages: 2
total_source_events: 0
---

# Full-Arch CRM Knowledge Wiki

> **Architecture note:** This wiki lives in **full-arch-crm**, not in any individual clinic's database.
> It learns from ALL connected clinics (via their DatabaseAdapter implementations) and feeds
> anonymized intelligence back to each clinic's backend via the `/api/v1/intelligence/` endpoints.
> No real PHI ever enters this wiki — only aggregated, anonymized patterns.

## Quick Stats
- **Total pages:** 2
- **Last ingest:** 2026-06-27 00:00 UTC (bootstrap)
- **Highest-confidence category:** insurance (seeded)
- **Stalest page:** n/a — just bootstrapped

## Patient Intelligence
| Page | Confidence | Last Updated | Source Count |
|------|------------|--------------|--------------|
| _(no pages yet — populated after first simulation batch)_ | — | — | — |

## Clinical Intelligence
| Page | CDT | Confidence | Source Count |
|------|-----|------------|--------------|
| [[clinical/all-on-4-protocol.md]] | D6010, D6056, D6114 | medium | 1 |

## Insurance Intelligence
| Page | Payer Type | Confidence | Source Count |
|------|------------|------------|--------------|
| [[insurance/delta-dental.md]] | PPO | medium | 1 |

## DSO Intelligence
| Page | Confidence | Last Updated |
|------|------------|--------------|
| _(populated as clinics connect)_ | — | — |

## Agent Self-Improvement Logs
| Page | Avg Score | Last Updated |
|------|-----------|--------------|
| _(populated after first simulation cycle)_ | — | — |

## Competitor Intelligence
| Page | Threat Level | Last Updated |
|------|--------------|--------------|
| _(populated by competitive research)_ | — | — |

## Lint Status
- Last lint: 2026-06-27 00:00 UTC (bootstrap — no issues)
- Orphan pages: 0
- Contradiction flags: 0
- Stale pages (>90 days): 0
