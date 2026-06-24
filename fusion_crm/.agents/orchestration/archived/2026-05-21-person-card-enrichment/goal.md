# Mission Goal — Person Card Enrichment (ENG-218)

Surface "where does this person live in Salesforce and CareStack" directly
on `/persons/[uid]`, with deep-links into the providers and a React Flow
identity graph visualization.

## Source

- Linear: ENG-218 (child of ENG-216 umbrella)
- Predecessor: ENG-217 (PR #84, merged 23:42Z) — shipped ops.consultation
  domain that this page reads.

## Outcome

1. Per-source-link "Open in {provider}" link via `providerUrlFor()` helper.
2. New `<IdentityGraphModal>` (React Flow over the existing
   `buildIdentityMergeGraph` builder) — "Identity graph" button on card.
3. Consultations card re-sorted: future scheduled first, past second.
4. SourceLink Zod schema gains optional `provider_url` (backend-supplied
   when ready; client-synthesized via fallback today).
5. Vitest coverage for `providerUrlFor` and `IdentityGraphModal`.
6. Navigation `/people/search → /persons/{uid}` confirmed working
   (existing `LinkedPersonStrip` already does this — no change).

## Constraints

- No backend changes in this PR (real `/persons/{uid}` endpoint comes
  later; MSW continues mocking for local dev).
- Provider URLs are client-public — never include secrets.
- No PHI in consultation card.
- Repository files in English.
