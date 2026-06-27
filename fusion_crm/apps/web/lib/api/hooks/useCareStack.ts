"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

interface FetchResult {
  modifiedSince: string;
  pageSize: number;
  data: unknown;
}

export function useFetchCsPatients() {
  // Explicit <Data, Error, TVariables> generics: a default arg in mutationFn
  // makes TanStack infer TVariables as void, then mutate(7) fails type-check.
  return useMutation<FetchResult, Error, number>({
    mutationFn: async (days) => {
      return await api.get<FetchResult>(
        `/integrations/carestack/recent-patients?days=${days}&pageSize=50`,
      );
    },
  });
}

export function useFetchCsAppointments() {
  return useMutation<FetchResult, Error, number>({
    mutationFn: async (days) => {
      return await api.get<FetchResult>(
        `/integrations/carestack/recent-appointments?days=${days}&pageSize=100`,
      );
    },
  });
}

export function useCsPatientRaw(id: string | null) {
  return useQuery({
    enabled: !!id,
    queryKey: ["cs-patient-raw", id],
    queryFn: async (): Promise<Record<string, unknown>> => {
      const raw = await api.get<unknown>(
        `/integrations/carestack/patient/${encodeURIComponent(id!)}/raw`,
      );
      return raw as Record<string, unknown>;
    },
    staleTime: 0,
    gcTime: 60_000,
  });
}

export function useCsAppointmentRaw(id: string | null) {
  return useQuery({
    enabled: !!id,
    queryKey: ["cs-appointment-raw", id],
    queryFn: async (): Promise<Record<string, unknown>> => {
      const raw = await api.get<unknown>(
        `/integrations/carestack/appointment/${encodeURIComponent(id!)}/raw`,
      );
      return raw as Record<string, unknown>;
    },
    staleTime: 0,
    gcTime: 60_000,
  });
}
