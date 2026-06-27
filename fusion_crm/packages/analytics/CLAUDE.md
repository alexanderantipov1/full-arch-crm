# CLAUDE.md — `packages/analytics`

This package owns route-facing backend contracts for governed analytics
semantics: catalog proposal review API DTOs, review service orchestration, and
later analytics service boundaries. Durable semantic catalog storage belongs in
`packages/insight`.

## Scope

- Keep analytics business meaning in services, never in API routes or frontend
  draft state.
- Proposal review contracts are tenant-scoped and PHI-denying by default.
- Unreviewed proposals must never become production metric truth.
- Approved catalog reads are the only catalog state that dashboard, chat,
  services, and agent tools may consume.

## Layering

- API routes depend on `AnalyticsCatalogReviewService`.
- Services depend on repository protocols plus cross-cutting services when
  needed.
- Repositories are data-only and own storage adaptation.
- Data Intelligence Agent tools may submit proposals through services only;
  they must not approve proposals.

## Storage Status

The API-facing `AnalyticsCatalogReviewService` is wired to
`packages.insight.InsightCatalogService` in FastAPI dependency injection, so
catalog proposal review state is durable in the `insight` schema. The
in-memory repository remains only for focused contract tests and local shape
validation.

## Safety

- Do not import `phi`; PHI-capable catalog review requires a separate approved
  lane.
- Do not expose raw provider payloads as ordinary review output.
- Review actions that deny or reject a transition must raise a `PlatformError`
  subclass so the API returns the standard error envelope.
