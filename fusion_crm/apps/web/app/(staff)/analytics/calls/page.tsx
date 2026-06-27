"use client";

import { useMemo, useState } from "react";
import { CalendarRange, Info, PhoneCall } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { NativeSelect } from "@/components/ui/native-select";
import { useCallsAnalytics } from "@/lib/api/hooks/useCallsAnalytics";
import type { MarketingKpi } from "@/lib/api/schemas";

const PERIOD_PRESETS = [
  { value: "7", label: "Last 7 days", days: 7 },
  { value: "30", label: "Last 30 days", days: 30 },
  { value: "90", label: "Last 90 days", days: 90 },
  { value: "365", label: "Last 12 months", days: 365 },
] as const;

function isoDate(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function formatKpi(kpi: MarketingKpi): string {
  if (kpi.value === null) return "—";
  switch (kpi.format) {
    case "currency":
      return kpi.value.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      });
    case "percent":
      return `${(kpi.value * 100).toFixed(2)}%`;
    case "ratio":
      return kpi.value.toFixed(1);
    case "integer":
    default:
      return Math.round(kpi.value).toLocaleString("en-US");
  }
}

// One legacy call-center section that needs the unbuilt Phase-3 telephony feed.
function PendingCard({ name }: { name: string }) {
  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base text-muted-foreground">
          <Info className="h-4 w-4" />
          {name}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Badge variant="outline" className="text-[10px] uppercase">
          Pending Phase 3 comms ingest
        </Badge>
      </CardContent>
    </Card>
  );
}

function KpiGrid({
  loading,
  kpis,
}: {
  loading: boolean;
  kpis: MarketingKpi[] | undefined;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {loading
        ? Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-2 py-4">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-7 w-24" />
              </CardContent>
            </Card>
          ))
        : kpis?.map((kpi) => (
            <Card key={kpi.key}>
              <CardContent className="space-y-1 py-4">
                <div
                  className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  title={kpi.hint ?? undefined}
                >
                  {kpi.label}
                </div>
                <div className="text-2xl font-semibold tabular-nums">
                  {formatKpi(kpi)}
                </div>
              </CardContent>
            </Card>
          ))}
    </div>
  );
}

export default function CallsAnalyticsPage() {
  const [period, setPeriod] = useState<string>("30");

  const preset =
    PERIOD_PRESETS.find((p) => p.value === period) ?? PERIOD_PRESETS[1];
  const start_date = useMemo(() => isoDate(preset.days), [preset.days]);

  const query = useCallsAnalytics({ start_date });

  const pending = useMemo(
    () => (query.data ? query.data.pending : []),
    [query.data],
  );

  // No call events in the window — show an empty state, never fake numbers.
  const showEmpty = !query.isLoading && query.data?.connected === false;

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <PhoneCall className="h-6 w-6" />
            Calls
          </h1>
          <p className="text-sm text-muted-foreground">
            Call volume from logged activity events. We do not yet ingest a
            telephony feed (RingCentral / CallRail), so disposition, agent
            scorecards, recordings, transcripts, sentiment and QA are pending
            Phase 3 comms ingest. Metrics without a source render “—”, never a
            fake zero.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CalendarRange className="h-4 w-4 text-muted-foreground" />
          <NativeSelect
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            aria-label="Period"
            className="w-44"
          >
            {PERIOD_PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load calls analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {showEmpty ? (
        <Card>
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            No call events for this period yet.
          </CardContent>
        </Card>
      ) : (
        <KpiGrid loading={query.isLoading} kpis={query.data?.kpis} />
      )}

      <div className="space-y-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Pending Phase 3 comms ingest
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {pending.map((name) => (
            <PendingCard key={name} name={name} />
          ))}
        </div>
      </div>
    </div>
  );
}
