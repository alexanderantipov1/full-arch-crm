# CLAUDE.md — `packages/insight`

Semantic analytics and governed business-meaning storage.

## Tables (schema `insight`)

- **`semantic_catalog_proposal`** — review inbox for candidate semantic
  mappings, source-drift briefs, and gap briefs. Proposals are not business
  truth until approved by a human reviewer through `InsightCatalogService`.
- **`semantic_catalog_version`** — immutable approved catalog entries. Each
  approval creates a new row with a monotonic `(tenant_id, term, version)`
  number, previous/new snapshots, reviewer actor, timestamp, reason, and
  affected analytics metadata.

## Hard Rules

- Unreviewed proposals must never be returned as approved business truth.
- Approved catalog truth is read from `semantic_catalog_version`, not from
  proposal rows or browser draft state.
- Agents may create proposals through services, but agents must not approve
  proposals by themselves.
- No raw SQL from LLM planners, dashboards, chat, or agents. Repository methods
  use SQLAlchemy expression APIs and expose data-only operations.
- PHI is not in scope for this domain. If future analytics require PHI, the
  read path must go through `PhiService` with audit before any insight service
  consumes the result.
- Version rows are append-only at the service layer. Do not add service methods
  that update or delete approved versions.

## Service Surface

`InsightCatalogService.create_proposal(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.list_proposals(...) -> list[SemanticCatalogProposalOut]`
`InsightCatalogService.get_proposal(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.update_proposal(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.approve_proposal(...) -> CatalogApprovalOut`
`InsightCatalogService.reject_proposal(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.mark_proposal_unresolved(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.mark_proposal_proposed(...) -> SemanticCatalogProposalOut`
`InsightCatalogService.list_approved_catalog_entries(...) -> list[SemanticCatalogVersionOut]`

Audit for route-facing review actions is written by the analytics catalog
review service through write-only `AuditService`; insight remains the durable
catalog storage service.
