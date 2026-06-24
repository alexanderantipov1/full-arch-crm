# CLAUDE.md — `packages/tools` (AI-agent surface)

The ONLY surface AI agents are allowed to call. Anything an agent
does to the platform must come through a tool registered here.

## Files

- **`base.py`** — `ToolContext` (principal + session) and `ToolSpec`.
- **`person_tools.py`** — `resolve_person`.
- **`ops_tools.py`** — `get_ops_person_snapshot`,
  `create_followup_task`.
- **`analytics_tools.py`** — `run_analytics_query`, the approved
  aggregate analytics query runner. It accepts only registry-backed
  `query_id` values and structured params; it never accepts SQL.
- **`semantic_time.py`** — shared Semantic Time Constraints helpers for
  governed tools and agent runtime manager analytics. Keep EN/RU/ES
  time-window marker semantics here instead of duplicating them in
  runtime or tool entry points.
- **`manager_chat_tools.py`** — `ask_manager_analytics`, the
  deterministic V1 manager-chat planner/executor over approved
  aggregate analytics queries.
- **`export_tools.py`** — `export_analytics_csv` and
  `save_analytics_report_definition`, the ENG-281 aggregate-only CSV
  export and saved-report-definition tools. XLSX, scheduled reports,
  row-level exports, PHI, and raw payload exports are disabled in V1.
- **`data_intelligence_tools.py`** — `data_intelligence_discover`,
  `data_intelligence_preflight`, `data_intelligence_profile_field`, and
  `data_intelligence_linkage_coverage`, and
  `data_intelligence_evidence_coverage`, and
  `data_intelligence_bounded_sample`, and
  `data_intelligence_semantic_mapping_proposal`, and
  `data_intelligence_person_journey_proposals`, and
  `data_intelligence_gap_brief`, the Data Intelligence local tooling policy,
  discovery, field-profile, source-linkage coverage, evidence coverage,
  bounded masked sample, review-only semantic mapping proposal, review-only
  person journey registry projection, and non-sensitive gap brief surface.
  V1 denies raw SQL, direct DB access, raw payload output, PHI output, exports,
  writes, and uncapped samples.
- **`phi_tools.py`** — `get_phi_person_snapshot` (PHI-gated).
- **`registry.py`** — `ALL_TOOLS` dict; the single source of truth
  for what an agent can see.

## Hard rules

- **Tools call services. Tools NEVER touch repositories or
  `session.execute(...)` directly.** If you find yourself reaching
  for a query in this package, push it down into a service.
- **Tools NEVER open their own DB session.** They use
  `ctx.session`. The unit-of-work commits at the caller boundary
  (API or job).
- **Every tool emits an audit row.** PHI tools rely on `PhiService`
  to write the row (do NOT double-log). Non-PHI tools call
  `AuditService.record_tool_call(...)` themselves.
- **Tool inputs are JSON-friendly** (str/int/bool/dict/list).
  Accept `str | UUID` for ids; convert via `_to_uid()`.
- **Outputs are JSON-friendly dicts** built from `pydantic` schemas
  (`.model_dump(mode="json")`).
- **Register every new tool in `ALL_TOOLS`.** A tool that isn't
  in the registry must not be reachable.
- **Touches metadata** (`ToolSpec.touches`) is for governance —
  set it correctly so future role-based tool gating works.

## Adding a new tool — checklist

1. Decide which domain it belongs to → file lives in
   `<area>_tools.py`.
2. Signature: `async def <name>(ctx: ToolContext, *, ...) -> dict`.
3. Call services only.
4. Emit an audit row (or rely on `PhiService` if it's a PHI tool).
5. Register in `registry.ALL_TOOLS` with a descriptive
   `description` and the correct `touches`.
6. If the tool can mutate state, document the side effects in the
   `description` — agents read those.

## Anti-patterns to refuse

- Bypassing the tool layer ("just let the agent run SQL") — refuse,
  propose a new tool instead.
- A tool that combines `ops` + `phi` outputs into one return value —
  split it: agents holding only ops scope must not receive PHI
  fields by accident.
- A tool that takes a free-form `query: str` for the DB.
