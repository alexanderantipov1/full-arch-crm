"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  FunnelAggregateSchema,
  FunnelDropoffSchema,
  FunnelOwnersSchema,
  FunnelRevenueByActorSchema,
} from "@/lib/api/schemas";

/** Filters that mirror the ENG-251 PM dashboard contract — keeps the
 * funnel filter bar reusable with the existing date / location / source
 * controls. ``role`` is funnel-specific (scope the aggregation to
 * operational or clinical actors only). */
export type FunnelFilters = {
  from?: string;
  to?: string;
  source_provider?: "salesforce" | "carestack";
  location_id?: string;
  role?: "operational" | "clinical";
};

function toQueryString(filters: FunnelFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useFunnelAggregate(filters: FunnelFilters) {
  return useQuery({
    queryKey: ["funnel", "aggregate", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/funnel/aggregate${toQueryString(filters)}`,
      );
      return FunnelAggregateSchema.parse(raw);
    },
  });
}

export function useFunnelDropoff(filters: FunnelFilters) {
  return useQuery({
    queryKey: ["funnel", "dropoff", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/funnel/dropoff${toQueryString(filters)}`,
      );
      return FunnelDropoffSchema.parse(raw);
    },
  });
}

export function useFunnelRevenueByActor(filters: FunnelFilters) {
  return useQuery({
    queryKey: ["funnel", "revenue-by-actor", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/funnel/revenue-by-actor${toQueryString(filters)}`,
      );
      return FunnelRevenueByActorSchema.parse(raw);
    },
  });
}

export function useFunnelOwners(role?: "operational" | "clinical") {
  return useQuery({
    queryKey: ["funnel", "owners", role ?? null],
    queryFn: async () => {
      const qs = role ? `?role=${role}` : "";
      const raw = await api.get<unknown>(`/funnel/owners${qs}`);
      return FunnelOwnersSchema.parse(raw);
    },
  });
}
