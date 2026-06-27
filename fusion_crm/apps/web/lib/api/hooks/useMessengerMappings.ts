"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  ProviderMessengerMappingListSchema,
  ProviderMessengerMappingSchema,
  type ProviderMessengerMapping,
  type ProviderMessengerMappingList,
} from "@/lib/api/schemas/messengerMappings";

const BASE = "/actor/provider-messenger-mappings";
const QUERY_KEY = ["provider-messenger-mappings"] as const;

/**
 * List every CareStack provider (doctor) + its current Mattermost username.
 * Backs the Messenger-settings card (ENG-546). Mapping config is stable, so a
 * 60s staleTime keeps page revisits during a shift from refetching.
 */
export function useProviderMessengerMappings() {
  return useQuery<ProviderMessengerMappingList>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const raw = await api.get<unknown>(BASE);
      return ProviderMessengerMappingListSchema.parse(raw);
    },
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
}

/**
 * Map one provider (doctor) → Mattermost username. The backend strips a
 * leading `@` and keeps exactly one username per doctor. Invalidates the list
 * on success so the card reflects the new handle without a manual reload.
 */
export function useSetProviderMessengerUsername() {
  const qc = useQueryClient();
  return useMutation<
    ProviderMessengerMapping,
    Error,
    { carestackProviderId: string; mattermostUsername: string }
  >({
    mutationFn: async ({ carestackProviderId, mattermostUsername }) => {
      const raw = await api.put<unknown>(
        `${BASE}/${encodeURIComponent(carestackProviderId)}`,
        { mattermost_username: mattermostUsername },
      );
      return ProviderMessengerMappingSchema.parse(raw);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}
