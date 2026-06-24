"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { ExecutiveOverviewSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Executive Overview (ENG-514). Funnel + cost/ROI + realized-cash widgets over
 * the shared fact, served by `GET /dashboard/analytics/executive`. The filters
 * object is part of the query key, so changing the time range / location
 * refetches.
 */
export function useExecutiveOverview(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "executive", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/executive${toAnalyticsQuery(filters)}`,
      );
      return ExecutiveOverviewSchema.parse(raw);
    },
  });
}
