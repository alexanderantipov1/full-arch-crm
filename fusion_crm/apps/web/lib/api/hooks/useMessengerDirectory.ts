"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  MessengerChannelListSchema,
  MessengerTeamListSchema,
  type MessengerChannelList,
  type MessengerTeamList,
} from "@/lib/api/schemas/messenger";

const BASE = "/messenger";
const TEAMS_QUERY_KEY = ["messenger-teams"] as const;
const CHANNELS_QUERY_KEY = ["messenger-channels"] as const;

/**
 * List every Mattermost team the server exposes to us (all teams when an admin
 * token is configured, otherwise only the bot's memberships). Backs the staff
 * Settings → Messenger directory tab. The roster is stable during a shift, so a
 * 60s staleTime avoids refetching on tab revisits; the card's Refresh button
 * invalidates this key to force a live refetch.
 */
export function useMessengerTeams() {
  return useQuery<MessengerTeamList>({
    queryKey: TEAMS_QUERY_KEY,
    queryFn: async () => {
      const raw = await api.get<unknown>(`${BASE}/teams`);
      return MessengerTeamListSchema.parse(raw);
    },
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
}

/**
 * Lazily list one team's channels. Disabled until `teamId` is set, so the
 * request only fires when the operator expands a team row.
 */
export function useMessengerChannels(teamId: string | null) {
  return useQuery<MessengerChannelList>({
    queryKey: [...CHANNELS_QUERY_KEY, teamId],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `${BASE}/teams/${encodeURIComponent(teamId ?? "")}/channels`,
      );
      return MessengerChannelListSchema.parse(raw);
    },
    enabled: teamId !== null,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
}

export { TEAMS_QUERY_KEY, CHANNELS_QUERY_KEY };
