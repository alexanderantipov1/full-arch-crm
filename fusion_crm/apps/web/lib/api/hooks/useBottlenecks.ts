"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { BottlenecksSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Bottleneck Detection (ENG-524). Rule-based funnel bottleneck finder over the
 * shared fact, served by `GET /dashboard/analytics/bottlenecks`. The filters
 * object is part of the query key, so changing the time range / location
 * refetches.
 *
 * `findings` is empty when the cohort is too sparse to detect (all entities
 * below minimum sample thresholds). No findings are invented from noise.
 */
export function useBottlenecks(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "bottlenecks", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/bottlenecks${toAnalyticsQuery(filters)}`,
      );
      return BottlenecksSchema.parse(raw);
    },
  });
}
