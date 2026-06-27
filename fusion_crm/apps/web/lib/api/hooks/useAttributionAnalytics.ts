"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { AttributionAnalyticsSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Attribution Analytics (ENG-525). Revenue attribution by dimension
 * (campaign / vendor / caller / coordinator / doctor), served by
 * `GET /dashboard/analytics/attribution`.
 *
 * Campaign dimension has good data. Caller/coordinator/doctor have partial
 * coverage (NULL = "Unassigned"). Vendor is `resolved=false` today —
 * vendor_id is 100% NULL on the fact (ENG-569 wires attribution).
 */
export function useAttributionAnalytics(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "attribution", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/attribution${toAnalyticsQuery(filters)}`,
      );
      return AttributionAnalyticsSchema.parse(raw);
    },
  });
}
