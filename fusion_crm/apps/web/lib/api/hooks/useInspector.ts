"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { RawEventListSchema, RawEventSchema } from "@/lib/api/schemas";

export function useRawEvents(provider?: string) {
  const params = provider ? `?provider=${provider}` : "";
  return useQuery({
    queryKey: ["inspector", "raw-events", provider ?? "all"],
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/ingest/dev/inspector/raw-events${params}`,
      );
      return RawEventListSchema.parse(raw);
    },
  });
}

export function useRawEvent(eventId: string | null | undefined) {
  return useQuery({
    queryKey: ["inspector", "raw-events", "by-id", eventId ?? null],
    enabled: Boolean(eventId),
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/ingest/dev/inspector/raw-events/${eventId}`,
      );
      return RawEventSchema.parse(raw);
    },
  });
}
