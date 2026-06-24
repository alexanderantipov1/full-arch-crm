"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  ClaimSuggestionsSchema,
  UnassignedSignaturesSchema,
  VendorClaimListSchema,
  VendorClaimSchema,
  VendorCostListSchema,
  VendorCostSchema,
  VendorListSchema,
  VendorSchema,
  type ClaimSuggestions,
  type UnassignedSignatures,
  type Vendor,
  type VendorClaim,
  type VendorClaimInput,
  type VendorCost,
  type VendorCostInput,
  type VendorCreate,
  type VendorUpdate,
} from "@/lib/api/schemas/vendor";

/**
 * ENG-570 — vendor CRUD hooks. A vendor is the configured "who" behind the
 * traffic (agency or the in-house team). Mutations invalidate the list so the
 * settings table refetches.
 */

const KEY = ["attribution", "vendors"] as const;

export function useVendors(activeOnly = false) {
  return useQuery<Vendor[]>({
    queryKey: [...KEY, { activeOnly }],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/vendors${activeOnly ? "?active_only=true" : ""}`,
      );
      return VendorListSchema.parse(raw);
    },
  });
}

export function useCreateVendor() {
  const qc = useQueryClient();
  return useMutation<Vendor, Error, VendorCreate>({
    mutationFn: async (payload) => {
      const raw = await api.post<unknown>("/attribution/vendors", payload);
      return VendorSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useUpdateVendor() {
  const qc = useQueryClient();
  return useMutation<Vendor, Error, { id: string; patch: VendorUpdate }>({
    mutationFn: async ({ id, patch }) => {
      const raw = await api.patch<unknown>(
        `/attribution/vendors/${id}`,
        patch,
      );
      return VendorSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeactivateVendor() {
  const qc = useQueryClient();
  return useMutation<{ deactivated: boolean }, Error, string>({
    mutationFn: async (id) => {
      return await api.del<{ deactivated: boolean }>(
        `/attribution/vendors/${id}`,
      );
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

// --- per-month costs (ENG-573) ---

const costsKey = (vendorId: string) =>
  ["attribution", "vendors", vendorId, "costs"] as const;

export function useVendorCosts(vendorId: string | null) {
  return useQuery<VendorCost[]>({
    queryKey: vendorId ? costsKey(vendorId) : ["attribution", "vendors", "costs", "none"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/vendors/${vendorId}/costs`,
      );
      return VendorCostListSchema.parse(raw);
    },
    enabled: vendorId !== null,
  });
}

export function useSetVendorCost(vendorId: string) {
  const qc = useQueryClient();
  return useMutation<VendorCost, Error, VendorCostInput>({
    mutationFn: async (payload) => {
      const raw = await api.put<unknown>(
        `/attribution/vendors/${vendorId}/costs`,
        payload,
      );
      return VendorCostSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: costsKey(vendorId) });
    },
  });
}

export function useDeleteVendorCost(vendorId: string) {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, string>({
    mutationFn: async (periodMonth) => {
      return await api.del<{ deleted: boolean }>(
        `/attribution/vendors/${vendorId}/costs/${periodMonth}`,
      );
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: costsKey(vendorId) });
    },
  });
}

// --- claims + unassigned signatures (ENG-571) ---

const claimsKey = (vendorId: string) =>
  ["attribution", "vendors", vendorId, "claims"] as const;
const SIGNATURES_KEY = ["attribution", "unassigned-signatures"] as const;

export function useVendorClaims(vendorId: string | null) {
  return useQuery<VendorClaim[]>({
    queryKey: vendorId ? claimsKey(vendorId) : [...SIGNATURES_KEY, "none"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/vendors/${vendorId}/claims`,
      );
      return VendorClaimListSchema.parse(raw);
    },
    enabled: vendorId !== null,
  });
}

export function useVendorClaimSuggestions(
  vendorId: string | null,
  enabled: boolean,
) {
  return useQuery<ClaimSuggestions>({
    queryKey: ["attribution", "vendors", vendorId, "claim-suggestions"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/attribution/vendors/${vendorId}/claim-suggestions?lead_limit=2000`,
      );
      // The endpoint returns null for a missing vendor (mirrors create-claim).
      return raw === null
        ? { items: [], scanned: 0, capped: false }
        : ClaimSuggestionsSchema.parse(raw);
    },
    enabled: enabled && vendorId !== null,
    staleTime: 60_000,
  });
}

export function useUnassignedSignatures(enabled: boolean) {
  return useQuery<UnassignedSignatures>({
    queryKey: SIGNATURES_KEY,
    queryFn: async () => {
      const raw = await api.get<unknown>(
        "/attribution/unassigned-signatures?lead_limit=2000",
      );
      return UnassignedSignaturesSchema.parse(raw);
    },
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateVendorClaim(vendorId: string) {
  const qc = useQueryClient();
  return useMutation<VendorClaim | null, Error, VendorClaimInput>({
    mutationFn: async (payload) => {
      const raw = await api.post<unknown>(
        `/attribution/vendors/${vendorId}/claims`,
        payload,
      );
      return raw === null ? null : VendorClaimSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: claimsKey(vendorId) });
      // a new claim re-resolves matching leads → the Unassigned set + tree shift
      void qc.invalidateQueries({ queryKey: SIGNATURES_KEY });
      void qc.invalidateQueries({ queryKey: ["attribution", "tree"] });
    },
  });
}

export function useDeleteVendorClaim(vendorId: string) {
  const qc = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, string>({
    mutationFn: async (claimId) => {
      return await api.del<{ deleted: boolean }>(
        `/attribution/vendors/${vendorId}/claims/${claimId}`,
      );
    },
    onSuccess: () => {
      // Symmetric with create: the binding is gone, so the signature picker and
      // the tree/Unassigned views may shift (after the next resolve pass).
      void qc.invalidateQueries({ queryKey: claimsKey(vendorId) });
      void qc.invalidateQueries({ queryKey: SIGNATURES_KEY });
      void qc.invalidateQueries({ queryKey: ["attribution", "tree"] });
    },
  });
}
