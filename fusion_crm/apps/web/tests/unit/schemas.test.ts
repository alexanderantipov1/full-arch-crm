import { describe, expect, it } from "vitest";
import {
  ConnectStartResponseSchema,
  AgentRuntimeConnectionCheckSchema,
  AgentRuntimeApprovalRequestsSchema,
  AgentRuntimeRunHistorySchema,
  AgentRuntimeDiaCatalogLinkagesSchema,
  AgentRuntimeLlmPlanInputSchema,
  AgentRuntimeLlmPlanSchema,
  AgentRuntimeManagerAnswerEligibilitySchema,
  AgentRuntimeManagerAnswerSchema,
  AgentRuntimeToolsProjectionSchema,
  CatalogDraftPatchSchema,
  CatalogProposalCreateInputSchema,
  CatalogProposalHistorySchema,
  CatalogProposalListSchema,
  CatalogVersionHistorySchema,
  IntegrationAccountSchema,
  IntegrationCredentialBootstrapInputSchema,
  OpsConsultationSchema,
  PersonDetailSchema,
  PersonLocationProfileSchema,
  PeopleSearchOutSchema,
  ProviderSchema,
  TimelineEventSchema,
} from "@/lib/api/schemas";
import { personDetails } from "@/lib/msw/fixtures/persons";
import { rawEvents } from "@/lib/msw/fixtures/inspector";
import { integrationStore } from "@/lib/msw/fixtures/integrations";

describe("API contract schemas accept fixture data", () => {
  it("PersonDetail fixtures parse", () => {
    for (const detail of Object.values(personDetails)) {
      expect(() => PersonDetailSchema.parse(detail)).not.toThrow();
    }
  });

  it("Timeline events parse and use known kinds", () => {
    for (const detail of Object.values(personDetails)) {
      for (const ev of detail.timeline) {
        expect(() => TimelineEventSchema.parse(ev)).not.toThrow();
      }
    }
  });

  it("IntegrationAccount fixtures parse", () => {
    for (const account of Object.values(integrationStore)) {
      expect(() => IntegrationAccountSchema.parse(account)).not.toThrow();
    }
    expect(() =>
      IntegrationAccountSchema.parse({
        id: "ddee0001-0000-0000-0000-000000000003",
        provider: "salesforce",
        status: "needs_reconnect",
        display_name: "Salesforce production",
        last_sync_at: null,
        last_sync_summary: null,
        error_message: "Reconnect this integration to resume scheduled sync.",
      }),
    ).not.toThrow();
  });

  it("Raw event provider values are in the canonical set", () => {
    for (const ev of rawEvents) {
      expect(() => ProviderSchema.parse(ev.provider)).not.toThrow();
    }
  });

  it("ConnectStart discriminated union round-trips both arms", () => {
    expect(() =>
      ConnectStartResponseSchema.parse({
        kind: "oauth_redirect",
        redirect_url: "http://localhost:3000/cb",
      }),
    ).not.toThrow();
    expect(() =>
      ConnectStartResponseSchema.parse({
        kind: "api_key_form",
        label: "API key",
        placeholder: "...",
      }),
    ).not.toThrow();
  });

  it("bootstrap credential schema accepts Salesforce app config only with api_key kind", () => {
    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "salesforce",
        credential_kind: "api_key",
        client_id: "sf-client-id",
        client_secret: "sf-client-secret",
        callback_url:
          "https://fusioncrm.app/api/integrations/salesforce/callback",
        domain: "login.salesforce.com",
      }),
    ).not.toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "salesforce",
        credential_kind: "password_grant",
        client_id: "sf-client-id",
        client_secret: "sf-client-secret",
        callback_url:
          "https://fusioncrm.app/api/integrations/salesforce/callback",
      }),
    ).toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "salesforce",
        credential_kind: "api_key",
        client_id: "sf-client-id",
        client_secret: "sf-client-secret",
        callback_url:
          "https://fusioncrm.app/api/integrations/salesforce/callback",
        vendor_key: "carestack-only",
      }),
    ).toThrow();
  });

  it("bootstrap credential schema requires CareStack password-grant fields", () => {
    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "carestack",
        credential_kind: "password_grant",
        client_id: "cs-client-id",
        client_secret: "cs-client-secret",
        vendor_key: "vendor",
        account_key: "account",
        account_id: "account-id",
        idp_base_url: "https://identity.carestack.com",
        api_base_url: "https://api.carestack.com",
      }),
    ).not.toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "carestack",
        credential_kind: "password_grant",
        client_id: "cs-client-id",
        client_secret: "cs-client-secret",
      }),
    ).toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "carestack",
        credential_kind: "password_grant",
        client_id: "cs-client-id",
        client_secret: "cs-client-secret",
        vendor_key: "vendor",
        account_key: "account",
        account_id: "account-id",
        idp_base_url: "https://identity.carestack.com",
        api_base_url: "https://api.carestack.com",
        callback_url:
          "https://fusioncrm.app/api/integrations/salesforce/callback",
      }),
    ).toThrow();
  });

  it("bootstrap credential schema accepts OpenAI API-key config only", () => {
    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "openai",
        credential_kind: "api_key",
        display_name: "OpenAI primary",
        api_key: "sk-test-openai-secret",
      }),
    ).not.toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "openai",
        credential_kind: "password_grant",
        api_key: "sk-test-openai-secret",
      }),
    ).toThrow();

    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "openai",
        credential_kind: "api_key",
        api_key: "sk-test-openai-secret",
        client_secret: "provider-mismatch",
      }),
    ).toThrow();
  });

  it("agent runtime OpenAI health check response parses", () => {
    expect(() =>
      AgentRuntimeConnectionCheckSchema.parse({
        ok: true,
        runtime: "agent_runtime",
        provider_kind: "openai",
        credential_kind: "api_key",
        model: "gpt-4.1-mini",
        last_agent: "Fusion OpenAI Health Check",
        output: "ok",
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeConnectionCheckSchema.parse({
        ok: true,
        runtime: "agent_runtime",
        provider_kind: "openai",
        credential_kind: "password_grant",
        model: "gpt-4.1-mini",
        last_agent: "Fusion OpenAI Health Check",
        output: "ok",
      }),
    ).toThrow();
  });

  it("agent runtime LLM planning request and response parse safely", () => {
    expect(() =>
      AgentRuntimeLlmPlanInputSchema.parse({
        user_prompt:
          "Which aggregate manager analytics tool should answer lead conversion performance this week?",
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeLlmPlanInputSchema.parse({
        user_prompt: "Use sk-test-secret in the full_prompt.",
      }),
    ).toThrow();

    expect(() =>
      AgentRuntimeLlmPlanInputSchema.parse({
        user_prompt: "select * from phi.patient",
      }),
    ).toThrow();

    expect(() =>
      AgentRuntimeLlmPlanSchema.parse({
        runtime: "agent_runtime",
        provider_kind: "openai",
        credential_kind: "api_key",
        run_id: "run-llm-plan-1",
        model: "gpt-4.1-mini",
        last_agent: "Fusion Agent Runtime Planner",
        outcome: "tool_plan",
        intent: "manager_analytics_aggregate_question",
        tool_id: "ask_manager_analytics",
        tool_arguments: {
          question: "Summarize aggregate lead conversion posture.",
          output_level: "aggregate",
        },
        confidence: "high",
        clarification_question: null,
        refusal_reason: null,
        safety_notes: [
          "Plan is metadata-only until a service-owned approved tool executes.",
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
          output_type: "aggregate",
          data_classes: ["ops", "integration_metadata"],
          row_count: 2,
          explanation:
            "Executed lead_conversion_funnel.v1 for read model lead_conversion.",
          policy_reason:
            "Approved aggregate analytics tool executed through service-owned read-model code.",
          result: {
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            result: {
              lead_status: [{ key: "new", count: 4 }],
            },
          },
        },
        answer_eligibility: {
          eligible: true,
          reason: "Approved aggregate execution can be summarized for managers.",
          answer_posture: "generated",
          execution_status: "executed",
          result_posture: "safe_aggregate_tool_execution",
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          data_classes: ["ops", "integration_metadata"],
          data_quality_evidence_refs: ["lead.lead_source"],
          data_quality_metrics: [
            {
              id: "source_attribution_coverage",
              label: "Source attribution coverage",
              value: 0.75,
              unit: "ratio",
              numerator: 3,
              denominator: 4,
              status: "caveat",
              evidence_ref: "lead.lead_source",
            },
          ],
          source_refs: {
            tool_id: "ask_manager_analytics",
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            execution_run_id: "run-llm-plan-1",
            approved_catalog_version_refs: ["lead_source:v1"],
            evidence_refs: ["service_owned_read_model_execution"],
          },
        },
        manager_answer: {
          status: "generated_with_caveat",
          summary: "Lead conversion improved for the selected aggregate period.",
          key_numbers: [
            {
              label: "New leads",
              value: 4,
              unit: "leads",
              comparison: "Selected aggregate result.",
            },
          ],
          explanation:
            "The answer is grounded in approved aggregate execution only.",
          caveats: ["No row-level rows are included."],
          source_refs: {
            tool_id: "ask_manager_analytics",
            query_id: "lead_conversion_funnel.v1",
            read_model_id: "lead_conversion",
            execution_run_id: "run-llm-plan-1",
            approved_catalog_version_refs: ["lead_source:v1"],
            evidence_refs: ["service_owned_read_model_execution"],
          },
          confidence: "high",
          safety_notes: ["Aggregate-only answer."],
          validation_errors: [],
        },
        result_posture: "safe_aggregate_tool_execution",
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeLlmPlanSchema.parse({
        runtime: "agent_runtime",
        provider_kind: "openai",
        credential_kind: "api_key",
        run_id: "run-llm-plan-unsafe",
        model: "gpt-4.1-mini",
        last_agent: "Fusion Agent Runtime Planner",
        outcome: "tool_plan",
        intent: "unsafe",
        tool_id: "unsafe_sql",
        confidence: "high",
        policy_result: "raw_sql_allowed",
        policy_reason: "Unsafe value should fail.",
        result_posture: "raw_provider_payload",
      }),
    ).toThrow();
  });

  it("agent runtime manager answer contract parses", () => {
    expect(() =>
      AgentRuntimeManagerAnswerSchema.parse({
        status: "generated",
        summary: "Lead conversion improved for the selected aggregate period.",
        key_numbers: [
          {
            label: "Converted leads",
            value: 42,
            unit: "leads",
            comparison: "Higher than the prior aggregate period.",
          },
        ],
        explanation:
          "The answer is based on approved aggregate execution metadata.",
        caveats: ["The answer excludes row-level lead details."],
        source_refs: {
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          execution_run_id: "run-123",
          approved_catalog_version_refs: ["catalog:v1"],
          evidence_refs: ["service_owned_read_model_execution"],
        },
        confidence: "high",
        safety_notes: ["Aggregate-only answer; no row-level rows included."],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeManagerAnswerSchema.parse({
        status: "generated_with_caveat",
        summary:
          "Lead conversion can be summarized with aggregate data-quality caveats.",
        key_numbers: [
          {
            label: "Converted leads",
            value: 42,
            unit: "leads",
          },
        ],
        explanation:
          "The answer is based on approved aggregate execution metadata.",
        caveats: ["Some lead source values are unmapped."],
        source_refs: {
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          execution_run_id: "run-123",
          approved_catalog_version_refs: ["catalog:v1"],
          evidence_refs: ["service_owned_read_model_execution"],
        },
        confidence: "medium",
        safety_notes: ["Aggregate-only answer; no row-level rows included."],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeManagerAnswerSchema.parse({
        status: "generated",
        summary: "Missing source refs should fail.",
        key_numbers: [{ label: "Converted leads", value: 42 }],
        explanation: "Aggregate explanation.",
        confidence: "medium",
        safety_notes: ["Aggregate-only answer."],
      }),
    ).toThrow();

    expect(() =>
      AgentRuntimeManagerAnswerEligibilitySchema.parse({
        eligible: true,
        reason: "Planning-only posture should fail.",
        answer_posture: "generated",
        execution_status: "not_executed",
        result_posture: "safe_llm_plan_metadata_only",
      }),
    ).toThrow();

    expect(() =>
      AgentRuntimeManagerAnswerEligibilitySchema.parse({
        eligible: true,
        reason: "Blocked posture should fail when eligible.",
        answer_posture: "blocked",
        execution_status: "executed",
        result_posture: "safe_aggregate_tool_execution",
        source_refs: {
          tool_id: "ask_manager_analytics",
          query_id: "lead_conversion_funnel.v1",
          read_model_id: "lead_conversion",
          execution_run_id: "run-123",
        },
      }),
    ).toThrow();
  });

  it("agent runtime tools projection response parses", () => {
    expect(() =>
      AgentRuntimeToolsProjectionSchema.parse({
        runtime: "agent_runtime",
        source: "packages.tools.registry",
        tools: [
          {
            id: "data_intelligence_profile_field",
            title: "Data Intelligence Profile Field",
            description: "Profile one allowlisted field.",
            owner_package: "packages.tools.data_intelligence_tools",
            status: "available",
            callable: true,
            data_classes: ["ops"],
            input_posture: "allowlisted dataset and field",
            output_posture: "aggregate field profile",
            policy_posture: "service-owned aggregates only",
            limits: ["aggregate output"],
            downstream_surfaces: ["data_intelligence"],
            requires_approval: false,
            notes: [],
          },
        ],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeToolsProjectionSchema.parse({
        runtime: "agent_runtime",
        source: "packages.tools.registry",
        tools: [
          {
            id: "unsafe_sql",
            title: "Unsafe SQL",
            description: "Invalid status should fail.",
            owner_package: "packages.tools",
            status: "unsafe",
            callable: true,
            data_classes: [],
            input_posture: "raw sql",
            output_posture: "rows",
            policy_posture: "none",
          },
        ],
      }),
    ).toThrow();
  });

  it("agent runtime run history response parses", () => {
    expect(() =>
      AgentRuntimeRunHistorySchema.parse({
        runtime: "agent_runtime",
        runs: [
          {
            id: "run-1",
            agent_name: "Fusion OpenAI Health Check",
            provider_kind: "openai",
            model: "gpt-4.1-mini",
            run_kind: "provider_health_check",
            status: "success",
            started_at: "2026-06-05T16:00:00Z",
            completed_at: "2026-06-05T16:00:00Z",
            duration_ms: 42,
            triggered_by: "ops@example.com",
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
              ],
              evidence_refs: ["provider_health_check"],
              compliance_notes: ["No sensitive details stored."],
              linked_approval_request_ids: [],
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
                  execution_run_id: "run-1",
                  approved_catalog_version_refs: ["lead_source:v1"],
                  evidence_refs: ["service_owned_read_model_execution"],
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
            id: "run-denied",
            agent_name: "Manager Analytics Export Planner",
            provider_kind: "openai",
            model: "gpt-4.1-mini",
            run_kind: "export_request_preflight",
            status: "denied",
            started_at: "2026-06-05T16:00:00Z",
            completed_at: "2026-06-05T16:00:00Z",
            duration_ms: 42,
            triggered_by: "ops@example.com",
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
                "Row-level exports are deferred until allowlists are stable.",
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
                  reason: "Field allowlist is not approved.",
                  evidence_refs: ["deferred_row_level_exports"],
                },
              ],
              evidence_refs: ["export_preflight"],
              compliance_notes: ["No file was generated."],
              linked_approval_request_ids: [],
            },
            error_code: "row_level_export_denied",
            error_message: "Denied by row-level export policy.",
          },
        ],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeRunHistorySchema.parse({
        runtime: "agent_runtime",
        runs: [
          {
            id: "run-unsafe",
            agent_name: "Unsafe",
            provider_kind: "openai",
            run_kind: "sql",
            status: "raw_sql",
            started_at: "2026-06-05T16:00:00Z",
            result_posture: "unsafe",
            audit_summary: {
              policy_result: "denied",
            },
          },
        ],
      }),
    ).toThrow();
  });

  it("agent runtime approval requests response parses", () => {
    expect(() =>
      AgentRuntimeApprovalRequestsSchema.parse({
        runtime: "agent_runtime",
        approvals: [
          {
            id: "approval-1",
            source_run_id: null,
            agent_name: "Data Intelligence Mapping Helper",
            tool_id: "data_intelligence_semantic_mapping_proposal",
            target_kind: "semantic_catalog_mapping_proposal",
            target_ref: "lead-source-google-ads",
            title: "Review mapping candidate",
            reason: "Repeated source values need human review.",
            evidence_summary: "Aggregate coverage only.",
            requested_action: "Create Semantic Catalog review draft.",
            status: "pending",
            requested_at: "2026-06-05T16:10:00Z",
            requested_by: "ops@example.com",
            decided_at: null,
            decided_by: null,
            data_classes: ["ops"],
            affected_surfaces: ["semantic_catalog"],
            risk_flags: ["business_meaning_change"],
            approval_posture: "human_review_required_no_auto_mutation",
            decision_summary: null,
            edit_summary: null,
          },
        ],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeApprovalRequestsSchema.parse({
        runtime: "agent_runtime",
        approvals: [
          {
            id: "approval-unsafe-status",
            agent_name: "Unsafe",
            target_kind: "write_tool_execution",
            title: "Unsafe",
            reason: "Invalid status should fail.",
            evidence_summary: "Aggregate only.",
            requested_action: "Run",
            status: "auto_executed",
            requested_at: "2026-06-05T16:10:00Z",
            approval_posture: "unsafe",
          },
        ],
      }),
    ).toThrow();
  });

  it("agent runtime DIA catalog linkages response parses", () => {
    expect(() =>
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
            evidence_refs: ["mapping_coverage_summary"],
            impact_surfaces: [
              {
                surface: "semantic_catalog",
                confidence: "known",
                reason:
                  "Human review proposal is the only path into catalog meaning.",
              },
              {
                surface: "reports",
                confidence: "unknown",
                reason: "Report dependencies need registry impact metadata.",
              },
            ],
            path: [
              {
                id: "agent_run",
                title: "Agent run",
                status: "ready",
                owner: "packages.agent_runtime",
                contract: "Safe run summary only.",
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
            ],
          },
        ],
      }),
    ).not.toThrow();

    expect(() =>
      AgentRuntimeDiaCatalogLinkagesSchema.parse({
        runtime: "agent_runtime",
        source: "agent_runtime_projection",
        linkages: [
          {
            id: "unsafe-linkage",
            title: "Unsafe linkage",
            source_agent: "Agent",
            output_kind: "mapping_proposal",
            review_posture: "auto_approved",
            downstream_consumption: "draft_docs",
            impact_surfaces: [],
            path: [],
          },
        ],
      }),
    ).toThrow();
  });

  it("bootstrap credential schema rejects unsupported providers", () => {
    expect(() =>
      IntegrationCredentialBootstrapInputSchema.parse({
        provider_kind: "hubspot",
        credential_kind: "api_key",
        client_id: "hubspot-client-id",
        client_secret: "hubspot-client-secret",
      }),
    ).toThrow();
  });

  it("PeopleSearchOut accepts partial provider warnings", () => {
    const parsed = PeopleSearchOutSchema.parse({
      query: { phone_normalised: "18186403956" },
      salesforce: { matches: [] },
      carestack: { matches: [] },
      linked_person_uids: [],
      warnings: [
        {
          provider: "salesforce",
          code: "not_connected",
          message: "Salesforce not connected.",
        },
      ],
    });

    expect(parsed.warnings).toHaveLength(1);
  });

  it("Ops person context schemas accept backend projections", () => {
    expect(() =>
      OpsConsultationSchema.parse({
        id: "11111111-1111-1111-1111-111111111111",
        person_uid: "22222222-2222-2222-2222-222222222222",
        source_provider: "carestack",
        source_instance: "carestack-main",
        external_id: "7821",
        scheduled_at: "2026-06-01T14:00:00+00:00",
        duration_minutes: 30,
        status: "rescheduled",
        consultation_kind: "other",
        location_id: "33333333-3333-3333-3333-333333333333",
        provider_clinician_name: "Dr. Smith",
        raw_event_id: null,
        created_at: "2026-05-22T09:00:00+00:00",
        updated_at: "2026-05-22T09:00:00+00:00",
      }),
    ).not.toThrow();

    expect(() =>
      PersonLocationProfileSchema.parse({
        id: "44444444-4444-4444-4444-444444444444",
        person_uid: "22222222-2222-2222-2222-222222222222",
        location_id: "33333333-3333-3333-3333-333333333333",
        relationship_kind: "prospect",
        relationship_status: "consult_scheduled",
        last_evidence_provider: "carestack",
        last_evidence_source_instance: "carestack-main",
        last_evidence_external_id: "7821",
        last_evidence_at: "2026-06-01T14:00:00+00:00",
        last_consultation_id: null,
        last_raw_event_id: null,
        created_at: "2026-05-22T09:00:00+00:00",
        updated_at: "2026-05-22T09:00:00+00:00",
      }),
    ).not.toThrow();
  });

  it("Semantic catalog proposal schemas accept backend contracts", () => {
    const proposal = {
      id: "11111111-1111-1111-1111-111111111111",
      tenant_id: "22222222-2222-2222-2222-222222222222",
      raw_value: "IG Campaign June",
      source_system: "salesforce",
      source_field: "LeadSource",
      suggested_term: "paid_social/facebook",
      definition: "Paid social lead from Meta, Facebook, or Instagram campaigns.",
      synonyms: ["Instagram", "IG", "Meta"],
      confidence: 0.9,
      reason: "Contains IG source pattern in campaign source data.",
      reviewer_note: "",
      affected_questions: ["Q16", "Q19"],
      affected_read_models: ["lead_conversion"],
      status: "proposed",
      source_type: "agent",
      source_reference_id: "semantic-agent-run-1",
      created_by_actor_id: null,
      reviewed_by_actor_id: null,
      reviewed_at: null,
      created_at: "2026-06-01T12:00:00+00:00",
      updated_at: "2026-06-01T12:00:00+00:00",
    };

    expect(() =>
      CatalogProposalListSchema.parse({ items: [proposal] }),
    ).not.toThrow();

    expect(() =>
      CatalogProposalCreateInputSchema.parse({
        raw_value: "Google PMAX",
        source_system: "salesforce",
        source_field: "Campaign",
        suggested_term: "paid_search/google",
        definition: "Paid search or Google Ads lead source.",
        synonyms: ["Google Ads", "Performance Max"],
        confidence: 0.65,
        reason: "PMAX is a Google campaign type.",
        reviewer_note: "",
        affected_questions: ["Q18"],
        affected_read_models: ["paid_leads"],
        source_type: "manual",
        source_reference_id: null,
      }),
    ).not.toThrow();

    expect(() =>
      CatalogDraftPatchSchema.parse({
        proposal_ids: ["11111111-1111-1111-1111-111111111111"],
        patch: [
          {
            term: "paid_social/facebook",
            definition:
              "Paid social lead from Meta, Facebook, or Instagram campaigns.",
          },
        ],
        catalog_version_id: null,
      }),
    ).not.toThrow();

    expect(() =>
      CatalogProposalHistorySchema.parse({
        proposal_id: "11111111-1111-1111-1111-111111111111",
        items: [
          {
            action: "approved",
            status: "approved",
            actor_id: "33333333-3333-3333-3333-333333333333",
            occurred_at: "2026-06-01T12:10:00+00:00",
            reason: "Human reviewer decision.",
            reviewer_note: "Approved by marketing.",
            catalog_version_id: "44444444-4444-4444-4444-444444444444",
          },
        ],
      }),
    ).not.toThrow();

    expect(() =>
      CatalogVersionHistorySchema.parse({
        term: "paid_social/facebook",
        items: [
          {
            id: "44444444-4444-4444-4444-444444444444",
            tenant_id: "22222222-2222-2222-2222-222222222222",
            term: "paid_social/facebook",
            version: 1,
            review_status: "approved",
            definition:
              "Paid social lead from Meta, Facebook, or Instagram campaigns.",
            synonyms: ["Instagram", "Meta"],
            allowed_data_sources: ["salesforce.LeadSource"],
            data_classes: ["ops"],
            allowed_outputs: ["aggregate"],
            canonical_fields: [],
            row_level_fields: [],
            aggregate_metrics: [],
            used_by: ["lead_conversion"],
            source_references: [],
            previous_version_id: null,
            proposal_id: "11111111-1111-1111-1111-111111111111",
            previous_value: null,
            new_value: { term: "paid_social/facebook", version: 1 },
            reason: "Human reviewer decision.",
            affected_questions: ["Q16"],
            affected_read_models: ["lead_conversion"],
            affected_reports: [],
            affected_dashboard_panels: [],
            affected_chat_answers: [],
            affected_agent_briefs: [],
            approved_by_actor_id: "33333333-3333-3333-3333-333333333333",
            approved_at: "2026-06-01T12:10:00+00:00",
            created_at: "2026-06-01T12:10:00+00:00",
            updated_at: "2026-06-01T12:10:00+00:00",
          },
        ],
      }),
    ).not.toThrow();
  });
});
