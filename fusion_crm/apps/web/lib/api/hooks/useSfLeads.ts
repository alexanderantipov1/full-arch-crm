"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  SfLeadListSchema,
  SfLeadOperationalSummarySchema,
  SfLeadTaskSummaryListSchema,
  SfPullRecentResponseSchema,
  type SfLead,
  type SfLeadOperationalSummary,
  type SfLeadTaskSummary,
  type SfPullRecentResponse,
} from "@/lib/api/schemas/sfLead";

const KEY = ["sf-leads"] as const;

export function useRecentSfLeads(limit = 5, enabled = true) {
  return useQuery({
    queryKey: [...KEY, limit],
    queryFn: async (): Promise<SfLead[]> => {
      const raw = await api.get<unknown>(
        `/integrations/salesforce/recent-leads?limit=${limit}`,
      );
      return SfLeadListSchema.parse(raw).items;
    },
    enabled,
  });
}

export function usePullRecentSfLeads() {
  const qc = useQueryClient();
  // Explicit <Data, Error, TVariables> generics: a default arg in mutationFn
  // makes TanStack infer TVariables as void, then mutate(5) fails type-check.
  return useMutation<SfPullRecentResponse, Error, number>({
    mutationFn: async (limit) => {
      const raw = await api.post<unknown>(
        `/integrations/salesforce/pull-recent?limit=${limit}`,
      );
      return SfPullRecentResponseSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
    onError: () => {
      void qc.invalidateQueries({ queryKey: ["integrations"] });
    },
  });
}

/** Live SF round-trip for a single Lead — NOT persisted. */
export function useSfLeadRaw(sfId: string | null) {
  return useQuery({
    enabled: !!sfId,
    queryKey: ["sf-lead-raw", sfId],
    queryFn: async (): Promise<Record<string, unknown>> => {
      const raw = await api.get<unknown>(
        `/integrations/salesforce/lead/${encodeURIComponent(sfId!)}/raw`,
      );
      return raw as Record<string, unknown>;
    },
    staleTime: 0,
    gcTime: 60_000,
  });
}

/** Live SF round-trip for the PM card, reduced to an allowlisted DTO. */
export function useSfLeadOperationalSummary(sfId: string | null) {
  return useQuery({
    enabled: !!sfId,
    queryKey: ["sf-lead-operational-summary", sfId],
    queryFn: async (): Promise<SfLeadOperationalSummary> => {
      const raw = await api.get<unknown>(
        `/integrations/salesforce/lead/${encodeURIComponent(
          sfId!,
        )}/operational-summary`,
      );
      return SfLeadOperationalSummarySchema.parse(raw);
    },
    staleTime: 30_000,
    gcTime: 120_000,
  });
}

/** Live SF Task summary for a Lead, reduced to safe call metadata. */
export function useSfLeadOperationalTasks(sfId: string | null) {
  return useQuery({
    enabled: !!sfId,
    queryKey: ["sf-lead-operational-tasks", sfId],
    queryFn: async (): Promise<SfLeadTaskSummary[]> => {
      const raw = await api.get<unknown>(
        `/integrations/salesforce/lead/${encodeURIComponent(
          sfId!,
        )}/operational-tasks?limit=10`,
      );
      return SfLeadTaskSummaryListSchema.parse(raw).items;
    },
    staleTime: 30_000,
    gcTime: 120_000,
  });
}
