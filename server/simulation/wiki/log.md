# Full-Arch CRM Wiki — Append-Only Event Log

Every ingest, query, and lint pass appends a structured entry here.
Agents grep this log for patterns. Do not edit existing entries — append only.

Grep helpers:
```bash
grep "^## \[" log.md | tail -10
grep "^## \[.*\] lint" log.md
grep "^## \[.*\] ingest" log.md
```

---

## [2026-06-27 00:00 UTC] bootstrap | system | initial-setup
- **Trigger:** Repository initialization — feature/fusion-client branch
- **Architecture:** Wiki lives in full-arch-crm (universal SaaS layer). Learns from all connected clinics via DatabaseAdapter. Pushes anonymized patterns back to each clinic's backend via /api/v1/intelligence/ endpoints.
- **Pages created:**
  - [[AGENTS.md]] — wiki schema + operational contract (from AGENTS_WIKI_SCHEMA.md)
  - [[index.md]] — initial catalog
  - [[log.md]] — this file
  - [[insurance/delta-dental.md]] — seed: Delta Dental PPO patterns for D6010
  - [[clinical/all-on-4-protocol.md]] — seed: All-on-4 procedure intelligence
  - Directory stubs: patients/, clinical/, insurance/, dso/, agents/, competitors/
- **Key insight:** fusion_crm is Fusion Dental's specific adapter. Any other clinic builds their own adapter implementing DatabaseAdapter. Wiki aggregates intelligence across all of them.
- **Connected adapters at bootstrap:** FusionCrmAdapter (mock mode until FUSION_CRM_URL set)
