"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { PatientJourneySchema } from "@/lib/api/schemas";

/**
 * Patient Journey (ENG-523). One person's fact-derived stage timeline, served
 * by `GET /dashboard/analytics/patient-journey/{person_uid}`. Disabled until a
 * person is selected (the page is also a drill-down target from other pages).
 */
export function usePatientJourney(personUid: string | null) {
  return useQuery({
    queryKey: ["analytics", "patient-journey", personUid],
    enabled: Boolean(personUid),
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/dashboard/analytics/patient-journey/${personUid}`,
      );
      return PatientJourneySchema.parse(raw);
    },
  });
}
