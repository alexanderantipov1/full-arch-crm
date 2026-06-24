# CLAUDE.md — `packages/data_intelligence`

The Data Intelligence package owns service-level contracts for safe local data
profiling. It exists so internal agents can understand available CRM data
through approved services and tools without direct database access.

## Hard Rules

- Agents never call this package directly; they call `packages.tools`.
- This package must not expose raw SQL, SQL fragments, database credentials, or
  raw provider payload dumps.
- V1 denies PHI output. Any future PHI-capable lane must go through
  `PhiService` and audit, and requires explicit approval.
- Row-level local samples are allowed only through approved tools with caps,
  masking, and audit metadata.
- Services own policy and profiling semantics. Repositories, when added, must
  remain data-only and package-local.
- Outputs must carry data classes, output posture, limits, and masking posture.

## Scope

V1 starts with executable policy metadata and dataset discovery. Profiling,
linkage, evidence coverage, samples, mapping proposals, and gap briefs are
added behind the same service boundary.
