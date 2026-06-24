"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  LeadSourceLeadListSchema,
  LeadSourceTreeSchema,
} from "@/lib/api/schemas";

export type LeadSourceTreeFilters = {
  from?: string;
  to?: string;
  search?: string;
  location_id?: string;
};

export type LeadSourceLeadsFilters = {
  channel: string;
  source?: string;
  medium?: string;
  campaign?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
  sort?: "created" | "collected";
  location_id?: string;
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

export function useLeadSourceTree(filters: LeadSourceTreeFilters) {
  return useQuery({
    queryKey: ["dev", "lead-sources", "tree", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/ops/analytics/lead-sources/tree${toQueryString(filters)}`,
      );
      return LeadSourceTreeSchema.parse(raw);
    },
  });
}

export function useLeadSourceLeads(filters: LeadSourceLeadsFilters | null) {
  return useQuery({
    queryKey: ["dev", "lead-sources", "leads", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/ops/analytics/lead-sources/leads${toQueryString(filters ?? {})}`,
      );
      return LeadSourceLeadListSchema.parse(raw);
    },
    enabled: filters !== null && filters.channel.length > 0,
  });
}
