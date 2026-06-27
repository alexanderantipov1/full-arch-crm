"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { RevenueInfluenceMatrixSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Revenue Influence Matrix (ENG-527). Employee × role × revenue influenced,
 * served by `GET /dashboard/analytics/revenue-influence`.
 *
 * DOUBLE-COUNTING CAVEAT: the same patient's revenue is counted once per role
 * they touch. This is intentional per-spec — "Revenue Influenced" measures
 * influence, not additive attribution. Do not sum rows across roles.
 *
 * Vendor role rows will be empty today (vendor_id 100% NULL — see ENG-517).
 */
export function useRevenueInfluence(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "revenue-influence", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/revenue-influence${toAnalyticsQuery(filters)}`,
      );
      return RevenueInfluenceMatrixSchema.parse(raw);
    },
  });
}
