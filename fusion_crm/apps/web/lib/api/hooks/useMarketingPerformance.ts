"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { MarketingPerformanceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Marketing Performance (ENG-516). Ad spend ⇄ outcomes by campaign / source
 * over the shared fact, served by
 * `GET /dashboard/analytics/marketing-performance`.
 */
export function useMarketingPerformance(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "marketing-performance", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/marketing-performance${toAnalyticsQuery(filters)}`,
      );
      return MarketingPerformanceSchema.parse(raw);
    },
  });
}
