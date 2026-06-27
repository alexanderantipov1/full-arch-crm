"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  DashboardPmLeadListSchema,
  DashboardPmLeadSourcesSchema,
  DashboardPmPaymentGroupListSchema,
  DashboardPmPaymentListSchema,
  DashboardPmPaymentSummarySchema,
  DashboardPmSchema,
  DashboardSummarySchema,
} from "@/lib/api/schemas";
import type {
  DashboardPmLeadLocationTab,
  DashboardPmLeadSort,
} from "@/lib/api/schemas";

export type DashboardPmFilters = {
  from?: string;
  to?: string;
  source_provider?: "salesforce" | "carestack";
  lead_source?: string;
  lead_source_match?: "contains" | "exact";
  location_id?: string;
  q?: string;
};

export type DashboardPmLeadFilters = DashboardPmFilters & {
  status?: string;
  linked_only?: boolean;
  // ENG-561: clinic location tab filter. Omit (or pass the page's "all"/"linked"
  // tab) to leave the param absent. The server resolves each person to exactly
  // one tab; the row DTO is unchanged.
  location_tab?: DashboardPmLeadLocationTab;
  // ENG-559: location-tab ordering. "lead" (default) = lead/funnel date;
  // "appointment" = CareStack appointment-creation order. Request-side only.
  sort?: DashboardPmLeadSort;
  limit?: number;
  offset?: number;
};

// Lets callers gate a query (e.g. only fetch the active tab) without each hook
// re-declaring the full react-query options surface.
export type QueryGate = {
  enabled?: boolean;
};

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/dashboard/summary");
      return DashboardSummarySchema.parse(raw);
    },
  });
}

export function useDashboardPm(filters: DashboardPmFilters) {
  return useQuery({
    queryKey: ["dashboard", "pm", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, value);
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(`/dashboard/pm${qs ? `?${qs}` : ""}`);
      return DashboardPmSchema.parse(raw);
    },
  });
}

export function useDashboardPmLeads(
  filters: DashboardPmLeadFilters,
  options: QueryGate = {},
) {
  return useQuery({
    queryKey: ["dashboard", "pm", "leads", filters],
    enabled: options.enabled,
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, String(value));
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(
        `/dashboard/pm/leads${qs ? `?${qs}` : ""}`,
      );
      return DashboardPmLeadListSchema.parse(raw);
    },
  });
}

// Source options for the PM Leads filter dropdown, grouped by provider.
// The option set changes only when ingest pulls new source values, so a
// few minutes of staleness is fine.
export function useDashboardPmLeadSources() {
  return useQuery({
    queryKey: ["dashboard", "pm", "lead-sources"],
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const raw = await api.get<unknown>("/dashboard/pm/lead-sources");
      return DashboardPmLeadSourcesSchema.parse(raw);
    },
  });
}

export type DashboardPmPaymentFilters = DashboardPmFilters & {
  include_applied?: boolean;
  // ENG-408 resource filter: one lead-source explorer node. On the payments
  // endpoints `lead_source` (from DashboardPmFilters) carries the node's
  // SOURCE level in explorer label terms (lowercase, last-touch), not the
  // PM leads label chain.
  lead_channel?: string;
  lead_medium?: string;
  lead_campaign?: string;
  limit?: number;
  offset?: number;
};

export function useDashboardPmPayments(
  filters: DashboardPmPaymentFilters,
  options: QueryGate = {},
) {
  return useQuery({
    queryKey: ["dashboard", "pm", "payments", filters],
    enabled: options.enabled,
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, String(value));
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(
        `/dashboard/pm/payments${qs ? `?${qs}` : ""}`,
      );
      return DashboardPmPaymentListSchema.parse(raw);
    },
  });
}

// ENG-410: same-day payment groups — same filter surface as the flat list,
// but rows collapse by (person, kind, clinic-local day) with embedded legs.
export function useDashboardPmPaymentGroups(
  filters: DashboardPmPaymentFilters,
  options: QueryGate = {},
) {
  return useQuery({
    queryKey: ["dashboard", "pm", "payments", "groups", filters],
    enabled: options.enabled,
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, String(value));
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(
        `/dashboard/pm/payments/groups${qs ? `?${qs}` : ""}`,
      );
      return DashboardPmPaymentGroupListSchema.parse(raw);
    },
  });
}

// Window-wide totals for the summary bar — same window/filters as the list,
// but aggregated over the whole range (no pagination). ENG-302; accepts the
// payment filter shape so the ENG-408 lead-source node scopes the bar too.
export function useDashboardPmPaymentsSummary(filters: DashboardPmPaymentFilters) {
  return useQuery({
    queryKey: ["dashboard", "pm", "payments", "summary", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, String(value));
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(
        `/dashboard/pm/payments/summary${qs ? `?${qs}` : ""}`,
      );
      return DashboardPmPaymentSummarySchema.parse(raw);
    },
  });
}
