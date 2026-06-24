"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  OpsConsultationSchema,
  PersonDetailSchema,
  PersonListSchema,
  PersonLocationProfileSchema,
  PersonOperationalTimelineSchema,
} from "@/lib/api/schemas";

export function usePersons() {
  return useQuery({
    queryKey: ["persons"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/persons");
      return PersonListSchema.parse(raw);
    },
  });
}

export function usePersonDetail(uid: string) {
  return useQuery({
    queryKey: ["persons", uid],
    queryFn: async () => {
      const raw = await api.get<unknown>(`/persons/${uid}`);
      return PersonDetailSchema.parse(raw);
    },
    enabled: Boolean(uid),
  });
}

export function usePersonOperationalTimeline(uid: string) {
  return useQuery({
    queryKey: ["persons", uid, "operational-timeline"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/persons/${uid}/operational-timeline`,
      );
      return PersonOperationalTimelineSchema.parse(raw);
    },
    enabled: Boolean(uid),
  });
}

export function usePersonConsultations(uid: string) {
  return useQuery({
    queryKey: ["ops", "persons", uid, "consultations"],
    queryFn: async () => {
      const raw = await api.get<unknown>(`/ops/persons/${uid}/consultations`);
      return OpsConsultationSchema.array().parse(raw);
    },
    enabled: Boolean(uid),
  });
}

export function usePersonLocationProfiles(uid: string) {
  return useQuery({
    queryKey: ["ops", "persons", uid, "location-profiles"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/ops/persons/${uid}/location-profiles`,
      );
      return PersonLocationProfileSchema.array().parse(raw);
    },
    enabled: Boolean(uid),
  });
}
