"use client";

import { useState } from "react";
import { GitMerge } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAttributionAnalytics } from "@/lib/api/hooks/useAttributionAnalytics";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type AttributionDimension,
  type AttributionRevenueGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  NO_DATA_DASH,
} from "../_components/format";

const DIMENSION_LABELS: Record<string, string> = {
  campaign: "Campaign",
  vendor: "Vendor",
  caller: "Caller",
  coordinator: "Coordinator",
  doctor: "Doctor",
};

function groupLabel(g: AttributionRevenueGroup, dimension: string): string {
  if (dimension === "campaign" || dimension === "source") {
    return g.group_label ?? "Unassigned";
  }
  // UUID-keyed people dimensions: short prefix or Unassigned
  if (g.group_id) {
    return `${DIMENSION_LABELS[dimension] ?? dimension} ${g.group_id.slice(0, 8)}`;
  }
  return "Unassigned";
}

function DimensionTable({
  dim,
}: {
  dim: AttributionDimension;
}) {
  if (!dim.resolved) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-300">
        <span className="font-semibold">No data.</span>{" "}
        {dim.note ?? "This dimension is not yet attributed on the analytics fact."}
      </div>
    );
  }

  if (dim.groups.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No attribution data for this dimension in the selected window.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-3 font-medium">
              {DIMENSION_LABELS[dim.dimension] ?? dim.dimension}
            </th>
            <th className="py-2 pr-3 text-right font-medium">Cases</th>
            <th className="py-2 pr-3 text-right font-medium">Gross</th>
            <th className="py-2 pr-3 text-right font-medium">Collected</th>
            <th className="py-2 pr-3 text-right font-medium">Outstanding</th>
            <th className="py-2 text-right font-medium">Avg Case Value</th>
          </tr>
        </thead>
        <tbody>
          {dim.groups.map((g, i) => (
            <tr
              key={g.group_id ?? `row-${i}`}
              className="border-b border-border/50"
            >
              <td className="py-1.5 pr-3 font-medium">
                {groupLabel(g, dim.dimension)}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {formatCount(g.case_count)}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {formatMoney(g.gross)}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {formatMoney(g.collected)}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {formatMoney(g.outstanding)}
              </td>
              <td className="py-1.5 text-right tabular-nums">
                {formatMoneyOrDash(g.avg_case_value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AttributionAnalyticsPage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useAttributionAnalytics(filters);
  const data = query.data;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <GitMerge className="h-6 w-6" />
          Attribution analytics
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Revenue attribution by dimension: campaign, vendor, caller, coordinator,
          doctor. Collected revenue + case counts per group. Campaign has full
          data; caller/coordinator/doctor have partial coverage (null =
          Unassigned); vendor is not yet attributed on the fact (ENG-569).
          Cohort anchor: lead_date in window.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load attribution analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Window totals */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-2">
        {query.isLoading || !data
          ? Array.from({ length: 2 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : [
              {
                label: "Collected (cohort)",
                value: formatMoney(data.collected_total),
              },
              {
                label: "Cases",
                value: formatCount(data.case_count),
              },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Per-dimension tabs */}
      {query.isLoading || !data ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Revenue by dimension</CardTitle>
            <CardDescription>
              Each tab shows collected revenue + cases per group. Vendor tab
              shows no data today (not yet wired to the fact). NULL actor ids
              appear as Unassigned.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue={data.dimensions[0]?.dimension ?? "campaign"}>
              <TabsList className="mb-4">
                {data.dimensions.map((dim) => (
                  <TabsTrigger key={dim.dimension} value={dim.dimension}>
                    {DIMENSION_LABELS[dim.dimension] ?? dim.dimension}
                    {!dim.resolved && (
                      <span className="ml-1 text-xs text-amber-600">
                        (no data)
                      </span>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
              {data.dimensions.map((dim) => (
                <TabsContent key={dim.dimension} value={dim.dimension}>
                  <DimensionTable dim={dim} />
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
