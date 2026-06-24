"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { CostIntelligenceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Cost Intelligence (ENG-522). Marketing cost per funnel stage over the shared
 * fact, served by `GET /dashboard/analytics/cost`. The filters object is part
 * of the query key, so changing the time range / location refetches.
 *
 * `spend` and every spend-derived metric are `null` when no ad-spend source is
 * connected — renders "—", never a fabricated 0. Operational cost metrics
 * (`cost_per_caller_conversion`, `cost_per_coordinator_conversion`) are always
 * `null` — inputs not yet captured.
 */
export function useCostIntelligence(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "cost", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/cost${toAnalyticsQuery(filters)}`,
      );
      return CostIntelligenceSchema.parse(raw);
    },
  });
}
