"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  TenantSettingSchema,
  TenantWithRelationsSchema,
  type TenantSetting,
  type TenantWithRelations,
} from "@/lib/api/schemas/tenant";

/**
 * Reads the current tenant + its locations, integration credentials, and
 * settings. Path matches the FastAPI route that ENG-124 will serve.
 *
 * Tenant config is stable, so we keep a 60s staleTime — page revisits during
 * the same shift won't refetch unless a mutation invalidates the key.
 */
export function useCurrentTenant() {
  return useQuery<TenantWithRelations>({
    queryKey: ["tenant", "current"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/tenant/current");
      return TenantWithRelationsSchema.parse(raw);
    },
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
}

interface LocationsSyncResult {
  created: number;
  updated: number;
  deactivated: number;
  total_seen: number;
}

/**
 * Trigger a sync of locations from CareStack into ``tenant.location``.
 * Idempotent — re-running is safe. Invalidates the tenant-current query
 * on success so the LocationsTab refetches and shows the freshly-imported
 * rows without a manual reload.
 */
export function useSyncLocationsFromCareStack() {
  const qc = useQueryClient();
  return useMutation<LocationsSyncResult, Error, void>({
    mutationFn: async () => {
      return await api.post<LocationsSyncResult>(
        "/tenant/locations/sync-from-carestack",
      );
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant", "current"] });
    },
  });
}

export function useUpsertTenantSetting() {
  const qc = useQueryClient();
  return useMutation<
    TenantSetting,
    Error,
    { key: string; value: Record<string, unknown> }
  >({
    mutationFn: async ({ key, value }) => {
      const raw = await api.put<unknown>(
        `/tenant/settings/${encodeURIComponent(key)}`,
        { value },
      );
      return TenantSettingSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant", "current"] });
    },
  });
}
