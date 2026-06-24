import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

const ProviderHealthSchema = z.object({
  status: z.enum(["ok", "stale", "failed", "unknown"]),
  last_status: z.string().nullable(),
  last_run_at: z.string().nullable(),
  records_succeeded: z.number(),
  records_failed: z.number(),
});

const IngestHealthSchema = z.object({
  status: z.enum(["ok", "stale", "failed", "unknown"]),
  providers: z.record(z.string(), ProviderHealthSchema),
});

export type IngestHealth = z.infer<typeof IngestHealthSchema>;

export function useIngestHealth() {
  return useQuery({
    queryKey: ["ingest-health"],
    queryFn: async () => {
      const res = await fetch("/api/health/ingest");
      if (!res.ok) return { status: "unknown" as const, providers: {} };
      const data: unknown = await res.json();
      return IngestHealthSchema.parse(data);
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
