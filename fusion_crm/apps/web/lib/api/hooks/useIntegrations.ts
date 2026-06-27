"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  type ApiKeyConnectRequest,
  ConnectStartResponseSchema,
  IntegrationAccountSchema,
  IntegrationListSchema,
  type Provider,
  SyncTriggerResponseSchema,
} from "@/lib/api/schemas";

const KEY = ["integrations"] as const;

export function useIntegrations() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const raw = await api.get<unknown>("/integrations");
      return IntegrationListSchema.parse(raw).items;
    },
    refetchInterval: 2000,
  });
}

export function useConnectStart() {
  return useMutation({
    mutationFn: async (provider: Provider) => {
      const raw = await api.post<unknown>(
        `/integrations/${provider}/connect/start`,
      );
      return ConnectStartResponseSchema.parse(raw);
    },
  });
}

export function useApiKeyConnect(provider: Provider) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ApiKeyConnectRequest) => {
      const raw = await api.post<unknown>(
        `/integrations/${provider}/api-key`,
        input,
      );
      return IntegrationAccountSchema.parse(raw);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (provider: Provider) => {
      const raw = await api.post<unknown>(`/integrations/${provider}/sync`);
      return SyncTriggerResponseSchema.parse(raw);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (provider: Provider) => {
      const raw = await api.del<unknown>(`/integrations/${provider}`);
      return IntegrationAccountSchema.parse(raw);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useOAuthCallback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (provider: Provider) => {
      const raw = await api.get<unknown>(
        `/integrations/${provider}/callback?mock=1&code=mock_oauth_code`,
      );
      return IntegrationAccountSchema.parse(raw);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
