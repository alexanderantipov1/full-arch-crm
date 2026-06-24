"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { RevenueIntelligenceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Revenue Intelligence (ENG-521). Revenue by the seven dimensions over the
 * shared fact, served by `GET /dashboard/analytics/revenue`.
 */
export function useRevenueIntelligence(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "revenue", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/revenue${toAnalyticsQuery(filters)}`,
      );
      return RevenueIntelligenceSchema.parse(raw);
    },
  });
}
