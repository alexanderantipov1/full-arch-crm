"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFunnelStages } from "@/lib/api/hooks/useFunnelStages";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "./AnalyticsFilterBar";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatRatio,
} from "./format";

/**
 * Funnel Analytics (ENG-515) — the nine-point patient funnel over the shared
 * `fact_patient_journey` + global filters. Rendered ABOVE the existing
 * Full-Funnel v2 content on `/analytics/funnel` so v2's numbers do not regress;
 * this is the shared-fact, per-stage count / conversion / cost / revenue view,
 * with the later stages (treatment accepted, surgeries) honestly empty until B1.3.
 */
export function FactFunnelSection() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useFunnelStages(filters);
  const data = query.data;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">
          Patient funnel (shared fact)
        </CardTitle>
        <CardDescription>
          The full Lead → Reached → Consult → Show → Treatment presented →
          Treatment accepted → Surgery scheduled → Surgery completed ladder over
          the patient-journey fact, with the global filter bar (location
          aggregate or per-location). Conversion is the share of the previous
          stage; cost = spend ÷ count (“—” until ad spend connects); revenue is
          collected cash carried by persons reaching the stage. Stages with no
          data yet (treatment accepted, surgeries) show an honest 0.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <AnalyticsFilterBar value={filters} onChange={setFilters} />

        {query.isError ? (
          <p className="py-6 text-center text-sm text-destructive">
            Failed to load the funnel. Is the API running?
          </p>
        ) : query.isLoading || !data ? (
          <Skeleton className="h-56 w-full" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-2 font-medium">Stage</th>
                  <th className="py-2 pr-2 text-right font-medium">Count</th>
                  <th className="py-2 pr-2 text-right font-medium">
                    Conversion
                  </th>
                  <th className="py-2 pr-2 text-right font-medium">Cost</th>
                  <th className="py-2 text-right font-medium">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {data.stages.map((s) => (
                  <tr key={s.key} className="border-b border-border/50">
                    <td className="py-1.5 pr-2 font-medium">{s.label}</td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {formatCount(s.count)}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums text-emerald-600 dark:text-emerald-500">
                      {formatRatio(s.conversion)}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums text-amber-600 dark:text-amber-500">
                      {formatMoneyOrDash(s.cost)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      {formatMoney(s.revenue)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="pt-3 text-xs text-muted-foreground">
              {formatCount(data.patients)} persons in window ·{" "}
              {formatMoney(data.revenue_total)} gross ·{" "}
              {formatMoney(data.collected_total)} collected · spend{" "}
              {formatMoneyOrDash(data.spend)}. The Full-Funnel v2 report below is
              unchanged (Salesforce + CareStack person-anchored truth).
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
