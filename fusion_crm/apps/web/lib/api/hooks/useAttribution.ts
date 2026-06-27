"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  AttributionLeadListSchema,
  AttributionTreeSchema,
} from "@/lib/api/schemas";

/**
 * ENG-450 (Block D) — attribution funnel analytics hooks. Hierarchical
 * lead→consult breakdown sliced by the resolved vendor → channel → campaign
 * chain, plus a drill-down of the leads behind one node.
 */

export type AttributionNodeFilters = {
  vendor?: string;
  channel?: string;
  campaign?: string;
  limit?: number;
  offset?: number;
  period?: string; // YYYY-MM (ENG-572)
};

function toQueryString(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useAttributionTree(period?: string) {
  return useQuery({
    queryKey: ["attribution", "tree", period ?? null],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/analytics/tree${toQueryString({ period })}`,
      );
      return AttributionTreeSchema.parse(raw);
    },
  });
}

export function useAttributionNodeLeads(filters: AttributionNodeFilters | null) {
  return useQuery({
    queryKey: ["attribution", "leads", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/analytics/leads${toQueryString(filters ?? {})}`,
      );
      return AttributionLeadListSchema.parse(raw);
    },
    enabled:
      filters !== null &&
      Boolean(filters.vendor || filters.channel || filters.campaign),
  });
}
