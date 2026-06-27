# Mission Contract

## Parent Umbrella

- Linear project: `Semantic Context And Analytics Foundation`
- Project URL:
  `https://linear.app/fusion-dental-implants/project/semantic-context-and-analytics-foundation-b545bfd55250`
- Mission parent issue: ENG-286

## Hard Constraints

- Agents do not access the database directly.
- No raw SQL from agents, LLM planners, dashboard code, chat, or workbench code.
- Tools call services only.
- Tools must not call repositories or `session.execute(...)`.
- Routes and jobs call services; services call repositories.
- PHI access goes through `PhiService` with audit; PHI is denied for this V1
  mission unless separately approved.
- Raw provider payloads remain evidence storage and are not ordinary outputs.
- Row-level local samples are allowed only for authorized internal builders
  through approved tools, with caps, masks, and audit/logging.
- `.agents/` must not become a production product runtime dependency.
- Exports, XLSX, scheduled reports, and broad production role matrices are out
  of scope.

## Default Policy

- Environment: local/dev first.
- Role: authorized internal builder.
- Default row sample limit: 25.
- Hard row sample cap: 100.
- Default top-value cap: 50.
- Hard profile group cap: 250.
- Date window default: 365 days.
- Export: denied.
- Raw payload output: denied.
- PHI: denied.
- Audit/logging: required for every tool call.

## Dependency Order

1. ENG-287 / DIA-01 Mission Setup And Linear Sync.
2. ENG-288 / DIA-02 Tool Policy And Allowlist.
3. ENG-289 / DIA-03 Data Intelligence Service Contract.
4. ENG-290 / DIA-04 Query Registry And Dataset Discovery Tool.
5. ENG-291 / DIA-05 Field Profile Tool.
6. ENG-292 / DIA-06 Linkage And Source Coverage Tool.
7. ENG-293 / DIA-07 Evidence Coverage Tool.
8. ENG-294 / DIA-08 Bounded Masked Sample Tool.
9. ENG-295 / DIA-09 Semantic Mapping Proposal Generator.
10. ENG-296 / DIA-10 Gap Brief Writer.
11. ENG-297 / DIA-11 Audit And Tool Call Logging.
12. ENG-298 / DIA-12 Local Workbench Visibility.
13. ENG-299 / DIA-13 Verification And Production Review.

ENG-291, ENG-292, and ENG-293 may run in parallel after ENG-288 through
ENG-290 if the Orchestrator assigns disjoint file ownership. ENG-297 must be
integrated into every executable tool before mission completion.

## Worker Gate

Workers are blocked until the human explicitly approves execution after this
Linear structure exists.
