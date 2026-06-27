"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { DoctorPerformanceSchema } from "@/lib/api/schemas";
import type { AnalyticsFilterValue } from "@/lib/api/schemas";
import { toAnalyticsQuery } from "@/lib/api/schemas";

/**
 * Doctor Performance (ENG-520). Per-doctor consult→treatment→surgery→revenue
 * metrics over the shared fact, served by `GET /dashboard/analytics/doctor`.
 */
export function useDoctorPerformance(filters: AnalyticsFilterValue) {
  return useQuery({
    queryKey: ["analytics", "doctor", filters],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/doctor${toAnalyticsQuery(filters)}`,
      );
      return DoctorPerformanceSchema.parse(raw);
    },
  });
}
