import { http, HttpResponse, delay } from "msw";
import {
  ApiKeyConnectRequestSchema,
  AgentRuntimeConnectionCheckSchema,
  AgentRuntimeApprovalDecisionSchema,
  AgentRuntimeApprovalRequestSchema,
  AgentRuntimeApprovalRequestsSchema,
  AgentRuntimeRunHistorySchema,
  AgentRuntimeDiaCatalogLinkagesSchema,
  AgentRuntimeLlmPlanInputSchema,
  AgentRuntimeLlmPlanSchema,
  AgentRuntimeToolsProjectionSchema,
  IntegrationListSchema,
  LoginRequestSchema,
  OpsConsultationSchema,
  PersonLocationProfileSchema,
  type LoginResponse,
  type PersonList,
} from "@/lib/api/schemas";
import { personDetails, personSummaries } from "./fixtures/persons";
import { integrationStore } from "./fixtures/integrations";
import { tenantFixture } from "./fixtures/tenant";
import { outreachHandlers } from "./outreachHandlers";

const apiError = (
  status: number,
  code: string,
  message: string,
  details: Record<string, unknown> = {},
) =>
  HttpResponse.json(
    { error: { code, message, details } },
    { status },
  );

/**
 * When NEXT_PUBLIC_USE_REAL_SF=true, real Next.js route handlers serve
 * /api/integrations/* and /api/persons. Those mock handlers are excluded
 * so MSW's onUnhandledRequest:"bypass" lets the request fall through to
 * Next.js. Auth, health, tenant settings, and outreach remain mock-only
 * until their matching backend or local route surfaces land.
 */
const USE_REAL_SF = process.env.NEXT_PUBLIC_USE_REAL_SF === "true";

const authHandlers = [
  http.post("/api/auth/login", async ({ request }) => {
    const json = (await request.json()) as unknown;
    const parsed = LoginRequestSchema.safeParse(json);
    if (!parsed.success) {
      return apiError(400, "VALIDATION", "Invalid login payload");
    }
    if (parsed.data.password !== "demo") {
      await delay(400);
      return apiError(401, "AUTH_INVALID", "Invalid email or password");
    }
    await delay(250);
    const body: LoginResponse = {
      session: {
        staff_id: "55555555-5555-5555-5555-555555555555",
        email: parsed.data.email,
        display_name: parsed.data.email.split("@")[0] ?? "staff",
        expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      },
    };
    return HttpResponse.json(body, {
      headers: {
        "Set-Cookie":
          "staff_session=mock-session; Path=/; SameSite=Lax; Max-Age=28800",
      },
    });
  }),

  http.post("/api/auth/logout", () =>
    HttpResponse.json(
      { ok: true },
      { headers: { "Set-Cookie": "staff_session=; Path=/; Max-Age=0" } },
    ),
  ),

  http.get("/api/auth/session", ({ request }) => {
    const cookies = request.headers.get("cookie") ?? "";
    if (!cookies.includes("staff_session=")) {
      return apiError(401, "UNAUTHENTICATED", "No active session");
    }
    return HttpResponse.json({
      session: {
        staff_id: "55555555-5555-5555-5555-555555555555",
        email: "demo@fusion-dental.local",
        display_name: "demo",
        expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      },
    });
  }),
];

const integrationsAndPersonsHandlers = [
  http.get("/api/integrations", () =>
    HttpResponse.json(
      IntegrationListSchema.parse({ items: Object.values(integrationStore) }),
    ),
  ),

  http.post("/api/integrations/:provider/connect/start", ({ params }) => {
    const provider = String(params.provider);
    if (provider === "salesforce") {
      const origin =
        typeof window !== "undefined"
          ? window.location.origin
          : "http://localhost:3000";
      return HttpResponse.json({
        kind: "oauth_redirect",
        redirect_url: `${origin}/integrations/salesforce/callback?mock=1&code=mock_oauth_code`,
      });
    }
    if (provider === "carestack") {
      return HttpResponse.json({
        kind: "api_key_form",
        label: "CareStack API key",
        placeholder: "cs_live_...",
      });
    }
    return apiError(400, "UNKNOWN_PROVIDER", `Unknown provider: ${provider}`);
  }),

  http.get("/api/integrations/:provider/callback", async ({ params }) => {
    const provider = String(params.provider);
    const account = integrationStore[provider];
    if (!account) {
      return apiError(404, "UNKNOWN_PROVIDER", `Unknown provider: ${provider}`);
    }
    account.status = "connected";
    account.display_name = `${provider} prod`;
    account.last_sync_at = null;
    account.error_message = null;
    await delay(500);
    return HttpResponse.json(account);
  }),

  http.post(
    "/api/integrations/:provider/api-key",
    async ({ params, request }) => {
      const provider = String(params.provider);
      const account = integrationStore[provider];
      if (!account) {
        return apiError(
          404,
          "UNKNOWN_PROVIDER",
          `Unknown provider: ${provider}`,
        );
      }
      const json = (await request.json()) as unknown;
      const parsed = ApiKeyConnectRequestSchema.safeParse(json);
      if (!parsed.success) {
        return apiError(400, "VALIDATION", "API key required");
      }
      account.status = "connected";
      account.display_name = parsed.data.display_name ?? `${provider} prod`;
      account.last_sync_at = null;
      account.error_message = null;
      await delay(400);
      return HttpResponse.json(account);
    },
  ),

  http.post("/api/integrations/:provider/sync", async ({ params }) => {
    const provider = String(params.provider);
    const account = integrationStore[provider];
    if (!account) {
      return apiError(404, "UNKNOWN_PROVIDER", `Unknown provider: ${provider}`);
    }
    if (account.status !== "connected" && account.status !== "syncing") {
      return apiError(409, "NOT_CONNECTED", "Connect the integration first");
    }
    const now = new Date().toISOString();
    account.status = "connected";
    account.last_sync_at = now;
    account.last_sync_summary = {
      id: "ff000099-0000-0000-0000-000000000099",
      status: "success",
      records_pulled: 2,
      finished_at: now,
    };
    await delay(400);
    return HttpResponse.json({
      sync_run_id: "ff000099-0000-0000-0000-000000000099",
    });
  }),

  http.delete("/api/integrations/:provider", async ({ params }) => {
    const provider = String(params.provider);
    const account = integrationStore[provider];
    if (!account) {
      return apiError(404, "UNKNOWN_PROVIDER", `Unknown provider: ${provider}`);
    }
    account.status = "disconnected";
    account.display_name = null;
    account.last_sync_at = null;
    account.last_sync_summary = null;
    account.error_message = null;
    await delay(200);
    return HttpResponse.json(account);
  }),

  http.get("/api/persons", () => {
    const body: PersonList = {
      items: personSummaries,
      total: personSummaries.length,
    };
    return HttpResponse.json(body);
  }),

  http.get("/api/persons/:uid", ({ params }) => {
    const detail = personDetails[String(params.uid)];
    if (!detail) {
      return apiError(404, "NOT_FOUND", "Person not found");
    }
    return HttpResponse.json(detail);
  }),

  http.get("/api/ops/persons/:uid/consultations", ({ params }) => {
    const uid = String(params.uid);
    if (!personDetails[uid]) {
      return apiError(404, "NOT_FOUND", "Person not found");
    }
    const consultations =
      uid === "11111111-1111-1111-1111-111111111111"
        ? [
            {
              id: "ccaa1111-0000-0000-0000-000000000001",
              person_uid: uid,
              source_provider: "carestack",
              source_instance: "carestack-main",
              external_id: "CS-44218",
              scheduled_at: "2026-05-04T18:00:00.000Z",
              duration_minutes: 60,
              status: "completed",
              consultation_kind: "initial",
              location_id: "22222222-0000-0000-0000-000000000001",
              provider_clinician_name: "Dr. Smith",
              raw_event_id: "ddaa1111-0000-0000-0000-000000000001",
              created_at: "2026-04-29T11:30:00.000Z",
              updated_at: "2026-05-04T18:32:00.000Z",
            },
          ]
        : uid === "33333333-3333-3333-3333-333333333333"
          ? [
              {
                id: "ccbb2222-0000-0000-0000-000000000001",
                person_uid: uid,
                source_provider: "carestack",
                source_instance: "carestack-main",
                external_id: "CS-44219",
                scheduled_at: "2026-05-12T17:00:00.000Z",
                duration_minutes: 45,
                status: "scheduled",
                consultation_kind: "initial",
                location_id: "22222222-0000-0000-0000-000000000004",
                provider_clinician_name: null,
                raw_event_id: "ddbb2222-0000-0000-0000-000000000001",
                created_at: "2026-05-05T15:50:00.000Z",
                updated_at: "2026-05-05T15:50:00.000Z",
              },
            ]
          : [];
    return HttpResponse.json(OpsConsultationSchema.array().parse(consultations));
  }),

  http.get("/api/ops/persons/:uid/location-profiles", ({ params }) => {
    const uid = String(params.uid);
    if (!personDetails[uid]) {
      return apiError(404, "NOT_FOUND", "Person not found");
    }
    const profiles =
      uid === "11111111-1111-1111-1111-111111111111"
        ? [
            {
              id: "44aa1111-0000-0000-0000-000000000001",
              person_uid: uid,
              location_id: "22222222-0000-0000-0000-000000000001",
              relationship_kind: "patient",
              relationship_status: "consult_completed",
              last_evidence_provider: "carestack",
              last_evidence_source_instance: "carestack-main",
              last_evidence_external_id: "CS-44218",
              last_evidence_at: "2026-05-04T18:00:00.000Z",
              last_consultation_id: "ccaa1111-0000-0000-0000-000000000001",
              last_raw_event_id: "ddaa1111-0000-0000-0000-000000000001",
              created_at: "2026-04-29T11:30:00.000Z",
              updated_at: "2026-05-04T18:32:00.000Z",
            },
          ]
        : uid === "33333333-3333-3333-3333-333333333333"
          ? [
              {
                id: "44bb2222-0000-0000-0000-000000000001",
                person_uid: uid,
                location_id: "22222222-0000-0000-0000-000000000004",
                relationship_kind: "prospect",
                relationship_status: "consult_scheduled",
                last_evidence_provider: "carestack",
                last_evidence_source_instance: "carestack-main",
                last_evidence_external_id: "CS-44219",
                last_evidence_at: "2026-05-12T17:00:00.000Z",
                last_consultation_id: "ccbb2222-0000-0000-0000-000000000001",
                last_raw_event_id: "ddbb2222-0000-0000-0000-000000000001",
                created_at: "2026-05-05T15:50:00.000Z",
                updated_at: "2026-05-05T15:50:00.000Z",
              },
            ]
          : [];
    return HttpResponse.json(
      PersonLocationProfileSchema.array().parse(profiles),
    );
  }),
];

const healthHandlers = [
  http.get("/api/health/ingest", () =>
    HttpResponse.json({
      status: "ok",
      providers: {
        salesforce: {
          status: "ok",
          last_status: "succeeded",
          last_run_at: new Date().toISOString(),
          records_succeeded: 12,
          records_failed: 0,
        },
        carestack: {
          status: "ok",
          last_status: "succeeded",
          last_run_at: new Date().toISOString(),
          records_succeeded: 8,
          records_failed: 0,
        },
      },
    }),
  ),
  http.get("/api/health/services", () =>
    HttpResponse.json({
      status: "ok",
      services: {
        postgres: { status: "ok" },
        redis: { status: "ok" },
        api: { status: "ok" },
        worker: { status: "ok", last_run_ago: "0:05:12" },
      },
    }),
  ),
];

const tenantHandlers = [
  // ENG-126: read-only tenant settings page. Replace this handler with a
  // deletion when ENG-124 ships `GET /api/tenant/current` from FastAPI.
  http.get("/api/tenant/current", () => HttpResponse.json(tenantFixture)),
];

const agentRuntimeApprovalFixtures = [
  AgentRuntimeApprovalRequestSchema.parse({
    id: "approval-semantic-catalog-1",
    source_run_id: "11111111-1111-4111-8111-111111111111",
    agent_name: "Data Intelligence Mapping Helper",
    tool_id: "data_intelligence_semantic_mapping_proposal",
    target_kind: "semantic_catalog_mapping_proposal",
    target_ref: "lead-source-google-ads",
    title: "Review lead source mapping candidate",
    reason:
      "The agent found repeated unmapped lead source values that likely belong to a governed marketing source term.",
    evidence_summary:
      "Aggregate coverage shows a repeated source/campaign pattern; examples remain masked and bounded.",
    requested_action:
      "Allow this proposal to enter Semantic Catalog review as a draft candidate.",
    status: "pending",
    requested_at: "2026-06-05T16:10:00Z",
    requested_by: "demo@fusion-dental.local",
    decided_at: null,
    decided_by: null,
    data_classes: ["ops", "integration_metadata"],
    affected_surfaces: ["semantic_catalog", "data_intelligence"],
    risk_flags: ["business_meaning_change"],
    approval_posture: "human_review_required_no_auto_mutation",
    decision_summary: null,
    edit_summary: null,
  }),
  AgentRuntimeApprovalRequestSchema.parse({
    id: "approval-export-1",
    source_run_id: null,
    agent_name: "Manager Analytics Planner",
    tool_id: "export_analytics_csv",
    target_kind: "export_request",
    target_ref: "weekly-conversion-aggregate",
    title: "Approve aggregate CSV export definition",
    reason:
      "The saved report definition would prepare aggregate CSV output for manager review.",
    evidence_summary:
      "Only aggregate metrics are included; row-level exports and XLSX remain deferred.",
    requested_action:
      "Approve the aggregate export definition posture for report review.",
    status: "needs_edit",
    requested_at: "2026-06-05T15:20:00Z",
    requested_by: "demo@fusion-dental.local",
    decided_at: "2026-06-05T15:25:00Z",
    decided_by: "demo@fusion-dental.local",
    data_classes: ["ops", "billing"],
    affected_surfaces: ["reports"],
    risk_flags: ["export_boundary"],
    approval_posture: "human_review_required_no_auto_mutation",
    decision_summary: "Needs explicit owner and retention policy.",
    edit_summary:
      "Add owner, retention window, and confirm CSV-only aggregate output.",
  }),
];

const agentRuntimeHandlers = [
  http.get("/api/agent-runtime/dia-catalog-linkages", () =>
    HttpResponse.json(
      AgentRuntimeDiaCatalogLinkagesSchema.parse({
        runtime: "agent_runtime",
        source: "agent_runtime_projection",
        linkages: [
          {
            id: "dia-lead-source-mapping-to-catalog-review",
            title: "DIA lead source mapping candidate to Semantic Catalog review",
            source_agent: "Data Intelligence Mapping Helper",
            output_kind: "mapping_proposal",
            runtime_run_id: "run-semantic-proposal-planned",
            approval_request_id: "approval-semantic-catalog-1",
            catalog_proposal_ref: "lead-source-google-ads",
            approved_catalog_version_ref: null,
            review_posture: "review_only_no_auto_approval",
            downstream_consumption: "approved_version_only",
            data_classes: ["ops", "integration_metadata"],
            evidence_refs: [
              "mapping_coverage_summary",
              "bounded_masked_examples",
            ],
            impact_surfaces: [
              {
                surface: "semantic_catalog",
                confidence: "known",
                reason:
                  "Human review proposal is the only path into catalog meaning.",
              },
              {
                surface: "manager_dashboard",
                confidence: "likely",
                reason:
                  "Approved source mapping can change grouped marketing metrics.",
              },
              {
                surface: "manager_chat",
                confidence: "likely",
                reason:
                  "Chat answers must use approved catalog definitions only.",
              },
              {
                surface: "reports",
                confidence: "unknown",
                reason:
                  "Saved report dependencies need registry impact metadata.",
              },
            ],
            path: [
              {
                id: "agent_run",
                title: "Agent run",
                status: "ready",
                owner: "packages.agent_runtime",
                contract: "Safe run summary with metadata-only posture.",
              },
              {
                id: "review_only_output",
                title: "Review-only DIA output",
                status: "ready",
                owner: "packages.tools.data_intelligence_tools",
                contract: "Mapping proposal evidence stays aggregate or masked.",
              },
              {
                id: "human_approval",
                title: "Human approval request",
                status: "in_review",
                owner: "packages.agent_runtime",
                contract: "Human decision gates downstream review handoff.",
              },
              {
                id: "catalog_review",
                title: "Semantic Catalog review",
                status: "planned",
                owner: "packages.insight",
                contract:
                  "Proposal becomes catalog truth only after catalog approval.",
              },
              {
                id: "approved_version",
                title: "Approved catalog version",
                status: "planned",
                owner: "packages.insight",
                contract: "Downstream consumers read approved versions only.",
              },
            ],
            notes: [
              "Agent suggestions are never approved catalog truth by themselves.",
              "ENG-350 should verify this path in production-facing workbench docs.",
            ],
          },
          {
            id: "dia-gap-brief-to-catalog-planning",
            title: "DIA gap brief to Semantic Catalog planning",
            source_agent: "Data Intelligence Gap Brief Helper",
            output_kind: "gap_brief",
            runtime_run_id: null,
            approval_request_id: null,
            catalog_proposal_ref: null,
            approved_catalog_version_ref: null,
            review_posture: "planning_only_no_catalog_mutation",
            downstream_consumption: "approved_version_only",
            data_classes: ["ops", "identity", "integration_metadata"],
            evidence_refs: ["coverage_gap_summary"],
            impact_surfaces: [
              {
                surface: "semantic_catalog",
                confidence: "likely",
                reason: "Gap briefs can create future human-review proposals.",
              },
              {
                surface: "data_intelligence",
                confidence: "known",
                reason: "Gap brief remains local planning evidence.",
              },
              {
                surface: "linear",
                confidence: "likely",
                reason: "Gap briefs can become follow-up implementation tasks.",
              },
            ],
            path: [
              {
                id: "agent_run",
                title: "Agent run",
                status: "planned",
                owner: "packages.agent_runtime",
                contract: "Future DIA runner records safe run summary.",
              },
              {
                id: "gap_brief",
                title: "Gap brief",
                status: "ready",
                owner: "packages.tools.data_intelligence_tools",
                contract: "Planning summary only; no catalog mutation.",
              },
              {
                id: "proposal_candidate",
                title: "Proposal candidate",
                status: "planned",
                owner: "packages.insight",
                contract:
                  "Human must decide whether a catalog proposal is needed.",
              },
              {
                id: "approved_version",
                title: "Approved catalog version",
                status: "blocked",
                owner: "packages.insight",
                contract: "Blocked until a reviewed proposal is approved.",
              },
            ],
            notes: [
              "Gap briefs explain missing meaning; they are not business meaning.",
            ],
          },
        ],
      }),
    ),
  ),

  http.get("/api/agent-runtime/approvals", () =>
    HttpResponse.json(
      AgentRuntimeApprovalRequestsSchema.parse({
        runtime: "agent_runtime",
        approvals: agentRuntimeApprovalFixtures,
      }),
    ),
  ),

  http.post("/api/agent-runtime/approvals/:approvalId/decision", async ({
    params,
    request,
  }) => {
    const approvalId = String(params.approvalId);
    const body = (await request.json()) as {
      decision?: unknown;
      decision_summary?: unknown;
      edit_summary?: unknown;
    };
    const decision = AgentRuntimeApprovalDecisionSchema.parse(body.decision);
    const index = agentRuntimeApprovalFixtures.findIndex(
      (approval) => approval.id === approvalId,
    );
    if (index === -1) {
      return apiError(
        404,
        "not_found",
        "Agent runtime approval request was not found.",
      );
    }
    const approval = agentRuntimeApprovalFixtures[index];
    if (approval?.status !== "pending") {
      return apiError(
        422,
        "validation_error",
        "Only pending approval requests can be decided.",
      );
    }
    const statusByDecision = {
      approve: "approved",
      reject: "rejected",
      request_edit: "needs_edit",
      mark_unresolved: "unresolved",
    } as const;
    const updated = AgentRuntimeApprovalRequestSchema.parse({
      ...approval,
      status: statusByDecision[decision],
      decided_at: new Date().toISOString(),
      decided_by: "demo@fusion-dental.local",
      decision_summary: String(body.decision_summary ?? ""),
      edit_summary:
        body.edit_summary === null || body.edit_summary === undefined
          ? null
          : String(body.edit_summary),
    });
    agentRuntimeApprovalFixtures[index] = updated;
    await delay(250);
    return HttpResponse.json(updated);
  }),

  http.get("/api/agent-runtime/runs", ({ request }) => {
    const params = new URL(request.url).searchParams;
    const filters = {
      limit: Number(params.get("limit") ?? 25),
      status: params.get("status"),
      tool_id: params.get("tool_id"),
      policy_result: params.get("policy_result"),
      final_outcome: params.get("final_outcome"),
      triggered_by: params.get("triggered_by"),
      started_after: params.get("started_after"),
      started_before: params.get("started_before"),
    };
    const runs = [
          {
            id: "run-llm-answer-generated",
            agent_name: "Fusion Agent Runtime Planner",
            provider_kind: "openai",
            model: "gpt-4.1-mini",
            run_kind: "llm_planning_with_tool_execution",
            status: "success",
            started_at: "2026-06-05T16:20:00Z",
            completed_at: "2026-06-05T16:20:02Z",
            duration_ms: 2100,
            triggered_by: "demo@fusion-dental.local",
            tool_calls: [
              {
                tool_id: "ask_manager_analytics",
                status: "success",
                data_classes: ["ops", "integration_metadata"],
                output_posture: "aggregate analytics result",
              },
            ],
            result_posture: "safe_aggregate_tool_execution",
            audit_summary: {
              data_classes: ["ops", "integration_metadata"],
              data_level: "aggregate_only",
              row_level: false,
              phi: false,
              billing: false,
              export: false,
              masked: true,
              policy_result: "allowed",
              policy_gate: "llm_plan_and_tool_execution",
              policy_reason:
                "Approved aggregate analytics tool executed through service-owned read-model code.",
              approval_required: false,
              final_outcome: "completed",
              policy_decisions: [
                {
                  gate_id: "approved_query_read_model_match",
                  result: "allowed",
                  reason:
                    "Question matched approved manager analytics query keywords: conversion, booked.",
                  evidence_refs: [
                    "lead_conversion_funnel.v1",
                    "lead_conversion",
                  ],
                },
                {
                  gate_id: "approved_tool_execution",
                  result: "allowed",
                  reason:
                    "Approved aggregate analytics tool executed through service-owned read-model code.",
                  evidence_refs: [
                    "approved_tool_registry",
                    "service_owned_read_model_execution",
                  ],
                },
              ],
              evidence_refs: [
                "openai_agent_plan_contract",
                "manager_answer_contract",
                "manager_answer_llm_generation",
              ],
              compliance_notes: [
                "Run history stores manager answer metadata only; answer body and provider payload are not persisted.",
              ],
              linked_approval_request_ids: [],
              query_registry_refs: ["lead_conversion_funnel.v1"],
              read_model_refs: ["lead_conversion"],
              approved_catalog_version_refs: [
                "consultation_completed:v1",
                "consultation_scheduled:v1",
                "lead_source:v1",
              ],
              catalog_consumption_status: "approved_version_refs",
              answer: {
                status: "generated",
                eligible: true,
                reason:
                  "Approved aggregate execution can be summarized for managers.",
                model: "gpt-4.1",
                confidence: "high",
                source_refs: {
                  tool_id: "ask_manager_analytics",
                  query_id: "lead_conversion_funnel.v1",
                  read_model_id: "lead_conversion",
                  execution_run_id: "run-llm-answer-generated",
                  approved_catalog_version_refs: [
                    "consultation_completed:v1",
                    "consultation_scheduled:v1",
                    "lead_source:v1",
                  ],
                  evidence_refs: [
                    "approved_tool_registry",
                    "service_owned_read_model_execution",
                  ],
                },
                caveats: ["No row-level rows are included."],
                safety_notes: ["Aggregate-only answer."],
                validation_errors: [],
              },
            },
            error_code: null,
            error_message: null,
          },
          {
            id: "run-openai-health-check",
            agent_name: "Fusion OpenAI Health Check",
            provider_kind: "openai",
            model: "gpt-4.1-mini",
            run_kind: "provider_health_check",
            status: "success",
            started_at: "2026-06-05T16:00:00Z",
            completed_at: "2026-06-05T16:00:00Z",
            duration_ms: 42,
            triggered_by: "demo@fusion-dental.local",
            tool_calls: [],
            result_posture: "safe_metadata_only",
            audit_summary: {
              data_classes: ["integration_metadata"],
              data_level: "metadata_only",
              row_level: false,
              phi: false,
              billing: false,
              export: false,
              masked: true,
              policy_result: "allowed",
              policy_gate: "provider_credential_health_check",
              policy_reason:
                "Tenant OpenAI credential check uses metadata only.",
              approval_required: false,
              final_outcome: "completed",
              policy_decisions: [
                {
                  gate_id: "tenant_credential_scope",
                  result: "allowed",
                  reason: "Credential resolved server-side for current tenant.",
                  evidence_refs: ["tenant_credential_status"],
                },
                {
                  gate_id: "sensitive_output_filter",
                  result: "allowed",
                  reason: "Response includes safe provider metadata only.",
                  evidence_refs: ["safe_metadata_contract"],
                },
              ],
              evidence_refs: ["provider_health_check"],
              compliance_notes: [
                "No secret or sensitive runtime payload stored.",
              ],
              linked_approval_request_ids: [],
            },
            error_code: null,
            error_message: null,
          },
          {
            id: "run-semantic-proposal-planned",
            agent_name: "Data Intelligence Mapping Helper",
            provider_kind: "openai",
            model: null,
            run_kind: "semantic_mapping_proposal",
            status: "approval_required",
            started_at: "2026-06-05T15:40:00Z",
            completed_at: "2026-06-05T15:40:03Z",
            duration_ms: 3000,
            triggered_by: "demo@fusion-dental.local",
            tool_calls: [
              {
                tool_id: "data_intelligence_semantic_mapping_proposal",
                status: "approval_required",
                data_classes: ["ops"],
                output_posture: "review-only semantic proposal",
              },
            ],
            result_posture: "review_required",
            audit_summary: {
              data_classes: ["ops"],
              data_level: "aggregate_only",
              row_level: false,
              phi: false,
              billing: false,
              export: false,
              masked: true,
              policy_result: "approval_required",
              policy_gate: "semantic_catalog_business_meaning",
              policy_reason:
                "Agent proposal can enter human review, but cannot mutate catalog meaning automatically.",
              approval_required: true,
              final_outcome: "approval_required",
              policy_decisions: [
                {
                  gate_id: "data_level",
                  result: "allowed",
                  reason: "Proposal evidence is aggregate-only and masked.",
                  evidence_refs: ["bounded_mapping_coverage"],
                },
                {
                  gate_id: "catalog_mutation",
                  result: "approval_required",
                  reason: "Business meaning changes require human review.",
                  evidence_refs: ["semantic_catalog_review_policy"],
                },
              ],
              evidence_refs: ["mapping_coverage_summary"],
              compliance_notes: [
                "Agent suggestion is review-only; Semantic Catalog approval remains the source of truth.",
              ],
              linked_approval_request_ids: ["approval-semantic-catalog-1"],
            },
            error_code: null,
            error_message: null,
          },
          {
            id: "run-row-level-export-denied",
            agent_name: "Manager Analytics Export Planner",
            provider_kind: "openai",
            model: "gpt-4.1-mini",
            run_kind: "export_request_preflight",
            status: "denied",
            started_at: "2026-06-05T15:25:00Z",
            completed_at: "2026-06-05T15:25:01Z",
            duration_ms: 780,
            triggered_by: "demo@fusion-dental.local",
            tool_calls: [
              {
                tool_id: "export_analytics_csv",
                status: "denied",
                data_classes: ["ops", "billing"],
                output_posture: "no export generated",
              },
            ],
            result_posture: "denied_no_export",
            audit_summary: {
              data_classes: ["ops", "billing"],
              data_level: "row_level",
              row_level: true,
              phi: false,
              billing: true,
              export: true,
              masked: true,
              policy_result: "denied",
              policy_gate: "row_level_export_policy",
              policy_reason:
                "Row-level exports are deferred until field allowlists and export audit are stable.",
              approval_required: false,
              final_outcome: "denied",
              policy_decisions: [
                {
                  gate_id: "export_boundary",
                  result: "denied",
                  reason: "V1 only allows aggregate CSV posture.",
                  evidence_refs: ["exports_saved_reports_v1_policy"],
                },
                {
                  gate_id: "row_level_field_allowlist",
                  result: "blocked",
                  reason: "Field allowlist is not approved for row-level output.",
                  evidence_refs: ["deferred_row_level_exports"],
                },
              ],
              evidence_refs: ["export_preflight"],
              compliance_notes: [
                "No file was generated and no row-level values were returned.",
              ],
              linked_approval_request_ids: [],
            },
            error_code: "row_level_export_denied",
            error_message: "Denied by row-level export policy.",
          },
        ].filter((run) => {
          if (filters.status && run.status !== filters.status) return false;
          if (
            filters.policy_result &&
            run.audit_summary.policy_result !== filters.policy_result
          ) {
            return false;
          }
          if (
            filters.final_outcome &&
            run.audit_summary.final_outcome !== filters.final_outcome
          ) {
            return false;
          }
          if (filters.triggered_by && run.triggered_by !== filters.triggered_by) {
            return false;
          }
          if (
            filters.tool_id &&
            !run.tool_calls.some((call) => call.tool_id === filters.tool_id)
          ) {
            return false;
          }
          return true;
        })
        .slice(0, filters.limit);
    return HttpResponse.json(
      AgentRuntimeRunHistorySchema.parse({
        runtime: "agent_runtime",
        filters,
        runs,
      }),
    );
  }),

  http.get("/api/agent-runtime/tools", () =>
    HttpResponse.json(
      AgentRuntimeToolsProjectionSchema.parse({
        runtime: "agent_runtime",
        source: "packages.tools.registry",
        tools: [
          {
            id: "data_intelligence_discover",
            title: "Data Intelligence Discover",
            description:
              "List approved Data Intelligence datasets, fields, data classes, limits, masks, and policy defaults.",
            owner_package: "packages.tools.data_intelligence_tools",
            status: "available",
            callable: true,
            execution_posture: "planning_only",
            data_classes: ["identity", "interaction", "ops"],
            input_posture: "discovery request only",
            output_posture: "policy and dataset metadata",
            policy_posture: "no database read",
            limits: [],
            downstream_surfaces: ["data_intelligence", "semantic_catalog"],
            requires_approval: false,
            notes: [],
          },
          {
            id: "data_intelligence_profile_field",
            title: "Data Intelligence Profile Field",
            description:
              "Profile one allowlisted Data Intelligence field through service-owned aggregates.",
            owner_package: "packages.tools.data_intelligence_tools",
            status: "available",
            callable: true,
            execution_posture: "planning_only",
            data_classes: ["identity", "interaction", "ops"],
            input_posture: "allowlisted dataset and field",
            output_posture: "aggregate field profile",
            policy_posture: "service-owned aggregates only",
            limits: ["allowlisted fields", "aggregate output"],
            downstream_surfaces: ["data_intelligence", "semantic_catalog"],
            requires_approval: false,
            notes: [],
          },
          {
            id: "data_intelligence_semantic_mapping_proposal",
            title: "Data Intelligence Semantic Mapping Proposal",
            description:
              "Generate review-only semantic mapping candidates for lead source and campaign values.",
            owner_package: "packages.tools.data_intelligence_tools",
            status: "available",
            callable: true,
            execution_posture: "approval_required",
            data_classes: ["ops"],
            input_posture: "approved source/campaign mapping evidence",
            output_posture: "review-only semantic proposal",
            policy_posture: "no catalog mutation",
            limits: [],
            downstream_surfaces: ["data_intelligence", "semantic_catalog"],
            requires_approval: true,
            notes: [],
          },
          {
            id: "semantic_catalog_create_review_proposal",
            title: "Semantic Catalog Create Review Proposal",
            description:
              "Create a human-reviewable semantic catalog proposal from an agent or Data Intelligence observation.",
            owner_package: "packages.insight",
            status: "planned",
            callable: false,
            execution_posture: "approval_required",
            data_classes: [
              "billing",
              "identity",
              "integration_metadata",
              "ops",
            ],
            input_posture: "review-only proposal payload",
            output_posture: "catalog proposal metadata",
            policy_posture: "human review required; no automatic approval",
            limits: [],
            downstream_surfaces: ["semantic_catalog", "agent_runtime"],
            requires_approval: true,
            notes: ["Tracked by ENG-349."],
          },
        ],
      }),
    ),
  ),

  http.post("/api/agent-runtime/llm/plans", async ({ request }) => {
    await delay(450);
    const parsed = AgentRuntimeLlmPlanInputSchema.safeParse(
      await request.json(),
    );
    if (!parsed.success) {
      return apiError(
        422,
        "VALIDATION_ERROR",
        "LLM planning prompt did not pass safe input validation.",
      );
    }

    const prompt = parsed.data.user_prompt.toLowerCase();
    if (prompt.includes("missing credential")) {
      return apiError(
        424,
        "OPENAI_CREDENTIAL_NOT_CONNECTED",
        "OpenAI credential is not connected for this tenant.",
      );
    }

    const base = {
      runtime: "agent_runtime" as const,
      provider_kind: "openai" as const,
      credential_kind: "api_key" as const,
      run_id: `run-llm-plan-${Date.now()}`,
      model: "gpt-4.1-mini",
      last_agent: "Fusion Agent Runtime Planner",
      confidence: "medium" as const,
      result_posture: "safe_llm_plan_metadata_only" as const,
    };

    if (prompt.includes("export") || prompt.includes("row-level")) {
      return HttpResponse.json(
        AgentRuntimeLlmPlanSchema.parse({
          ...base,
          outcome: "refused",
          intent: "unsafe_or_deferred_request",
          tool_id: null,
          tool_arguments: {},
          confidence: "high",
          clarification_question: null,
          refusal_reason:
            "Row-level exports and uncontrolled export requests are deferred.",
          safety_notes: [
            "No tool execution was performed.",
            "No row-level data, raw provider payloads, secrets, or PHI were returned.",
          ],
          policy_result: "denied",
          policy_reason:
            "V1 planning only allows safe aggregate or metadata-only tool plans.",
          approval_required: false,
        }),
      );
    }

    if (prompt.includes("anything") || prompt.includes("not sure")) {
      return HttpResponse.json(
        AgentRuntimeLlmPlanSchema.parse({
          ...base,
          outcome: "clarification_required",
          intent: "ambiguous_manager_analytics_question",
          tool_id: null,
          tool_arguments: {},
          clarification_question:
            "Which approved manager analytics question should this answer map to?",
          refusal_reason: null,
          safety_notes: [
            "The planner asks for clarification before selecting a tool.",
          ],
          policy_result: "blocked",
          policy_reason:
            "Ambiguous prompts must be clarified before an approved tool can be selected.",
          approval_required: false,
        }),
      );
    }

    return HttpResponse.json(
      AgentRuntimeLlmPlanSchema.parse({
        ...base,
        outcome: "tool_plan",
        intent: "manager_analytics_aggregate_question",
        tool_id: "ask_manager_analytics",
        tool_arguments: {
          question: "What is lead conversion performance this week?",
          output_level: "aggregate",
        },
        confidence: "high",
        clarification_question: null,
        refusal_reason: null,
        safety_notes: [
          "Plan executed through the first service-owned aggregate analytics slice.",
          "The browser does not receive the API key or raw provider payload.",
        ],
        policy_result: "allowed",
        policy_reason:
          "Selected tool is approved for aggregate manager analytics planning.",
        approval_required: false,
        execution_status: "executed",
        execution: {
          status: "executed",
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          match_status: "matched",
          match_confidence: "high",
          match_reason:
            "Question matched approved manager analytics query keywords: conversion, booked.",
          matched_keywords: ["conversion", "booked"],
          output_type: "aggregate",
          data_classes: ["ops", "integration_metadata"],
          row_count: 2,
          explanation:
            "Executed lead_conversion_funnel.v1 for read model lead_conversion. The result is aggregate-only.",
          policy_reason:
            "Approved aggregate analytics tool executed through service-owned read-model code.",
          result: {
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            output_type: "aggregate",
            aggregation_level: "aggregate",
            data_classes: ["ops", "integration_metadata"],
            definition_versions: {
              lead_source: "v1",
              consultation_scheduled: "v1",
              consultation_completed: "v1",
            },
            filters: {
              created_from: "2026-06-08T00:00:00+00:00",
              created_to: "2026-06-09T12:00:00+00:00",
              time_window_source: "semantic",
              time_window_preset: "this_week",
              time_window_disclosure:
                "Applied semantic time window: this_week.",
              source_provider: null,
              lead_source: null,
              location_id: null,
              limit: 10,
            },
            time_window: {
              source: "semantic",
              preset: "this_week",
              created_from: "2026-06-08T00:00:00+00:00",
              created_to: "2026-06-09T12:00:00+00:00",
              disclosure: "Applied semantic time window: this_week.",
            },
            row_count: 2,
            warnings: [],
            drilldown_available: false,
            export_available: true,
            result: {
              lead_status: [
                { key: "new", count: 28 },
                { key: "consultation_booked", count: 11 },
              ],
              consultation_status: [
                { key: "scheduled", count: 11 },
                { key: "completed", count: 7 },
              ],
            },
          },
        },
        answer_eligibility: {
          eligible: true,
          reason: "Approved aggregate execution can be summarized for managers.",
          execution_status: "executed",
          result_posture: "safe_aggregate_tool_execution",
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          data_classes: ["ops", "integration_metadata"],
          source_refs: {
            tool_id: "ask_manager_analytics",
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            execution_run_id: base.run_id,
            approved_catalog_version_refs: [
              "consultation_completed:v1",
              "consultation_scheduled:v1",
              "lead_source:v1",
            ],
            evidence_refs: [
              "approved_tool_registry",
              "service_owned_read_model_execution",
            ],
          },
        },
        manager_answer: {
          status: "generated",
          model: "gpt-4.1",
          last_agent: "Fusion Manager Answer Generator",
          summary:
            "Lead conversion is active: 11 of 28 new leads reached consultation booking, and 7 consultations are completed in the approved aggregate result.",
          key_numbers: [
            {
              label: "New leads",
              value: 28,
              unit: "leads",
              comparison: "Selected aggregate result.",
            },
            {
              label: "Booked consultations",
              value: 11,
              unit: "consultations",
              comparison: "From approved lead conversion read model.",
            },
            {
              label: "Completed consultations",
              value: 7,
              unit: "consultations",
              comparison: "Aggregate-only status count.",
            },
          ],
          explanation:
            "The answer is grounded in lead_conversion_funnel.v1 and the lead_conversion read model. It summarizes aggregate status counts only.",
          caveats: [
            "No row-level rows are included.",
            "The answer depends on the selected aggregate filters.",
            "Applied semantic time window: this_week.",
          ],
          source_refs: {
            tool_id: "ask_manager_analytics",
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            execution_run_id: base.run_id,
            approved_catalog_version_refs: [
              "consultation_completed:v1",
              "consultation_scheduled:v1",
              "lead_source:v1",
            ],
            evidence_refs: [
              "approved_tool_registry",
              "service_owned_read_model_execution",
            ],
          },
          confidence: "high",
          safety_notes: ["Aggregate-only answer."],
          validation_errors: [],
        },
        result_posture: "safe_aggregate_tool_execution",
      }),
    );
  }),

  http.post("/api/agent-runtime/providers/openai/test", async () => {
    await delay(350);
    return HttpResponse.json(
      AgentRuntimeConnectionCheckSchema.parse({
        ok: true,
        runtime: "agent_runtime",
        provider_kind: "openai",
        credential_kind: "api_key",
        model: "gpt-4.1-mini",
        last_agent: "Fusion OpenAI Health Check",
        output: "ok",
      }),
    );
  }),
];

// People search MSW handler removed: real Next.js route handler at
// app/(staff)/people/search/live/route.ts now serves both SF and CareStack live.
// Per apps/web/CLAUDE.md: "real endpoint arrives → handler deleted".

export const handlers = [
  ...authHandlers,
  ...(USE_REAL_SF ? [] : integrationsAndPersonsHandlers),
  ...healthHandlers,
  ...tenantHandlers,
  ...agentRuntimeHandlers,
  ...outreachHandlers,
];
