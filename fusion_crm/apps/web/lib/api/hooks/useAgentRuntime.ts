"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  AgentRuntimeApprovalRequestSchema,
  AgentRuntimeApprovalRequestsSchema,
  AgentRuntimeConnectionCheckSchema,
  AgentRuntimeDiaCatalogLinkagesSchema,
  AgentRuntimeLlmPlanInputSchema,
  AgentRuntimeLlmPlanSchema,
  AgentRuntimeRunHistorySchema,
  AgentRuntimeToolsProjectionSchema,
  type AgentRuntimeApprovalDecision,
  type AgentRuntimeApprovalRequest,
  type AgentRuntimeApprovalRequests,
  type AgentRuntimeConnectionCheck,
  type AgentRuntimeDiaCatalogLinkages,
  type AgentRuntimeLlmPlan,
  type AgentRuntimeLlmPlanInput,
  type AgentRuntimeRunHistory,
  type AgentRuntimeRunHistoryFilters,
  type AgentRuntimeToolsProjection,
} from "@/lib/api/schemas/agentRuntime";

export function useAgentRuntimeTools() {
  return useQuery<AgentRuntimeToolsProjection>({
    queryKey: ["agent-runtime", "tools"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/agent-runtime/tools");
      return AgentRuntimeToolsProjectionSchema.parse(raw);
    },
    staleTime: 60_000,
  });
}

export function useAgentRuntimeRuns(
  filters: Partial<AgentRuntimeRunHistoryFilters> = {},
) {
  return useQuery<AgentRuntimeRunHistory>({
    queryKey: ["agent-runtime", "runs", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value === null || value === undefined || value === "") continue;
        params.set(key, String(value));
      }
      const query = params.toString();
      const raw = await api.get<unknown>(
        query ? `/agent-runtime/runs?${query}` : "/agent-runtime/runs",
      );
      return AgentRuntimeRunHistorySchema.parse(raw);
    },
    staleTime: 30_000,
  });
}

export function useAgentRuntimeApprovals() {
  return useQuery<AgentRuntimeApprovalRequests>({
    queryKey: ["agent-runtime", "approvals"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/agent-runtime/approvals");
      return AgentRuntimeApprovalRequestsSchema.parse(raw);
    },
    staleTime: 30_000,
  });
}

export function useAgentRuntimeDiaCatalogLinkages() {
  return useQuery<AgentRuntimeDiaCatalogLinkages>({
    queryKey: ["agent-runtime", "dia-catalog-linkages"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/agent-runtime/dia-catalog-linkages");
      return AgentRuntimeDiaCatalogLinkagesSchema.parse(raw);
    },
    staleTime: 60_000,
  });
}

export function useDecideAgentRuntimeApproval() {
  const qc = useQueryClient();
  return useMutation<
    AgentRuntimeApprovalRequest,
    Error,
    {
      approvalId: string;
      decision: AgentRuntimeApprovalDecision;
      decisionSummary: string;
      editSummary?: string;
    }
  >({
    mutationFn: async ({
      approvalId,
      decision,
      decisionSummary,
      editSummary,
    }) => {
      const raw = await api.post<unknown>(
        `/agent-runtime/approvals/${approvalId}/decision`,
        {
          decision,
          decision_summary: decisionSummary,
          edit_summary: editSummary ?? null,
        },
      );
      return AgentRuntimeApprovalRequestSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-runtime", "approvals"] });
      void qc.invalidateQueries({ queryKey: ["agent-runtime", "runs"] });
    },
  });
}

export function useTestOpenAIAgentRuntime() {
  const qc = useQueryClient();
  return useMutation<AgentRuntimeConnectionCheck, Error, void>({
    mutationFn: async () => {
      const raw = await api.post<unknown>(
        "/agent-runtime/providers/openai/test",
        {},
      );
      return AgentRuntimeConnectionCheckSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-runtime", "runs"] });
    },
  });
}

export function useCreateAgentRuntimeLlmPlan() {
  const qc = useQueryClient();
  return useMutation<AgentRuntimeLlmPlan, Error, AgentRuntimeLlmPlanInput>({
    mutationFn: async (payload) => {
      const input = AgentRuntimeLlmPlanInputSchema.parse(payload);
      const raw = await api.post<unknown>("/agent-runtime/llm/plans", input);
      return AgentRuntimeLlmPlanSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-runtime", "runs"] });
    },
  });
}
