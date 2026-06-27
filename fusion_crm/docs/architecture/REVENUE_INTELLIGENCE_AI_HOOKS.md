# Revenue Intelligence AI Hooks (ENG-528)

Architecture hooks for the four future AI analytics capabilities on the Revenue
Intelligence platform. **No model code is built here.** This document records
the exact extension points a future model or agent must use.

## Core invariant

A future AI agent MUST consume analytics data through the
**services / tools layer only**. Direct database access by any agent is
prohibited (CLAUDE.md invariant #6). The tool `read_revenue_intelligence_page`
in `packages/tools/revenue_intelligence_tools.py` is the single approved entry
point for all four capabilities below.

---

## The four future capabilities and their extension points

### 1. No-show prediction

**Goal:** score the probability that a scheduled consultation or surgery will be
a no-show, so staff can call ahead or double-book a slot.

**Extension point:**

| Component | Detail |
|---|---|
| Tool | `read_revenue_intelligence_page` with `page="executive_overview"` or `page="attribution_analytics"` |
| Service method | `AnalyticsPagesService.executive_overview`, `AnalyticsPagesService.attribution_analytics` |
| Output DTOs | `ExecutiveOverviewOut`, `AttributionAnalyticsOut` (from `packages/analytics/metrics_service.py`) |
| Key signals | `show_rate`, per-source show rates in attribution breakdown, cohort retention |
| Filter contract | `AnalyticsFilters` (`packages/analytics/filters.py`): scope by `location_id`, `time_range`, `source`, `campaign_id` |

A future model consumes the page result dict, trains on historical show/no-show
labels from `FactPatientJourney.showed` (accessible via `AnalyticsPagesService`
— never direct SQL), and scores new records through the same tool call.

---

### 2. Treatment acceptance probability

**Goal:** estimate the probability that a given lead or consult converts to a
treatment plan being accepted (surgery booked and completed).

**Extension point:**

| Component | Detail |
|---|---|
| Tool | `read_revenue_intelligence_page` with `page="cohort_analytics"`, `page="doctor_performance"`, or `page="coordinator_performance"` |
| Service methods | `AnalyticsPagesService.cohort_analytics`, `AnalyticsPagesService.doctor_performance`, `AnalyticsPagesService.coordinator_performance` |
| Output DTOs | `CohortAnalyticsOut`, `DoctorPerformanceOut`, `CoordinatorPerformanceOut` |
| Key signals | `treatment_acceptance_rate` per doctor/coordinator, cohort revenue retention, consultation-to-surgery ratios |
| Filter contract | `AnalyticsFilters`: scope by `doctor_id`, `coordinator_id`, `location_id` |

The model consumes pre-computed acceptance rates from the analytics read model;
it does not query `fact_patient_journey` directly.

---

### 3. Budget allocation recommendation

**Goal:** recommend how to shift marketing spend across campaigns/vendors/sources
to maximize booked surgeries per dollar (CPL and surgery conversion signals).

**Extension point:**

| Component | Detail |
|---|---|
| Tool | `read_revenue_intelligence_page` with `page="cost_intelligence"`, `page="marketing_performance"`, `page="vendor_performance"`, or `page="revenue_intelligence"` |
| Service methods | `AnalyticsPagesService.cost_intelligence`, `AnalyticsPagesService.marketing_performance`, `AnalyticsPagesService.vendor_performance`, `AnalyticsPagesService.revenue_intelligence` |
| Output DTOs | `CostIntelligenceOut`, `MarketingPerformanceOut`, `VendorPerformanceOut`, `RevenueIntelligenceOut` |
| Key signals | `cost_per_lead`, `cost_per_surgery`, `show_rate`, `surgery_conversion_rate` per campaign/vendor |
| Filter contract | `AnalyticsFilters`: scope by `vendor_id`, `campaign_id`, `time_range` |

A recommendation agent would read multiple pages in sequence (one tool call per
page), synthesize the signals, and produce a reallocation proposal. All reads go
through `read_revenue_intelligence_page`; no intermediate DB writes.

---

### 4. Auto bottleneck / high-performer detection

**Goal:** automatically surface the largest stage-conversion drop and the
best-performing actor (caller, coordinator, doctor) for each time period without
manual configuration.

**Extension point:**

| Component | Detail |
|---|---|
| Tool | `read_revenue_intelligence_page` with `page="bottleneck_detection"`, `page="caller_performance"`, `page="coordinator_performance"`, or `page="doctor_performance"` |
| Service methods | `AnalyticsPagesService.bottleneck_detection`, `AnalyticsPagesService.caller_performance`, `AnalyticsPagesService.coordinator_performance`, `AnalyticsPagesService.doctor_performance` |
| Output DTOs | `BottlenecksOut` (includes `BottleneckOut` and entity-level rules), `CallerPerformanceOut`, `CoordinatorPerformanceOut`, `DoctorPerformanceOut` |
| Key signals | `severity` ("high"/"medium"/"low"), relative-drop rules, `_is_bottleneck` logic already in `metrics_service.py` |
| Filter contract | `AnalyticsFilters`: `time_range`, `location_id` |

The rule-based bottleneck engine already runs in `AnalyticsPagesService.bottleneck_detection`
(parameters `_RELATIVE_DROP = 0.40`, `_ABSOLUTE_FLOOR = 0.02`, severity
thresholds). A future AI layer would consume `bottleneck_detection` output and
compare it with prior-period baselines to produce natural-language narratives —
again via tool calls only.

---

## No-DB-access guardrail (how it is enforced)

1. `packages/tools/revenue_intelligence_tools.py` imports ONLY services:
   `AnalyticsPagesService`, `FactAnalyticsQueries`, `MarketingService`,
   `TenantService`, `LocationService`, `AuditService`. It does NOT import any
   SQLAlchemy model, repository, or `AsyncSession` query method directly.
2. `FactAnalyticsQueries` is constructed inside `_build_pages_service(ctx)`,
   receiving `ctx.session` (the tool-runtime session injected by the agent
   harness) — the tool never opens its own connection.
3. All thirteen pages are dispatched through `AnalyticsPagesService` method
   calls whose internals live behind the service boundary.
4. The tool is registered in `packages/tools/registry.py` (`ALL_TOOLS`) with
   `touches=frozenset({"ops", "billing", "interaction"})` — the governance
   layer can gate it without touching the tool itself.
5. `AuditService.record_tool_call` is called on every invocation, recording
   `page`, `time_range`, and whether a location filter was applied — PHI-free.

---

## File map

| File | Role |
|---|---|
| `packages/tools/revenue_intelligence_tools.py` | Tool implementation (ENG-528) |
| `packages/tools/registry.py` | Registration in `ALL_TOOLS` |
| `packages/analytics/metrics_service.py` | `AnalyticsPagesService` — the service the tool delegates to |
| `packages/analytics/filters.py` | `AnalyticsFilters` — shared filter contract |
| `packages/analytics/queries.py` | `FactAnalyticsQueries` — query layer (no agent access) |
| `docs/architecture/REVENUE_INTELLIGENCE_AI_HOOKS.md` | This document |
