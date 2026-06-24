"use client";

import { useState } from "react";
import { Users } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoordinatorPerformance } from "@/lib/api/hooks/useCoordinatorPerformance";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type CoordinatorGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatRatio,
} from "../_components/format";

function coordinatorLabel(g: CoordinatorGroup): string {
  return g.coordinator_id
    ? `Coordinator ${g.coordinator_id.slice(0, 8)}`
    : "Unassigned";
}

export default function CoordinatorPerformancePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useCoordinatorPerformance(filters);
  const data = query.data;

  const totalConsults =
    data?.coordinators.reduce((s, c) => s + c.consults_assigned, 0) ?? 0;
  const totalShows =
    data?.coordinators.reduce((s, c) => s + c.shows, 0) ?? 0;
  const totalSurgeries =
    data?.coordinators.reduce((s, c) => s + c.surgery_completed, 0) ?? 0;
  const totalCollected =
    data?.coordinators.reduce((s, c) => s + c.collected, 0) ?? 0;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Users className="h-6 w-6" />
          Coordinator performance
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Per treatment coordinator: consultations assigned, shows, treatment plans
          presented, surgeries scheduled and completed, and revenue collected.
          Cohort anchor: lead_date in window, so counts reconcile with the funnel
          and revenue pages.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load coordinator performance. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Window totals */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {query.isLoading || !data
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : [
              { label: "Consultations assigned", value: formatCount(totalConsults) },
              { label: "Shows", value: formatCount(totalShows) },
              { label: "Surgeries completed", value: formatCount(totalSurgeries) },
              { label: "Revenue collected", value: formatMoney(totalCollected) },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Per-coordinator ranking table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Coordinator ranking</CardTitle>
          <CardDescription>
            Sorted by consultations assigned desc, then collected desc.
            Null coordinator_id = Unassigned (no coordinator mapped).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : data.coordinators.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No coordinator data for this window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Coordinator</th>
                    <th className="py-2 pr-3 text-right font-medium">Consults</th>
                    <th className="py-2 pr-3 text-right font-medium">Shows</th>
                    <th className="py-2 pr-3 text-right font-medium">Tx Presented</th>
                    <th className="py-2 pr-3 text-right font-medium">Surg Sched</th>
                    <th className="py-2 pr-3 text-right font-medium">Surg Done</th>
                    <th className="py-2 pr-3 text-right font-medium">Sched→Show</th>
                    <th className="py-2 pr-3 text-right font-medium">Show→Surgery</th>
                    <th className="py-2 pr-3 text-right font-medium">Collected</th>
                    <th className="py-2 text-right font-medium">Rev/Consult</th>
                  </tr>
                </thead>
                <tbody>
                  {data.coordinators.map((g, i) => (
                    <tr
                      key={g.coordinator_id ?? `unassigned-${i}`}
                      className="border-b border-border/50"
                    >
                      <td className="py-1.5 pr-3 font-medium">
                        {coordinatorLabel(g)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.consults_assigned)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.shows)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.treatment_presented)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.surgery_scheduled)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.surgery_completed)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.scheduled_to_show)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.show_to_surgery)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoney(g.collected)}
                      </td>
                      <td className="py-1.5 text-right tabular-nums">
                        {formatMoneyOrDash(g.revenue_per_consult)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
