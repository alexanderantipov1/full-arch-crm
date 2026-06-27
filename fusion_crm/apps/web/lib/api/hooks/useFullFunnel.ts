"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { FullFunnelSchema } from "@/lib/api/schemas";
import type { FullFunnelAudience } from "@/lib/api/schemas";

export type FullFunnelFilters = {
  // Audience toggle. `all` (default) is the whole person universe;
  // `marketing` keeps only persons whose lead resolves to an ad channel
  // (marketing ⊆ all for every stage and month).
  audience?: FullFunnelAudience;
  // Closed [start_date, end_date] window as YYYY-MM-DD. Both optional; the
  // backend derives a month range and defaults to the trailing 6 months when
  // omitted. Only the month component of each date matters.
  start_date?: string;
  end_date?: string;
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

export function useFullFunnel(filters: FullFunnelFilters) {
  return useQuery({
    queryKey: ["analytics", "full-funnel", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/full-funnel${toQueryString(filters)}`,
      );
      return FullFunnelSchema.parse(raw);
    },
  });
}
