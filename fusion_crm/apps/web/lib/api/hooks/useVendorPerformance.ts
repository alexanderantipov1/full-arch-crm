"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { VendorPerformanceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Vendor Performance (ENG-517). Per-vendor lead-to-revenue ranking grouped
 * by vendor_id, served by `GET /dashboard/analytics/vendor`.
 *
 * `vendor_attribution_wired` will be `false` today — vendor_id is 100% NULL
 * on the fact (ENG-569 wires attribution). `spend_managed` and `roi` are
 * always `null` (no vendor→spend column on the analytics fact).
 */
export function useVendorPerformance(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "vendor", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/vendor${toAnalyticsQuery(filters)}`,
      );
      return VendorPerformanceSchema.parse(raw);
    },
  });
}
