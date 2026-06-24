"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { FunnelStagesSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Funnel Analytics (ENG-515). The nine-point patient funnel over the shared
 * fact, served by `GET /dashboard/analytics/funnel-stages`. Rendered alongside
 * the existing Full-Funnel v2 (not replacing it).
 */
export function useFunnelStages(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "funnel-stages", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/funnel-stages${toAnalyticsQuery(filters)}`,
      );
      return FunnelStagesSchema.parse(raw);
    },
  });
}
