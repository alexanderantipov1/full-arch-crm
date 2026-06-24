import { describe, expect, it } from "vitest";
import type { AgentRuntimeLlmExecution } from "@/lib/api/schemas/agentRuntime";
import {
  ManagerAnalyticsVisualizationBuildSchema,
  buildManagerAnalyticsVisualizations,
} from "@/lib/agentRuntime/visualizations";

describe("Agent Runtime manager analytics visualizations", () => {
  it("builds lead conversion KPI and bucket chart specs from aggregate output", () => {
    const build = buildManagerAnalyticsVisualizations(
      execution({
        query_id: "lead_conversion_funnel.v1",
        read_model_id: "lead_conversion",
        result: {
          lead_status: [
            { key: "new", label: "New", count: 28 },
            { key: "booked", label: "Booked", count: 11 },
          ],
          consultation_status: [
            { key: "scheduled", label: "Scheduled", count: 11 },
            { key: "completed", label: "Completed", count: 7 },
          ],
          pipeline_total: 28,
          consultations_total: 11,
          completed_consultations: 7,
        },
      }),
    );

    expect(() =>
      ManagerAnalyticsVisualizationBuildSchema.parse(build),
    ).not.toThrow();
    expect(build.unavailable_reason).toBeNull();
    expect(build.specs.map((item) => item.id)).toEqual([
      "lead_conversion.kpis",
      "lead_conversion.lead_status",
      "lead_conversion.consultation_status",
    ]);
    expect(build.specs[0]?.data.map((item) => item.value)).toEqual([28, 11, 7]);
    expect(build.specs[1]?.data[0]).toMatchObject({
      label: "New",
      value: 28,
      source_path: "result.lead_status[0].count",
    });
    expect(build.specs[0]?.time_window?.preset).toBe("this_week");
  });

  it("builds paid leads horizontal bar specs from approved source buckets", () => {
    const build = buildManagerAnalyticsVisualizations(
      execution({
        query_id: "paid_leads_by_source.v1",
        read_model_id: "paid_leads",
        result: {
          total_paid_leads: 42,
          sources: [
            { key: "google", label: "Google", count: 31 },
            { key: "meta", label: "Meta", count: 11 },
          ],
          classification_terms: ["google", "meta"],
        },
      }),
    );

    expect(build.unavailable_reason).toBeNull();
    expect(build.specs.map((item) => item.kind)).toEqual([
      "kpi_grid",
      "horizontal_bar_chart",
    ]);
    expect(build.specs[1]?.data.map((item) => item.label)).toEqual([
      "Google",
      "Meta",
    ]);
  });

  it("does not build charts for non-executed or non-aggregate output", () => {
    const build = buildManagerAnalyticsVisualizations({
      ...execution({
        query_id: "lead_conversion_funnel.v1",
        read_model_id: "lead_conversion",
        result: {},
      }),
      status: "clarification_required",
    });

    expect(build.specs).toEqual([]);
    expect(build.unavailable_reason).toBe(
      "Visualization requires approved aggregate execution.",
    );
  });
});

function execution(input: {
  query_id: string;
  read_model_id: string;
  result: Record<string, unknown>;
}): AgentRuntimeLlmExecution {
  return {
    status: "executed",
    tool_id: "ask_manager_analytics",
    query_id: input.query_id,
    read_model_id: input.read_model_id,
    match_status: "matched",
    match_confidence: "high",
    match_reason: "Matched approved query.",
    matched_keywords: ["conversion"],
    output_type: "aggregate",
    data_classes: ["ops", "integration_metadata"],
    row_count: 2,
    explanation: "Executed approved aggregate query.",
    policy_reason: "Allowed.",
    result: {
      query_id: input.query_id,
      read_model_id: input.read_model_id,
      output_type: "aggregate",
      aggregation_level: "aggregate",
      data_classes: ["ops", "integration_metadata"],
      filters: {
        created_from: "2026-06-08T00:00:00+00:00",
        created_to: "2026-06-09T12:00:00+00:00",
      },
      time_window: {
        source: "semantic",
        preset: "this_week",
        created_from: "2026-06-08T00:00:00+00:00",
        created_to: "2026-06-09T12:00:00+00:00",
        disclosure: "Applied semantic time window: this_week.",
      },
      result: input.result,
    },
  };
}
