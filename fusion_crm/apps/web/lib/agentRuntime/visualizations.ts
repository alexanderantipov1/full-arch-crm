import { z } from "zod";
import type { AgentRuntimeLlmExecution } from "@/lib/api/schemas/agentRuntime";

export const ManagerAnalyticsVisualizationKindSchema = z.enum([
  "kpi_grid",
  "bar_chart",
  "horizontal_bar_chart",
]);

export const ManagerAnalyticsVisualizationDatumSchema = z.object({
  key: z.string().min(1).max(160),
  label: z.string().min(1).max(160),
  value: z.number().finite().nonnegative(),
  unit: z.string().max(80).nullable().default(null),
  source_path: z.string().min(1).max(240),
});

export const ManagerAnalyticsVisualizationTimeWindowSchema = z
  .object({
    source: z.string().min(1).max(80),
    preset: z.string().min(1).max(80),
    created_from: z.string().nullable().default(null),
    created_to: z.string().nullable().default(null),
    disclosure: z.string().nullable().default(null),
  })
  .nullable()
  .default(null);

export const ManagerAnalyticsVisualizationSpecSchema = z.object({
  id: z.string().min(1).max(160),
  kind: ManagerAnalyticsVisualizationKindSchema,
  title: z.string().min(1).max(160),
  description: z.string().max(300).nullable().default(null),
  query_id: z.string().min(1).max(160),
  read_model_id: z.string().min(1).max(160),
  time_window: ManagerAnalyticsVisualizationTimeWindowSchema,
  data: z.array(ManagerAnalyticsVisualizationDatumSchema).min(1),
});

export const ManagerAnalyticsVisualizationBuildSchema = z.object({
  specs: z.array(ManagerAnalyticsVisualizationSpecSchema),
  unavailable_reason: z.string().max(240).nullable().default(null),
});

export type ManagerAnalyticsVisualizationSpec = z.infer<
  typeof ManagerAnalyticsVisualizationSpecSchema
>;
export type ManagerAnalyticsVisualizationBuild = z.infer<
  typeof ManagerAnalyticsVisualizationBuildSchema
>;

export function buildManagerAnalyticsVisualizations(
  execution: AgentRuntimeLlmExecution | null | undefined,
): ManagerAnalyticsVisualizationBuild {
  if (!execution || execution.status !== "executed") {
    return {
      specs: [],
      unavailable_reason:
        "Visualization requires approved aggregate execution.",
    };
  }
  if (execution.output_type !== "aggregate" || !execution.result) {
    return {
      specs: [],
      unavailable_reason:
        "Visualization is available only for aggregate execution output.",
    };
  }

  const envelope = execution.result;
  if (optionalString(envelope.output_type) !== "aggregate") {
    return {
      specs: [],
      unavailable_reason:
        "Visualization skipped because the execution envelope is not aggregate.",
    };
  }

  const result = envelope.result;
  if (!isRecord(result)) {
    return {
      specs: [],
      unavailable_reason:
        "Visualization skipped because aggregate result data is unavailable.",
    };
  }

  const queryId = optionalString(envelope.query_id) ?? execution.query_id;
  const readModelId =
    optionalString(envelope.read_model_id) ?? execution.read_model_id;
  if (!queryId || !readModelId) {
    return {
      specs: [],
      unavailable_reason:
        "Visualization skipped because query/read-model refs are unavailable.",
    };
  }

  const timeWindow = visualizationTimeWindow(envelope);
  const specs =
    queryId === "lead_conversion_funnel.v1"
      ? leadConversionSpecs(queryId, readModelId, result, timeWindow)
      : queryId === "paid_leads_by_source.v1"
        ? paidLeadsSpecs(queryId, readModelId, result, timeWindow)
        : queryId === "lead_source_profile.v1"
          ? leadSourceSpecs(queryId, readModelId, result, timeWindow)
          : queryId === "consultation_followup_worklist.v1"
            ? consultationFollowupSpecs(
                queryId,
                readModelId,
                result,
                timeWindow,
              )
            : [];

  if (specs.length === 0) {
    return {
      specs: [],
      unavailable_reason:
        "No approved visualization spec exists for this aggregate result yet.",
    };
  }

  return ManagerAnalyticsVisualizationBuildSchema.parse({
    specs,
    unavailable_reason: null,
  });
}

function leadConversionSpecs(
  queryId: string,
  readModelId: string,
  result: Record<string, unknown>,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
): ManagerAnalyticsVisualizationSpec[] {
  const kpis = numberDatums(result, [
    ["pipeline_total", "Leads added to pipeline", "leads"],
    ["consultations_total", "Total consultations", "consultations"],
    ["completed_consultations", "Completed consultations", "consultations"],
  ]);
  return compactSpecs([
    spec(queryId, readModelId, timeWindow, {
      id: "lead_conversion.kpis",
      kind: "kpi_grid",
      title: "Lead conversion KPIs",
      description:
        "Approved aggregate totals from the lead conversion read model.",
      data: kpis,
    }),
    bucketSpec(queryId, readModelId, timeWindow, result, {
      id: "lead_conversion.lead_status",
      kind: "bar_chart",
      title: "Lead status",
      description: "Lead buckets from the approved aggregate result.",
      sourceKey: "lead_status",
    }),
    bucketSpec(queryId, readModelId, timeWindow, result, {
      id: "lead_conversion.consultation_status",
      kind: "bar_chart",
      title: "Consultation status",
      description: "Consultation buckets from the approved aggregate result.",
      sourceKey: "consultation_status",
    }),
  ]);
}

function paidLeadsSpecs(
  queryId: string,
  readModelId: string,
  result: Record<string, unknown>,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
): ManagerAnalyticsVisualizationSpec[] {
  return compactSpecs([
    spec(queryId, readModelId, timeWindow, {
      id: "paid_leads.kpis",
      kind: "kpi_grid",
      title: "Paid lead KPIs",
      description: "Approved aggregate paid-lead totals.",
      data: numberDatums(result, [
        ["total_paid_leads", "Total paid leads", "leads"],
      ]),
    }),
    bucketSpec(queryId, readModelId, timeWindow, result, {
      id: "paid_leads.sources",
      kind: "horizontal_bar_chart",
      title: "Paid leads by source",
      description: "Ranked paid source buckets from the approved result.",
      sourceKey: "sources",
    }),
  ]);
}

function leadSourceSpecs(
  queryId: string,
  readModelId: string,
  result: Record<string, unknown>,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
): ManagerAnalyticsVisualizationSpec[] {
  return compactSpecs([
    spec(queryId, readModelId, timeWindow, {
      id: "lead_source.kpis",
      kind: "kpi_grid",
      title: "Lead source KPIs",
      description: "Approved aggregate lead-source totals.",
      data: numberDatums(result, [["total_leads", "Total leads", "leads"]]),
    }),
    bucketSpec(queryId, readModelId, timeWindow, result, {
      id: "lead_source.sources",
      kind: "horizontal_bar_chart",
      title: "Leads by source",
      description: "Ranked source buckets from the approved result.",
      sourceKey: "sources",
    }),
  ]);
}

function consultationFollowupSpecs(
  queryId: string,
  readModelId: string,
  result: Record<string, unknown>,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
): ManagerAnalyticsVisualizationSpec[] {
  return compactSpecs([
    spec(queryId, readModelId, timeWindow, {
      id: "consultation_followup.kpis",
      kind: "kpi_grid",
      title: "Consultation follow-up KPIs",
      description: "Approved aggregate follow-up workload totals.",
      data: numberDatums(result, [
        ["open_followups", "Open follow-ups", "tasks"],
        ["overdue_followups", "Overdue follow-ups", "tasks"],
      ]),
    }),
    bucketSpec(queryId, readModelId, timeWindow, result, {
      id: "consultation_followup.consultation_status",
      kind: "bar_chart",
      title: "Consultation status",
      description: "Consultation status buckets from the approved result.",
      sourceKey: "consultation_status",
    }),
  ]);
}

function spec(
  queryId: string,
  readModelId: string,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
  input: Omit<
    ManagerAnalyticsVisualizationSpec,
    "query_id" | "read_model_id" | "time_window"
  >,
): ManagerAnalyticsVisualizationSpec | null {
  if (input.data.length === 0) {
    return null;
  }
  return ManagerAnalyticsVisualizationSpecSchema.parse({
    ...input,
    query_id: queryId,
    read_model_id: readModelId,
    time_window: timeWindow,
  });
}

function bucketSpec(
  queryId: string,
  readModelId: string,
  timeWindow: ManagerAnalyticsVisualizationSpec["time_window"],
  result: Record<string, unknown>,
  input: {
    id: string;
    kind: "bar_chart" | "horizontal_bar_chart";
    title: string;
    description: string;
    sourceKey: string;
  },
): ManagerAnalyticsVisualizationSpec | null {
  const data = bucketDatums(result[input.sourceKey], `result.${input.sourceKey}`);
  return spec(queryId, readModelId, timeWindow, {
    id: input.id,
    kind: input.kind,
    title: input.title,
    description: input.description,
    data,
  });
}

function compactSpecs(
  specs: Array<ManagerAnalyticsVisualizationSpec | null>,
): ManagerAnalyticsVisualizationSpec[] {
  return specs.filter(
    (item): item is ManagerAnalyticsVisualizationSpec => item !== null,
  );
}

function numberDatums(
  result: Record<string, unknown>,
  fields: Array<[key: string, label: string, unit: string]>,
) {
  return fields.flatMap(([key, label, unit]) => {
    const value = result[key];
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
      return [];
    }
    return [
      ManagerAnalyticsVisualizationDatumSchema.parse({
        key,
        label,
        value,
        unit,
        source_path: `result.${key}`,
      }),
    ];
  });
}

function bucketDatums(value: unknown, sourcePath: string) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item, index) => {
    if (!isRecord(item)) {
      return [];
    }
    const key = optionalString(item.key) ?? `bucket_${index + 1}`;
    const label = optionalString(item.label) ?? key;
    const count = item.count;
    if (typeof count !== "number" || !Number.isFinite(count) || count < 0) {
      return [];
    }
    return [
      ManagerAnalyticsVisualizationDatumSchema.parse({
        key,
        label,
        value: count,
        unit: null,
        source_path: `${sourcePath}[${index}].count`,
      }),
    ];
  });
}

function visualizationTimeWindow(
  envelope: Record<string, unknown>,
): ManagerAnalyticsVisualizationSpec["time_window"] {
  const value = envelope.time_window;
  if (!isRecord(value)) {
    return null;
  }
  return ManagerAnalyticsVisualizationTimeWindowSchema.parse({
    source: optionalString(value.source) ?? "unknown",
    preset: optionalString(value.preset) ?? "unknown",
    created_from: optionalString(value.created_from),
    created_to: optionalString(value.created_to),
    disclosure: optionalString(value.disclosure),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}
