# Contract — Semantic Context And Analytics Foundation

## Scope

This mission is ready to start the first planning wave once the user explicitly
approves worker launch. The first wave covers manager analytics questions,
semantic catalog, Data Intelligence Agent local tooling boundaries, and
frontend-readable documentation requirements for the Semantic Analytics
Workbench.

The catalog scope now includes a controlled proposal-review extension: Data
Intelligence Agent tools may surface unmapped values, source drift, linkage
gaps, and semantic mapping proposals, but approved business meaning is stored
only through reviewed, versioned catalog changes.

This contract does not itself launch workers, create implementation branches,
or modify product code.

## Architecture Constraints

- Follow root `CLAUDE.md` and `AGENTS.md`.
- Agents do not access the database directly.
- No raw SQL from LLM planners, dashboards, chat, or agents.
- Routes and jobs call services.
- Services call repositories.
- Repositories are data-only.
- PHI access goes through `PhiService` with audit.
- `identity.person.id` remains the canonical `person_uid`.
- `ops` remains PHI-free.
- Raw provider payloads remain evidence-first and are not ordinary production
  dashboard, chat, or agent output.
- Analytics business logic belongs in backend services/read models, not
  browser-only filters.
- Billing-sensitive and PHI-adjacent data must be classified before surfacing.
- Current production users are treated as authorized internal users for this
  mission phase. Row-level analytics outputs are allowed for them unless a
  later access-control policy narrows access. This does not remove
  service-layer checks, source references, data-class markings, or PHI audit
  requirements.
- Frontend workbench views may render documentation and review status, but they
  must not define metric business logic or bypass backend policy/service
  boundaries.
- No deployment, environment variable, secret, OAuth/CORS, Cloud Run, deploy
  script, or GitHub Actions changes are in scope.

## Linear Structure

Project:
[Semantic Context And Analytics Foundation](https://linear.app/fusion-dental-implants/project/semantic-context-and-analytics-foundation-b545bfd55250)

First milestone:
`Slice 1 — Manager Questions + Semantic Catalog`

Issues:

- A: [ENG-272](https://linear.app/fusion-dental-implants/issue/ENG-272/manager-analytics-questions-v1)
- B: [ENG-273](https://linear.app/fusion-dental-implants/issue/ENG-273/semantic-analytics-catalog-v1)
- B2: [ENG-313](https://linear.app/fusion-dental-implants/issue/ENG-313/semantic-catalog-proposal-review-v1)
  Semantic Catalog Proposal Review V1.
- C: [ENG-274](https://linear.app/fusion-dental-implants/issue/ENG-274/structured-analytics-query-spec)
- D: [ENG-275](https://linear.app/fusion-dental-implants/issue/ENG-275/analytics-policy-preflight)
- E: [ENG-276](https://linear.app/fusion-dental-implants/issue/ENG-276/analytics-query-registry-v1)
- F: [ENG-277](https://linear.app/fusion-dental-implants/issue/ENG-277/analytics-services-v1)
- G: [ENG-278](https://linear.app/fusion-dental-implants/issue/ENG-278/manager-analytics-read-models-v1)
- H: [ENG-279](https://linear.app/fusion-dental-implants/issue/ENG-279/data-intelligence-agent-v1)
- I: [ENG-280](https://linear.app/fusion-dental-implants/issue/ENG-280/manager-ai-chat-v1)
- J: [ENG-281](https://linear.app/fusion-dental-implants/issue/ENG-281/exports-and-saved-reports)
- K: [ENG-282](https://linear.app/fusion-dental-implants/issue/ENG-282/semantic-analytics-workbench-v1)

Semantic Catalog Proposal Review V1 child issues:

- [ENG-314](https://linear.app/fusion-dental-implants/issue/ENG-314/scr-01-catalog-proposal-and-version-storage)
  SCR-01 Catalog Proposal And Version Storage.
- [ENG-315](https://linear.app/fusion-dental-implants/issue/ENG-315/scr-02-catalog-review-api-contracts)
  SCR-02 Catalog Review API Contracts.
- [ENG-316](https://linear.app/fusion-dental-implants/issue/ENG-316/scr-03-catalog-review-ui-persistence)
  SCR-03 Catalog Review UI Persistence.
- [ENG-317](https://linear.app/fusion-dental-implants/issue/ENG-317/scr-04-review-audit-and-version-history)
  SCR-04 Review Audit And Version History.
- [ENG-318](https://linear.app/fusion-dental-implants/issue/ENG-318/scr-05-data-intelligence-proposal-ingestion)
  SCR-05 Data Intelligence Proposal Ingestion.
- [ENG-319](https://linear.app/fusion-dental-implants/issue/ENG-319/scr-06-impact-preview-from-registry-and-read-models)
  SCR-06 Impact Preview From Registry And Read Models.
- [ENG-320](https://linear.app/fusion-dental-implants/issue/ENG-320/scr-07-approved-catalog-consumption-path)
  SCR-07 Approved Catalog Consumption Path.
- [ENG-321](https://linear.app/fusion-dental-implants/issue/ENG-321/scr-08-verification-and-production-review)
  SCR-08 Verification And Production Review.

## Dependency Order

1. A: Manager Analytics Questions V1.
2. B: Semantic Analytics Catalog V1, blocked by A.
3. H: Data Intelligence Agent V1, runs in parallel as a tooling-boundary and
   local-read-only contract task.
4. B2: Semantic Catalog Proposal Review V1, blocked by B and informed by H.
   This closes the loop from real data profiles and gap briefs to human-reviewed
   catalog versions.
5. C: Structured Analytics Query Spec, blocked by B. Query spec may proceed
   from the initial catalog while B2 defines catalog evolution mechanics.
6. D: Analytics Policy Preflight, blocked by B and C.
7. E: Analytics Query Registry V1, blocked by C and D.
8. F: Analytics Services V1, blocked by D and E.
9. G: Manager Analytics Read Models V1, blocked by B and F.
10. I: Manager AI Chat V1, blocked by B, C, D, E, and F.
11. J: Exports And Saved Reports, blocked by D, E, F, and human export-policy
    decision.
12. K: Semantic Analytics Workbench V1, blocked by A and B producing stable
    frontend-readable docs.

## Worker Assignment Gate

Workers are not ready to be assigned. Assignment is blocked until:

- the user explicitly approves worker launch;
- the first execution issue is selected;
- ownership and allowed write scope are confirmed;
- any implementation worker has a Linear issue id and URL.

The recommended first worker set is:

- ENG-272: Manager Analytics Questions V1.
- ENG-273: Semantic Analytics Catalog V1.
- ENG-279: Data Intelligence Agent V1.
- ENG-282: Semantic Analytics Workbench V1 can begin as an early read-only UI
  shell after ENG-272 and ENG-273 stabilize documentation structure.
