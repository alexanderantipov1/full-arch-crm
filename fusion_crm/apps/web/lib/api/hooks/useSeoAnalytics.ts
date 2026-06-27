"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { SeoAnalyticsSchema } from "@/lib/api/schemas";

export type SeoAnalyticsFilters = {
  // Closed [start_date, end_date] window as YYYY-MM-DD. Both optional; the
  // backend defaults to the trailing 30 days when omitted.
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

export function useSeoAnalytics(filters: SeoAnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "seo", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/seo${toQueryString(filters)}`,
      );
      return SeoAnalyticsSchema.parse(raw);
    },
  });
}
