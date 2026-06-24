"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { CohortAnalyticsSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Cohort Analytics (ENG-526). Cumulative revenue by lead-creation month, served
 * by `GET /dashboard/analytics/cohort`.
 */
export function useCohortAnalytics(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "cohort", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/cohort${toAnalyticsQuery(filters)}`,
      );
      return CohortAnalyticsSchema.parse(raw);
    },
  });
}
