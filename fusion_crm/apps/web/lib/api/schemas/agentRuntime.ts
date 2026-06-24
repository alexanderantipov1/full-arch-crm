import { z } from "zod";
import { Datetime } from "./common";

export const AgentRuntimeConnectionCheckSchema = z.object({
  ok: z.boolean(),
  runtime: z.literal("agent_runtime"),
  provider_kind: z.literal("openai"),
  credential_kind: z.literal("api_key"),
  model: z.string().min(1),
  last_agent: z.string().min(1),
  output: z.string().min(1),
});
export type AgentRuntimeConnectionCheck = z.infer<
  typeof AgentRuntimeConnectionCheckSchema
>;

export const AgentRuntimeToolStatusSchema = z.enum([
  "available",
  "planned",
  "deferred",
]);

export const AgentRuntimeToolExecutionPostureSchema = z.enum([
  "executable",
  "planning_only",
  "approval_required",
  "blocked",
]);

export const AgentRuntimeToolProjectionSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().min(1),
  owner_package: z.string().min(1),
  status: AgentRuntimeToolStatusSchema,
  callable: z.boolean(),
  execution_posture: AgentRuntimeToolExecutionPostureSchema.default(
    "planning_only",
  ),
  data_classes: z.array(z.string()),
  input_posture: z.string().min(1),
  output_posture: z.string().min(1),
  policy_posture: z.string().min(1),
  limits: z.array(z.string()).default([]),
  downstream_surfaces: z.array(z.string()).default([]),
  requires_approval: z.boolean().default(false),
  notes: z.array(z.string()).default([]),
});
export type AgentRuntimeToolProjection = z.infer<
  typeof AgentRuntimeToolProjectionSchema
>;

export const AgentRuntimeToolsProjectionSchema = z.object({
  runtime: z.literal("agent_runtime"),
  source: z.literal("packages.tools.registry"),
  tools: z.array(AgentRuntimeToolProjectionSchema),
});
export type AgentRuntimeToolsProjection = z.infer<
  typeof AgentRuntimeToolsProjectionSchema
>;

const UnsafeLlmPromptMarkers = [
  "sk-",
  "raw_provider_payload",
  "raw payload",
  "raw_sql",
  "raw sql",
  "select *",
  "patient_name",
  "date_of_birth",
  "full_prompt",
];

export const AgentRuntimeLlmPlanInputSchema = z.object({
  user_prompt: z
    .string()
    .min(1)
    .max(2000)
    .refine(
      (value) => {
        const lowered = value.toLowerCase();
        return !UnsafeLlmPromptMarkers.some((marker) =>
          lowered.includes(marker),
        );
      },
      { message: "Unsafe prompt detail is not allowed for LLM planning." },
    ),
});
export type AgentRuntimeLlmPlanInput = z.infer<
  typeof AgentRuntimeLlmPlanInputSchema
>;

export const AgentRuntimeLlmPlanOutcomeSchema = z.enum([
  "tool_plan",
  "clarification_required",
  "refused",
]);

export const AgentRuntimeLlmPlanConfidenceSchema = z.enum([
  "high",
  "medium",
  "low",
]);

export const AgentRuntimeLlmPlanPolicyResultSchema = z.enum([
  "allowed",
  "denied",
  "blocked",
  "approval_required",
]);

export const AgentRuntimeLlmExecutionStatusSchema = z.enum([
  "not_applicable",
  "not_executed",
  "executed",
  "clarification_required",
  "denied",
  "no_match",
  "failed",
]);

export const AgentRuntimeLlmExecutionSchema = z.object({
  status: AgentRuntimeLlmExecutionStatusSchema,
  tool_id: z.string().min(1).max(160),
  query_id: z.string().max(160).nullable().default(null),
  read_model_id: z.string().max(160).nullable().default(null),
  match_status: z
    .enum(["matched", "clarification_required", "no_match"])
    .default("no_match"),
  match_confidence: AgentRuntimeLlmPlanConfidenceSchema.nullable().default(null),
  match_reason: z.string().max(400).nullable().default(null),
  matched_keywords: z.array(z.string()).default([]),
  output_type: z.enum(["aggregate", "none"]).default("none"),
  data_classes: z.array(z.string()).default([]),
  row_count: z.number().int().nonnegative().nullable().default(null),
  explanation: z.string().max(500).nullable().default(null),
  policy_reason: z.string().min(1).max(400),
  result: z.record(z.unknown()).nullable().default(null),
});
export type AgentRuntimeLlmExecution = z.infer<
  typeof AgentRuntimeLlmExecutionSchema
>;

export const AgentRuntimeLlmPlanSchema = z.object({
  runtime: z.literal("agent_runtime"),
  provider_kind: z.literal("openai"),
  credential_kind: z.literal("api_key"),
  run_id: z.string().min(1),
  model: z.string().min(1).max(120),
  last_agent: z.string().min(1).max(160),
  outcome: AgentRuntimeLlmPlanOutcomeSchema,
  intent: z.string().min(1).max(160),
  tool_id: z.string().min(1).max(160).nullable().default(null),
  tool_arguments: z.record(z.unknown()).default({}),
  confidence: AgentRuntimeLlmPlanConfidenceSchema,
  clarification_question: z.string().max(400).nullable().default(null),
  refusal_reason: z.string().max(400).nullable().default(null),
  safety_notes: z.array(z.string()).default([]),
  policy_result: AgentRuntimeLlmPlanPolicyResultSchema,
  policy_reason: z.string().min(1).max(400),
  approval_required: z.boolean().default(false),
  execution_status: AgentRuntimeLlmExecutionStatusSchema.default("not_executed"),
  execution: AgentRuntimeLlmExecutionSchema.nullable().default(null),
  answer_eligibility: z
    .lazy(() => AgentRuntimeManagerAnswerEligibilitySchema)
    .nullable()
    .default(null),
  manager_answer: z
    .lazy(() => AgentRuntimeManagerAnswerSchema)
    .nullable()
    .default(null),
  result_posture: z.enum([
    "safe_llm_plan_metadata_only",
    "safe_aggregate_tool_execution",
  ]),
});
export type AgentRuntimeLlmPlan = z.infer<
  typeof AgentRuntimeLlmPlanSchema
>;

export const AgentRuntimeManagerAnswerStatusSchema = z.enum([
  "generated",
  "generated_with_caveat",
  "not_generated",
  "validation_failed",
  "blocked",
]);

export const AgentRuntimeDataQualityMetricSchema = z.object({
  id: z.string().min(1).max(160),
  label: z.string().min(1).max(160),
  value: z.union([z.number(), z.string()]),
  unit: z.string().max(80).nullable().default(null),
  numerator: z.number().nullable().default(null),
  denominator: z.number().nullable().default(null),
  status: z.enum(["ok", "caveat", "blocked", "unknown"]).default("unknown"),
  evidence_ref: z.string().max(160).nullable().default(null),
});
export type AgentRuntimeDataQualityMetric = z.infer<
  typeof AgentRuntimeDataQualityMetricSchema
>;

export const AgentRuntimeManagerAnswerKeyNumberSchema = z.object({
  label: z.string().min(1).max(120),
  value: z.union([z.number(), z.string()]),
  unit: z.string().max(80).nullable().default(null),
  comparison: z.string().max(240).nullable().default(null),
});
export type AgentRuntimeManagerAnswerKeyNumber = z.infer<
  typeof AgentRuntimeManagerAnswerKeyNumberSchema
>;

export const AgentRuntimeManagerAnswerSourceRefsSchema = z.object({
  tool_id: z.string().min(1).max(160),
  query_id: z.string().min(1).max(160),
  read_model_id: z.string().min(1).max(160),
  execution_run_id: z.string().min(1).max(160),
  approved_catalog_version_refs: z.array(z.string()).default([]),
  evidence_refs: z.array(z.string()).default([]),
});
export type AgentRuntimeManagerAnswerSourceRefs = z.infer<
  typeof AgentRuntimeManagerAnswerSourceRefsSchema
>;

export const AgentRuntimeManagerAnswerSchema = z
  .object({
    status: AgentRuntimeManagerAnswerStatusSchema,
    model: z.string().max(120).nullable().default(null),
    last_agent: z.string().max(160).nullable().default(null),
    summary: z.string().max(600).nullable().default(null),
    key_numbers: z.array(AgentRuntimeManagerAnswerKeyNumberSchema).default([]),
    explanation: z.string().max(1600).nullable().default(null),
    caveats: z.array(z.string()).default([]),
    source_refs: AgentRuntimeManagerAnswerSourceRefsSchema.nullable().default(
      null,
    ),
    confidence: AgentRuntimeLlmPlanConfidenceSchema.nullable().default(null),
    safety_notes: z.array(z.string()).default([]),
    validation_errors: z.array(z.string()).default([]),
  })
  .superRefine((value, ctx) => {
    if (
      value.status !== "generated" &&
      value.status !== "generated_with_caveat"
    ) {
      return;
    }
    if (!value.summary) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require a summary.",
        path: ["summary"],
      });
    }
    if (value.key_numbers.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require key numbers.",
        path: ["key_numbers"],
      });
    }
    if (!value.explanation) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require an explanation.",
        path: ["explanation"],
      });
    }
    if (!value.source_refs) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require source refs.",
        path: ["source_refs"],
      });
    }
    if (!value.confidence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require confidence.",
        path: ["confidence"],
      });
    }
    if (value.safety_notes.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Generated manager answers require safety notes.",
        path: ["safety_notes"],
      });
    }
  });
export type AgentRuntimeManagerAnswer = z.infer<
  typeof AgentRuntimeManagerAnswerSchema
>;

export const AgentRuntimeManagerAnswerEligibilitySchema = z
  .object({
    eligible: z.boolean(),
    reason: z.string().min(1).max(400),
    answer_posture: z.enum([
      "generated",
      "generated_with_caveat",
      "blocked",
    ]),
    execution_status: AgentRuntimeLlmExecutionStatusSchema,
    result_posture: z.enum([
      "safe_llm_plan_metadata_only",
      "safe_aggregate_tool_execution",
    ]),
    tool_id: z.string().max(160).nullable().default(null),
    query_id: z.string().max(160).nullable().default(null),
    read_model_id: z.string().max(160).nullable().default(null),
    data_classes: z.array(z.string()).default([]),
    source_refs: AgentRuntimeManagerAnswerSourceRefsSchema.nullable().default(
      null,
    ),
    data_quality_evidence_refs: z.array(z.string()).default([]),
    data_quality_metrics: z
      .array(AgentRuntimeDataQualityMetricSchema)
      .default([]),
    caveats: z.array(z.string()).default([]),
  })
  .superRefine((value, ctx) => {
    if (!value.eligible) {
      return;
    }
    if (value.answer_posture === "blocked") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Eligible answers require a generated answer posture.",
        path: ["answer_posture"],
      });
    }
    if (value.execution_status !== "executed") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Eligible answers require executed aggregate status.",
        path: ["execution_status"],
      });
    }
    if (value.result_posture !== "safe_aggregate_tool_execution") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          "Eligible answers require safe aggregate tool execution posture.",
        path: ["result_posture"],
      });
    }
    if (!value.source_refs) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Eligible answers require source refs.",
        path: ["source_refs"],
      });
    }
  });
export type AgentRuntimeManagerAnswerEligibility = z.infer<
  typeof AgentRuntimeManagerAnswerEligibilitySchema
>;

export const AgentRuntimeRunStatusSchema = z.enum([
  "success",
  "failure",
  "blocked",
  "approval_required",
  "denied",
]);

export const AgentRuntimeDataLevelSchema = z.enum([
  "none",
  "metadata_only",
  "aggregate_only",
  "row_level",
]);

export const AgentRuntimePolicyDecisionResultSchema = z.enum([
  "allowed",
  "denied",
  "blocked",
  "approval_required",
]);

export const AgentRuntimeFinalOutcomeSchema = z.enum([
  "completed",
  "failed",
  "blocked",
  "denied",
  "approval_required",
]);

export const AgentRuntimeCatalogConsumptionStatusSchema = z.enum([
  "approved_version_refs",
  "missing_catalog_version",
  "not_applicable",
]);

export const AgentRuntimeToolCallSummarySchema = z.object({
  tool_id: z.string().min(1),
  status: AgentRuntimeRunStatusSchema,
  data_classes: z.array(z.string()).default([]),
  output_posture: z.string().min(1),
  approval_request_id: z.string().nullable().default(null),
});

export const AgentRuntimePolicyDecisionSchema = z.object({
  gate_id: z.string().min(1),
  result: AgentRuntimePolicyDecisionResultSchema,
  reason: z.string().min(1),
  evidence_refs: z.array(z.string()).default([]),
});

export const AgentRuntimeAnswerAuditSummarySchema = z.object({
  status: AgentRuntimeManagerAnswerStatusSchema,
  eligible: z.boolean().default(false),
  reason: z.string().min(1).max(400),
  answer_posture: z
    .enum(["generated", "generated_with_caveat", "blocked"])
    .nullable()
    .default(null),
  model: z.string().max(120).nullable().default(null),
  confidence: AgentRuntimeLlmPlanConfidenceSchema.nullable().default(null),
  source_refs: AgentRuntimeManagerAnswerSourceRefsSchema.nullable().default(
    null,
  ),
  caveats: z.array(z.string()).default([]),
  data_quality_evidence_refs: z.array(z.string()).default([]),
  data_quality_metrics: z
    .array(AgentRuntimeDataQualityMetricSchema)
    .default([]),
  safety_notes: z.array(z.string()).default([]),
  validation_errors: z.array(z.string()).default([]),
});
export type AgentRuntimeAnswerAuditSummary = z.infer<
  typeof AgentRuntimeAnswerAuditSummarySchema
>;

export const AgentRuntimeAuditSummarySchema = z.object({
  data_classes: z.array(z.string()).default([]),
  data_level: AgentRuntimeDataLevelSchema.default("metadata_only"),
  row_level: z.boolean().default(false),
  phi: z.boolean().default(false),
  billing: z.boolean().default(false),
  export: z.boolean().default(false),
  masked: z.boolean().default(true),
  policy_result: z.string().min(1),
  policy_gate: z.string().min(1).default("runtime_preflight"),
  policy_reason: z.string().nullable().default(null),
  approval_required: z.boolean().default(false),
  final_outcome: AgentRuntimeFinalOutcomeSchema.default("completed"),
  policy_decisions: z.array(AgentRuntimePolicyDecisionSchema).default([]),
  evidence_refs: z.array(z.string()).default([]),
  compliance_notes: z.array(z.string()).default([]),
  linked_approval_request_ids: z.array(z.string()).default([]),
  query_registry_refs: z.array(z.string()).default([]),
  read_model_refs: z.array(z.string()).default([]),
  approved_catalog_version_refs: z.array(z.string()).default([]),
  catalog_consumption_status: AgentRuntimeCatalogConsumptionStatusSchema.default(
    "not_applicable",
  ),
  answer: AgentRuntimeAnswerAuditSummarySchema.nullable().default(null),
});

export const AgentRuntimeRunSummarySchema = z.object({
  id: z.string().min(1),
  agent_name: z.string().min(1),
  provider_kind: z.string().min(1),
  model: z.string().nullable().default(null),
  run_kind: z.string().min(1),
  status: AgentRuntimeRunStatusSchema,
  started_at: Datetime,
  completed_at: Datetime.nullable().default(null),
  duration_ms: z.number().int().nonnegative().nullable().default(null),
  triggered_by: z.string().nullable().default(null),
  tool_calls: z.array(AgentRuntimeToolCallSummarySchema).default([]),
  result_posture: z.string().min(1),
  audit_summary: AgentRuntimeAuditSummarySchema,
  error_code: z.string().nullable().default(null),
  error_message: z.string().nullable().default(null),
});
export type AgentRuntimeRunSummary = z.infer<
  typeof AgentRuntimeRunSummarySchema
>;

export const AgentRuntimeRunHistoryFiltersSchema = z.object({
  limit: z.number().int().min(1).max(100).default(25),
  status: AgentRuntimeRunStatusSchema.nullable().default(null),
  tool_id: z.string().nullable().default(null),
  policy_result: z.string().nullable().default(null),
  final_outcome: AgentRuntimeFinalOutcomeSchema.nullable().default(null),
  triggered_by: z.string().nullable().default(null),
  started_after: Datetime.nullable().default(null),
  started_before: Datetime.nullable().default(null),
});
export type AgentRuntimeRunHistoryFilters = z.infer<
  typeof AgentRuntimeRunHistoryFiltersSchema
>;

export const AgentRuntimeRunHistorySchema = z.object({
  runtime: z.literal("agent_runtime"),
  filters: AgentRuntimeRunHistoryFiltersSchema.default({}),
  runs: z.array(AgentRuntimeRunSummarySchema),
});
export type AgentRuntimeRunHistory = z.infer<
  typeof AgentRuntimeRunHistorySchema
>;

export const AgentRuntimeApprovalStatusSchema = z.enum([
  "pending",
  "approved",
  "rejected",
  "needs_edit",
  "unresolved",
]);

export const AgentRuntimeApprovalWorkflowStateSchema = z.enum([
  "pending_review",
  "approved_no_auto_execution",
  "rejected",
  "needs_edit",
  "unresolved",
  "expired",
  "executed_after_approval",
]);

export const AgentRuntimeApprovalTargetKindSchema = z.enum([
  "semantic_catalog_mapping_proposal",
  "semantic_catalog_impact_preview",
  "large_analysis_run",
  "export_request",
  "write_tool_execution",
]);

export const AgentRuntimeApprovalDecisionSchema = z.enum([
  "approve",
  "reject",
  "request_edit",
  "mark_unresolved",
]);
export type AgentRuntimeApprovalDecision = z.infer<
  typeof AgentRuntimeApprovalDecisionSchema
>;

export const AgentRuntimeApprovalRequestSchema = z.object({
  id: z.string().min(1),
  source_run_id: z.string().nullable().default(null),
  agent_name: z.string().min(1),
  tool_id: z.string().nullable().default(null),
  target_kind: AgentRuntimeApprovalTargetKindSchema,
  target_ref: z.string().nullable().default(null),
  title: z.string().min(1),
  reason: z.string().min(1),
  evidence_summary: z.string().min(1),
  requested_action: z.string().min(1),
  status: AgentRuntimeApprovalStatusSchema,
  requested_at: Datetime,
  requested_by: z.string().nullable().default(null),
  decided_at: Datetime.nullable().default(null),
  decided_by: z.string().nullable().default(null),
  workflow_state: AgentRuntimeApprovalWorkflowStateSchema.default(
    "pending_review",
  ),
  data_classes: z.array(z.string()).default([]),
  affected_surfaces: z.array(z.string()).default([]),
  risk_flags: z.array(z.string()).default([]),
  approval_posture: z.string().min(1),
  decision_summary: z.string().nullable().default(null),
  edit_summary: z.string().nullable().default(null),
});
export type AgentRuntimeApprovalRequest = z.infer<
  typeof AgentRuntimeApprovalRequestSchema
>;

export const AgentRuntimeApprovalRequestsSchema = z.object({
  runtime: z.literal("agent_runtime"),
  approvals: z.array(AgentRuntimeApprovalRequestSchema),
});
export type AgentRuntimeApprovalRequests = z.infer<
  typeof AgentRuntimeApprovalRequestsSchema
>;

export const AgentRuntimeLinkageImpactConfidenceSchema = z.enum([
  "known",
  "likely",
  "unknown",
]);

export const AgentRuntimeLinkageStepStatusSchema = z.enum([
  "ready",
  "in_review",
  "blocked",
  "planned",
  "deferred",
]);

export const AgentRuntimeLinkageImpactSurfaceSchema = z.object({
  surface: z.string().min(1),
  confidence: AgentRuntimeLinkageImpactConfidenceSchema,
  reason: z.string().min(1),
});

export const AgentRuntimeLinkageStepSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  status: AgentRuntimeLinkageStepStatusSchema,
  owner: z.string().min(1),
  contract: z.string().min(1),
});

export const AgentRuntimeDiaCatalogLinkageSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  source_agent: z.string().min(1),
  output_kind: z.enum(["mapping_proposal", "gap_brief"]),
  runtime_run_id: z.string().nullable().default(null),
  approval_request_id: z.string().nullable().default(null),
  catalog_proposal_ref: z.string().nullable().default(null),
  approved_catalog_version_ref: z.string().nullable().default(null),
  review_posture: z.string().min(1),
  downstream_consumption: z.literal("approved_version_only"),
  data_classes: z.array(z.string()).default([]),
  evidence_refs: z.array(z.string()).default([]),
  query_registry_refs: z.array(z.string()).default([]),
  read_model_refs: z.array(z.string()).default([]),
  approved_catalog_version_refs: z.array(z.string()).default([]),
  impact_surfaces: z.array(AgentRuntimeLinkageImpactSurfaceSchema),
  path: z.array(AgentRuntimeLinkageStepSchema),
  notes: z.array(z.string()).default([]),
});

export const AgentRuntimeDiaCatalogLinkagesSchema = z.object({
  runtime: z.literal("agent_runtime"),
  source: z.literal("agent_runtime_projection"),
  linkages: z.array(AgentRuntimeDiaCatalogLinkageSchema),
});
export type AgentRuntimeDiaCatalogLinkages = z.infer<
  typeof AgentRuntimeDiaCatalogLinkagesSchema
>;
