"use client";

import { useState } from "react";
import { Grid2x2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCohortAnalytics } from "@/lib/api/hooks/useCohortAnalytics";
import {
  type AnalyticsFilterValue,
  type CohortRevenue,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { formatCount, formatMoney } from "../_components/format";

// Cohorts span multiple lead-creation months, so default to a year window.
const COHORT_DEFAULT_FILTERS: AnalyticsFilterValue = {
  time_range: "this_year",
  location_id: null,
};

const HORIZON_KEYS: { key: keyof CohortRevenue; label: string }[] = [
  { key: "d30", label: "30d" },
  { key: "d60", label: "60d" },
  { key: "d90", label: "90d" },
  { key: "d180", label: "180d" },
  { key: "d365", label: "365d" },
];

export default function CohortAnalyticsPage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    COHORT_DEFAULT_FILTERS,
  );
  const query = useCohortAnalytics(filters);
  const data = query.data;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Grid2x2 className="h-6 w-6" />
          Cohort analytics
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Long-term lead value. Each row is a lead-creation month; each cell is
          cumulative collected revenue from persons who paid within N days of
          their lead date. Person-anchored dating means bulk-import patients
          don’t create a false spike — a cohort with no real payment lag simply
          shows no early revenue.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load cohort analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Revenue by cohort age
          </CardTitle>
          <CardDescription>
            Cumulative collected revenue at each horizon (days after the lead was
            created). Reads left-to-right as a cohort matures.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : data.cohorts.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No cohorts for this window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-2 font-medium">Cohort month</th>
                    <th className="py-2 pr-2 text-right font-medium">Leads</th>
                    {HORIZON_KEYS.map((h) => (
                      <th
                        key={h.key}
                        className="py-2 pr-2 text-right font-medium"
                      >
                        {h.label}
                      </th>
                    ))}
                    <th className="py-2 text-right font-medium">
                      Collected (all-time)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.cohorts.map((c) => (
                    <tr
                      key={c.cohort_month}
                      className="border-b border-border/50"
                    >
                      <td className="py-1.5 pr-2 font-medium tabular-nums">
                        {c.cohort_month}
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        {formatCount(c.lead_count)}
                      </td>
                      {HORIZON_KEYS.map((h) => (
                        <td
                          key={h.key}
                          className="py-1.5 pr-2 text-right tabular-nums"
                        >
                          {formatMoney(c.revenue[h.key])}
                        </td>
                      ))}
                      <td className="py-1.5 text-right tabular-nums font-medium">
                        {formatMoney(c.collected_total)}
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
