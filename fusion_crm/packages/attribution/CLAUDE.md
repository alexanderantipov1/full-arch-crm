# CLAUDE.md — `packages/attribution`

Derived lead-source attribution. Models a lead's origin as a hierarchical
distribution chain and a resolved per-lead attribution. Read the root
`CLAUDE.md` and `packages/CLAUDE.md` first.

Epic ENG-446. Design:
`.agents/strategy/LEAD_SOURCE_ATTRIBUTION_DESIGN.md`.

## Tables (schema `attribution`)

- **`source_node`** — controlled-vocab chain node. The chain is the
  `parent_id` ladder: ad → ad_set → campaign → channel → vendor. One row per
  `(tenant_id, level, slug)`. `level ∈ {vendor, channel, campaign, ad_set, ad,
  form}`.
- **`lead_attribution`** — the resolved chain for one lead, one row per
  `(tenant_id, person_uid)`. Denormalized levels (vendor_id … form_id) +
  `created_by_name` (manual creator) + `method` (auto|rule|manual) + `confidence` +
  `source_signal`. Denormalized so a funnel GROUP BY any level is one join.
- **`mapping_rule`** — editable `pattern → node` rules the resolver applies
  (e.g. `utm_campaign ILIKE 'Dima%' → vendor=Dima`). How the chain learns the
  vendor (not present in the source data).

## Hard rules

- **Derived data.** Everything here is re-buildable from raw evidence by the
  resolver. It is NOT a source of truth — `ingest.raw_event` is. Carries no
  PHI (field names / vocab only, never clinical values).
- **`person_uid` is a plain UUID** column referencing `identity.person.id`;
  no Python import of `identity` in the model layer.
- **Manual override is sticky.** A `method='manual'` row must not be clobbered
  by auto/rule re-resolution (`AttributionService.upsert_lead_attribution`).
- **Resolver reads, never writes, the source domains** (`ingest`, `identity`,
  `ops`); enrichment writes `audit`. Read-only SF pull guard-rail: attribution
  is never written back to Salesforce.
- Standard layering: routers/jobs → `AttributionService` → repository → DB.
  Repository is data-only; never commit/rollback below the boundary.

## Status

Block A (ENG-447) ships the schema + controlled-vocab seed
(`AttributionService.seed_default_nodes`). The waterfall resolver is ENG-448;
manual enrichment (rules + per-lead override endpoints) is ENG-449; funnel
analytics by chain level is ENG-450.
