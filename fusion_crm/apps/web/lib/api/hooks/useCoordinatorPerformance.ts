"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { CoordinatorPerformanceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Coordinator Performance (ENG-519). Per-coordinator consult→surgery funnel
 * over the shared fact, served by `GET /dashboard/analytics/coordinator`.
 */
export function useCoordinatorPerformance(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "coordinator", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/coordinator${toAnalyticsQuery(filters)}`,
      );
      return CoordinatorPerformanceSchema.parse(raw);
    },
  });
}
