"use client";

import { useState } from "react";
import { DollarSign, Info } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCostIntelligence } from "@/lib/api/hooks/useCostIntelligence";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type CostMetric,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  NO_DATA_DASH,
} from "../_components/format";

/** Render one cost metric row: label / value / note. */
function CostRow({ metric }: { metric: CostMetric }) {
  return (
    <tr className="border-b border-border/50">
      <td className="py-2 pr-4 font-medium">{metric.label}</td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {metric.value !== null ? formatMoneyOrDash(metric.value) : NO_DATA_DASH}
      </td>
      <td className="py-2 text-sm text-muted-foreground">
        {metric.note ? (
          <span className="flex items-center gap-1">
            <Info className="h-3 w-3 shrink-0" />
            {metric.note}
          </span>
        ) : null}
      </td>
    </tr>
  );
}

export default function CostIntelligencePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useCostIntelligence(filters);
  const data = query.data;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <DollarSign className="h-6 w-6" />
          Cost intelligence
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Marketing cost per funnel stage. Spend = ground-truth window ad spend
          from the connected marketing data source (same source as the Marketing
          Performance page). All metrics are "—" until a spend source is connected.
          Operational cost metrics (per-caller, per-coordinator) require staff cost
          inputs not yet captured — shown as "—" with an explanation.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load cost intelligence. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Window funnel summary */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {query.isLoading || !data
          ? Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : [
              { label: "Leads", value: formatCount(data.leads) },
              { label: "Consults", value: formatCount(data.consults) },
              { label: "Shows", value: formatCount(data.shows) },
              { label: "Surgeries", value: formatCount(data.surgeries) },
              {
                label: "Total spend",
                value: data.spend !== null ? formatMoney(data.spend) : NO_DATA_DASH,
              },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Marketing cost metrics */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Marketing cost metrics</CardTitle>
          <CardDescription>
            Computed from window ad spend ÷ cohort stage count. All null when no
            spend source is connected. Cohort anchor: lead_date in window.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Metric</th>
                    <th className="py-2 pr-4 text-right font-medium">Value</th>
                    <th className="py-2 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  <CostRow metric={data.cost_per_lead} />
                  <CostRow metric={data.cost_per_consult} />
                  <CostRow metric={data.cost_per_show} />
                  <CostRow metric={data.cost_per_surgery} />
                  <CostRow metric={data.cost_per_revenue_dollar} />
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Operational cost metrics — honest no-data */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Operational cost metrics</CardTitle>
          <CardDescription>
            These metrics require staff operational cost inputs (salary / cost-per-hour)
            that are not yet captured in the system. They will become available once
            operational cost data is connected.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Metric</th>
                    <th className="py-2 pr-4 text-right font-medium">Value</th>
                    <th className="py-2 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  <CostRow metric={data.cost_per_caller_conversion} />
                  <CostRow metric={data.cost_per_coordinator_conversion} />
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
