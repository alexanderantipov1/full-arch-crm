"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useRawEvents } from "@/lib/api/hooks/useInspector";
import { cn, formatDateTime } from "@/lib/utils";

interface ServiceStatus {
  status: string;
  last_run_ago?: string | null;
}

interface ServicesHealth {
  status: string;
  services: Record<string, ServiceStatus>;
}

interface SyncLocalSummary {
  total_imported?: number;
  elapsed_seconds?: number;
  caught_up?: boolean;
  deep?: boolean;
  since?: string | null;
  error?: string;
}

// Default deep-backfill lookback: today - 30 days, as a YYYY-MM-DD string for
// the date input. Mirrors run_local_sync's server-side default.
function defaultSinceDate(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

interface SyncLocalState {
  running: boolean;
  last_summary: SyncLocalSummary | null;
  last_finished_at: string | null;
}

function useServicesHealth() {
  return useQuery({
    queryKey: ["health", "services"],
    queryFn: async () => {
      const res = await fetch("/api/health/services");
      if (!res.ok) return null;
      return (await res.json()) as ServicesHealth;
    },
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}

function useSyncLocalState(enabled: boolean) {
  return useQuery({
    queryKey: ["dev", "sync-local"],
    queryFn: async () => {
      const res = await fetch("/api/dev/sync-local");
      if (!res.ok) return null;
      return (await res.json()) as SyncLocalState;
    },
    // Poll every 3s only while a drain is in flight; otherwise idle.
    refetchInterval: enabled ? 3_000 : false,
  });
}

function ServiceDot({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        status === "ok" && "bg-green-500",
        status === "stale" && "bg-yellow-500",
        status === "down" && "bg-red-500",
        status === "degraded" && "bg-yellow-500",
        status === "unknown" && "bg-gray-400",
      )}
    />
  );
}

function ServicesPanel() {
  const { data } = useServicesHealth();
  const { toast } = useToast();
  const [polling, setPolling] = useState(false);
  const [sinceDate, setSinceDate] = useState(defaultSinceDate);
  const { data: syncState } = useSyncLocalState(polling);

  const running = polling || (syncState?.running ?? false);

  // When a tracked drain transitions running -> finished, stop polling
  // (which becomes false and prevents this effect re-firing) and surface
  // the result.
  useEffect(() => {
    if (!polling || !syncState || syncState.running) return;
    setPolling(false);
    const summary = syncState.last_summary;
    if (summary?.error) {
      toast({
        title: "Sync failed",
        description: summary.error,
        variant: "destructive",
      });
    } else if (summary) {
      toast({
        title: summary.deep ? "Deep backfill complete" : "Sync complete",
        description: `${summary.total_imported ?? 0} rows imported in ${
          summary.elapsed_seconds ?? 0
        }s${summary.caught_up === false ? " (hit pass cap)" : ""}`,
        variant: "success",
      });
    }
  }, [polling, syncState, toast]);

  const syncMutation = useMutation({
    mutationFn: async (opts?: { deep: boolean; since?: string }) => {
      const res = await fetch("/api/dev/sync-local", {
        method: "POST",
        ...(opts?.deep
          ? {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ deep: true, since: opts.since }),
            }
          : {}),
      });
      if (!res.ok) throw new Error("Failed to start sync");
      return (await res.json()) as { status: string };
    },
    onSuccess: (result) => {
      setPolling(true);
      if (result.status === "already_running") {
        toast({
          title: "Sync already running",
          description: "A drain is already in progress.",
        });
      }
    },
    onError: () => {
      toast({
        title: "Could not start sync",
        description: "The local-dev sync endpoint did not respond.",
        variant: "destructive",
      });
    },
  });

  const services = [
    { key: "postgres", label: "Postgres" },
    { key: "redis", label: "Redis" },
    { key: "api", label: "API" },
    { key: "web", label: "Web", override: "ok" },
    { key: "worker", label: "Worker" },
  ];

  const busy = running || syncMutation.isPending;

  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex flex-wrap items-center gap-5">
          <span className="text-sm font-medium">Services</span>
          {services.map((svc) => {
            const status =
              svc.override ?? data?.services[svc.key]?.status ?? "unknown";
            const extra = data?.services[svc.key]?.last_run_ago;
            return (
              <div key={svc.key} className="flex items-center gap-1.5">
                <ServiceDot status={status} />
                <span className="text-sm">{svc.label}</span>
                {extra && (
                  <span className="text-xs text-muted-foreground">
                    ({extra})
                  </span>
                )}
              </div>
            );
          })}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => syncMutation.mutate({ deep: false })}
            >
              {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              {busy ? "Syncing…" : "Sync data"}
            </Button>
            <div className="flex items-center gap-1.5">
              <Input
                type="date"
                aria-label="Deep backfill since date"
                value={sinceDate}
                onChange={(e) => setSinceDate(e.target.value)}
                disabled={busy}
                className="h-8 w-[9.5rem] text-sm"
              />
              <Button
                variant="outline"
                size="sm"
                disabled={busy || !sinceDate}
                onClick={() =>
                  syncMutation.mutate({ deep: true, since: sinceDate })
                }
              >
                {busy && (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                )}
                Deep backfill
              </Button>
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Deep backfill re-scans CareStack from the chosen date to refill
          historical holes (e.g. days the worker was asleep). Slower than a
          normal sync — it ignores the freshness watermark and walks the full
          feed.
        </p>
      </CardContent>
    </Card>
  );
}

export default function InspectorPage() {
  const sfQuery = useRawEvents("salesforce");
  const csQuery = useRawEvents("carestack");
  const [selected, setSelected] = useState<{
    provider: "salesforce" | "carestack";
    id: string;
  } | null>(null);

  const selectedEvent =
    selected?.provider === "salesforce"
      ? sfQuery.data?.items.find((e) => e.id === selected.id)
      : selected?.provider === "carestack"
        ? csQuery.data?.items.find((e) => e.id === selected.id)
        : sfQuery.data?.items[0] ?? csQuery.data?.items[0];

  return (
    <div className="space-y-4 p-8">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inspector</h1>
          <p className="text-sm text-muted-foreground">
            Raw payloads from external providers. Local dev only.
          </p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">
              Docs
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Inspector &mdash; Документация</DialogTitle>
            </DialogHeader>
            <InspectorDocs />
          </DialogContent>
        </Dialog>
      </header>

      <ServicesPanel />

      {(sfQuery.error || csQuery.error) && (
        <p className="text-sm text-destructive">Failed to load raw events.</p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Column 1: Salesforce */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <Badge
                variant="outline"
                className="border-blue-500/50 bg-blue-500/10 text-blue-700"
              >
                Salesforce
              </Badge>
              <span className="text-xs text-muted-foreground">
                {sfQuery.data?.total ?? 0} total
              </span>
            </div>
          </CardHeader>
          <CardContent className="max-h-[calc(100vh-340px)] space-y-1.5 overflow-y-auto">
            {sfQuery.isLoading &&
              [...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            {sfQuery.data?.items.length === 0 && !sfQuery.isLoading && (
              <p className="py-8 text-center text-xs text-muted-foreground">
                No Salesforce events yet
              </p>
            )}
            {sfQuery.data?.items.map((e) => (
              <EventRow
                key={e.id}
                event={e}
                active={selected?.id === e.id}
                onClick={() =>
                  setSelected({ provider: "salesforce", id: e.id })
                }
              />
            ))}
          </CardContent>
        </Card>

        {/* Column 2: CareStack */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <Badge
                variant="outline"
                className="border-emerald-500/50 bg-emerald-500/10 text-emerald-700"
              >
                CareStack
              </Badge>
              <span className="text-xs text-muted-foreground">
                {csQuery.data?.total ?? 0} total
              </span>
            </div>
          </CardHeader>
          <CardContent className="max-h-[calc(100vh-340px)] space-y-1.5 overflow-y-auto">
            {csQuery.isLoading &&
              [...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            {csQuery.data?.items.length === 0 && !csQuery.isLoading && (
              <p className="py-8 text-center text-xs text-muted-foreground">
                No CareStack events yet
              </p>
            )}
            {csQuery.data?.items.map((e) => (
              <EventRow
                key={e.id}
                event={e}
                active={selected?.id === e.id}
                onClick={() =>
                  setSelected({ provider: "carestack", id: e.id })
                }
              />
            ))}
          </CardContent>
        </Card>

        {/* Column 3: Payload */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Payload</CardTitle>
            <CardDescription>Verbatim JSON</CardDescription>
          </CardHeader>
          <CardContent>
            {selectedEvent ? (
              <pre className="max-h-[calc(100vh-380px)] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
                {JSON.stringify(selectedEvent.payload, null, 2)}
              </pre>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Select an event to inspect its payload.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function EventRow({
  event,
  active,
  onClick,
}: {
  event: {
    id: string;
    provider: string;
    kind: string;
    external_id: string;
    fetched_at: string;
  };
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-md border bg-card px-3 py-2 text-left transition-colors hover:bg-accent",
        active && "border-primary bg-primary/5",
      )}
    >
      <div className="text-xs text-muted-foreground">{event.kind}</div>
      <div className="mt-0.5 font-mono text-xs">{event.external_id}</div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">
        {formatDateTime(event.fetched_at)}
      </div>
    </button>
  );
}

function InspectorDocs() {
  return (
    <div className="space-y-4 text-sm leading-relaxed">
      <section>
        <h3 className="font-semibold">Что такое Inspector?</h3>
        <p className="mt-1 text-muted-foreground">
          Inspector &mdash; это окно в сырые данные, которые мы вытягиваем из
          двух систем клиники. Каждый раз когда sync обращается к Salesforce
          или CareStack, мы <strong>сначала сохраняем ответ провайдера
          дословно</strong> в таблицу <code>ingest.raw_event</code>, и только
          потом обрабатываем его.
        </p>
      </section>
      <section className="rounded-md border border-yellow-500/30 bg-yellow-500/5 p-3">
        <p className="text-xs text-yellow-600 dark:text-yellow-400">
          Inspector доступен только в локальной dev-среде. Raw payloads могут
          содержать PHI (имена пациентов, контактные данные).
        </p>
      </section>
    </div>
  );
}
