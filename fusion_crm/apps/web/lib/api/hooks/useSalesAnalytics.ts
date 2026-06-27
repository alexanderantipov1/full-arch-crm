"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { SalesAnalyticsSchema } from "@/lib/api/schemas";

export function useSalesAnalytics() {
  return useQuery({
    queryKey: ["analytics", "sales"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/dashboard/analytics/sales");
      return SalesAnalyticsSchema.parse(raw);
    },
  });
}
