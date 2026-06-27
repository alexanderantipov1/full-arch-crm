"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  IntegrationCredentialBootstrapInputSchema,
  TenantIntegrationCredentialSchema,
  type IntegrationCredentialBootstrapInput,
  type TenantIntegrationCredential,
} from "@/lib/api/schemas/tenant";

/**
 * Mutations on per-tenant integration credential rows. Secret-bearing
 * create/update flows parse locally before sending and parse backend
 * responses as metadata-only DTOs, so stored payload values never flow
 * back into React state.
 */

export interface CredentialUpdateInput {
  display_name?: string | null;
  location_id?: string | null;
  tags?: string[];
}

function invalidateCredentials(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["tenant", "current"] });
  qc.invalidateQueries({ queryKey: ["integrations"] });
}

export function useUpsertBootstrapCredential() {
  const qc = useQueryClient();
  return useMutation<
    TenantIntegrationCredential,
    Error,
    IntegrationCredentialBootstrapInput
  >({
    mutationFn: async (input) => {
      const parsed = IntegrationCredentialBootstrapInputSchema.parse(input);
      const raw = await api.post<unknown>("/tenant/credentials", parsed);
      return TenantIntegrationCredentialSchema.parse(raw);
    },
    onSuccess: () => {
      invalidateCredentials(qc);
    },
  });
}

export function useUpdateCredential() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, { id: string } & CredentialUpdateInput>({
    mutationFn: async ({ id, ...patch }) =>
      api.put<unknown>(`/tenant/credentials/${id}`, patch),
    onSuccess: () => {
      invalidateCredentials(qc);
    },
  });
}

export function useSetDefaultCredential() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, string>({
    mutationFn: async (id) =>
      api.post<unknown>(`/tenant/credentials/${id}/set-default`, {}),
    onSuccess: () => {
      invalidateCredentials(qc);
    },
  });
}

export function useDeleteCredential() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, string>({
    mutationFn: async (id) => api.del<unknown>(`/tenant/credentials/${id}`),
    onSuccess: () => {
      invalidateCredentials(qc);
    },
  });
}
