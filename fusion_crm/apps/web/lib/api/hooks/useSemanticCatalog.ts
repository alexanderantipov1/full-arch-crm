"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  CatalogDraftPatchInputSchema,
  CatalogDraftPatchSchema,
  CatalogProposalCreateInputSchema,
  CatalogProposalHistorySchema,
  CatalogProposalImpactPreviewSchema,
  CatalogProposalListSchema,
  CatalogProposalReviewInputSchema,
  CatalogProposalReviewResponseSchema,
  CatalogProposalSchema,
  CatalogProposalUpdateInputSchema,
  CatalogVersionHistorySchema,
  type CatalogDraftPatch,
  type CatalogDraftPatchInput,
  type CatalogProposal,
  type CatalogProposalCreateInput,
  type CatalogProposalHistory,
  type CatalogProposalImpactPreview,
  type CatalogProposalReviewInput,
  type CatalogProposalReviewResponse,
  type CatalogProposalStatus,
  type CatalogProposalUpdateInput,
  type CatalogVersionHistory,
} from "@/lib/api/schemas/semanticCatalog";

const catalogProposalsKey = ["semantic-catalog", "proposals"] as const;

function invalidateCatalog(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: catalogProposalsKey });
  qc.invalidateQueries({ queryKey: ["semantic-catalog", "impact-preview"] });
  qc.invalidateQueries({ queryKey: ["semantic-catalog", "history"] });
  qc.invalidateQueries({ queryKey: ["semantic-catalog", "versions"] });
}

export function useCatalogProposals(status?: CatalogProposalStatus) {
  return useQuery({
    queryKey: [...catalogProposalsKey, { status }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (status) {
        params.set("status", status);
      }
      const qs = params.toString();
      const raw = await api.get<unknown>(
        `/semantic/catalog/proposals${qs ? `?${qs}` : ""}`,
      );
      return CatalogProposalListSchema.parse(raw);
    },
    staleTime: 15_000,
  });
}

export function useCreateCatalogProposal() {
  const qc = useQueryClient();
  return useMutation<CatalogProposal, Error, CatalogProposalCreateInput>({
    mutationFn: async (input) => {
      const body = CatalogProposalCreateInputSchema.parse(input);
      const raw = await api.post<unknown>("/semantic/catalog/proposals", body);
      return CatalogProposalSchema.parse(raw);
    },
    onSuccess: () => {
      invalidateCatalog(qc);
    },
  });
}

export function useUpdateCatalogProposal() {
  const qc = useQueryClient();
  return useMutation<
    CatalogProposal,
    Error,
    { id: string; input: CatalogProposalUpdateInput }
  >({
    mutationFn: async ({ id, input }) => {
      const body = CatalogProposalUpdateInputSchema.parse(input);
      const raw = await api.patch<unknown>(
        `/semantic/catalog/proposals/${id}`,
        body,
      );
      return CatalogProposalSchema.parse(raw);
    },
    onSuccess: () => {
      invalidateCatalog(qc);
    },
  });
}

export function useReviewCatalogProposal() {
  const qc = useQueryClient();
  return useMutation<
    CatalogProposalReviewResponse,
    Error,
    { id: string; input: CatalogProposalReviewInput }
  >({
    mutationFn: async ({ id, input }) => {
      const body = CatalogProposalReviewInputSchema.parse(input);
      const raw = await api.post<unknown>(
        `/semantic/catalog/proposals/${id}/review`,
        body,
      );
      return CatalogProposalReviewResponseSchema.parse(raw);
    },
    onSuccess: () => {
      invalidateCatalog(qc);
    },
  });
}

export function useCatalogProposalImpactPreview(id: string | null) {
  return useQuery<CatalogProposalImpactPreview>({
    queryKey: ["semantic-catalog", "impact-preview", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/semantic/catalog/proposals/${id}/impact-preview`,
      );
      return CatalogProposalImpactPreviewSchema.parse(raw);
    },
    staleTime: 15_000,
  });
}

export function useCatalogProposalHistory(id: string | null) {
  return useQuery<CatalogProposalHistory>({
    queryKey: ["semantic-catalog", "history", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/semantic/catalog/proposals/${id}/history`,
      );
      return CatalogProposalHistorySchema.parse(raw);
    },
    staleTime: 15_000,
  });
}

export function useCatalogVersionHistory(term: string | null) {
  return useQuery<CatalogVersionHistory>({
    queryKey: ["semantic-catalog", "versions", term],
    enabled: Boolean(term),
    queryFn: async () => {
      const params = new URLSearchParams({ term: term ?? "" });
      const raw = await api.get<unknown>(
        `/semantic/catalog/versions?${params.toString()}`,
      );
      return CatalogVersionHistorySchema.parse(raw);
    },
    staleTime: 15_000,
  });
}

export function useCatalogDraftPatch() {
  return useMutation<CatalogDraftPatch, Error, CatalogDraftPatchInput>({
    mutationFn: async (input) => {
      const body = CatalogDraftPatchInputSchema.parse(input);
      const raw = await api.post<unknown>("/semantic/catalog/draft-patch", body);
      return CatalogDraftPatchSchema.parse(raw);
    },
  });
}
