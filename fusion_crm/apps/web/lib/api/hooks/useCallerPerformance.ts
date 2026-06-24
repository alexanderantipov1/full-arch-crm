"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { CallerPerformanceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Caller Performance (ENG-518). Per-caller lead→contact→consult metrics
 * over the shared fact, served by `GET /dashboard/analytics/caller`.
 *
 * `calls_made` is `null` on every row — the fact has no dialer call-count
 * column. `first_contact_date` records whether contact was made, not attempts.
 */
export function useCallerPerformance(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "caller", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/caller${toAnalyticsQuery(filters)}`,
      );
      return CallerPerformanceSchema.parse(raw);
    },
  });
}
