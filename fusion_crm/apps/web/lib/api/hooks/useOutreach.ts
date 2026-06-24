"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  CampaignInSchema,
  CampaignListSchema,
  CampaignOutSchema,
  RecipientPreviewSchema,
  RenderedEmailSchema,
  SendListSchema,
  SuppressionListSchema,
  TemplateInSchema,
  TemplateListSchema,
  TemplateOutSchema,
  TemplateUpdateSchema,
  type CampaignIn,
  type CampaignList,
  type CampaignOut,
  type RecipientPreview,
  type RenderedEmail,
  type SendList,
  type SuppressionList,
  type TemplateIn,
  type TemplateList,
  type TemplateOut,
  type TemplateUpdate,
} from "@/lib/api/schemas/outreach";

/* -------------------------------------------------------------- templates */

export function useTemplates() {
  return useQuery<TemplateList>({
    queryKey: ["outreach", "templates"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/outreach/templates");
      return TemplateListSchema.parse(raw);
    },
    staleTime: 30_000,
  });
}

export function useTemplate(id: string | null) {
  return useQuery<TemplateOut>({
    queryKey: ["outreach", "template", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const raw = await api.get<unknown>(`/outreach/templates/${id}`);
      return TemplateOutSchema.parse(raw);
    },
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation<TemplateOut, Error, TemplateIn>({
    mutationFn: async (input) => {
      const body = TemplateInSchema.parse(input);
      const raw = await api.post<unknown>("/outreach/templates", body);
      return TemplateOutSchema.parse(raw);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach", "templates"] });
    },
  });
}

export function useUpdateTemplate(id: string) {
  const qc = useQueryClient();
  return useMutation<TemplateOut, Error, TemplateUpdate>({
    mutationFn: async (input) => {
      const body = TemplateUpdateSchema.parse(input);
      const raw = await api.put<unknown>(`/outreach/templates/${id}`, body);
      return TemplateOutSchema.parse(raw);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach", "templates"] });
      qc.invalidateQueries({ queryKey: ["outreach", "template", id] });
    },
  });
}

export function useArchiveTemplate() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await api.del<unknown>(`/outreach/templates/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach", "templates"] });
    },
  });
}

/**
 * Render the template against a sample person — used by the live preview
 * pane in the template editor. The backend wires this up via
 * `TemplateService.render` (ENG-133).
 */
export function useTemplatePreview() {
  return useMutation<RenderedEmail, Error, { id: string }>({
    mutationFn: async ({ id }) => {
      const raw = await api.post<unknown>(
        `/outreach/templates/${id}/preview`,
        {},
      );
      return RenderedEmailSchema.parse(raw);
    },
  });
}

/* -------------------------------------------------------------- campaigns */

export function useCampaigns() {
  return useQuery<CampaignList>({
    queryKey: ["outreach", "campaigns"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/outreach/campaigns");
      return CampaignListSchema.parse(raw);
    },
    staleTime: 15_000,
  });
}

export function useCampaign(id: string | null, opts?: { refetchMs?: number }) {
  return useQuery<CampaignOut>({
    queryKey: ["outreach", "campaign", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const raw = await api.get<unknown>(`/outreach/campaigns/${id}`);
      return CampaignOutSchema.parse(raw);
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Auto-refresh while the dispatcher is working through the queue —
      // ADR-0004 §"Dispatcher" guarantees terminal in seconds, so 5s polling
      // gives the operator near-live counts without hammering the API.
      if (status === "queued" || status === "sending") {
        return opts?.refetchMs ?? 5000;
      }
      return false;
    },
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation<CampaignOut, Error, CampaignIn>({
    mutationFn: async (input) => {
      const body = CampaignInSchema.parse(input);
      const raw = await api.post<unknown>("/outreach/campaigns", body);
      return CampaignOutSchema.parse(raw);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach", "campaigns"] });
    },
  });
}

/** Schedule a draft campaign — POST flips status from draft to queued. */
export function useScheduleCampaign() {
  const qc = useQueryClient();
  return useMutation<CampaignOut, Error, string>({
    mutationFn: async (id) => {
      const raw = await api.post<unknown>(
        `/outreach/campaigns/${id}/schedule`,
        {},
      );
      return CampaignOutSchema.parse(raw);
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach", "campaigns"] });
      qc.invalidateQueries({ queryKey: ["outreach", "campaign", data.id] });
    },
  });
}

export function useCampaignSends(id: string | null) {
  return useQuery<SendList>({
    queryKey: ["outreach", "campaign-sends", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const raw = await api.get<unknown>(`/outreach/campaigns/${id}/sends`);
      return SendListSchema.parse(raw);
    },
    // 5s polling pairs with the campaign-level refetch above so both the
    // counter cards and the per-row send list converge to terminal state.
    refetchInterval: 5000,
  });
}

export function usePreviewRecipients() {
  return useMutation<RecipientPreview, Error, Record<string, unknown>>({
    mutationFn: async (recipientQuery) => {
      const raw = await api.post<unknown>(
        "/outreach/campaigns/preview-recipients",
        recipientQuery,
      );
      return RecipientPreviewSchema.parse(raw);
    },
  });
}

/* -------------------------------------------------------------- suppressions */

export function useSuppressions() {
  return useQuery<SuppressionList>({
    queryKey: ["outreach", "suppressions"],
    queryFn: async () => {
      const raw = await api.get<unknown>("/outreach/suppressions");
      return SuppressionListSchema.parse(raw);
    },
    staleTime: 30_000,
  });
}

export function useRemoveSuppression() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (email) => {
      await api.del<unknown>(
        `/outreach/suppressions/${encodeURIComponent(email)}`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach", "suppressions"] });
    },
  });
}
