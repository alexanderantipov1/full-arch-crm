"use client";

import { useMemo, useState } from "react";
import { DollarSign } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useRevenueIntelligence } from "@/lib/api/hooks/useRevenueIntelligence";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type RevenueDimension,
  type RevenueGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
} from "../_components/format";

const DIMENSION_LABELS: Record<string, string> = {
  campaign: "Campaign",
  source: "Source",
  vendor: "Vendor",
  caller: "Caller",
  coordinator: "Coordinator",
  doctor: "Doctor",
  location: "Location",
};

export default function RevenueIntelligencePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useRevenueIntelligence(filters);
  const data = query.data;

  const tenant = useCurrentTenant();
  const locationNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const loc of tenant.data?.locations ?? []) {
      map.set(loc.id, loc.short_name || loc.name);
    }
    return map;
  }, [tenant.data]);

  function groupName(dim: RevenueDimension, g: RevenueGroup): string {
    if (g.group_label) return g.group_label;
    if (dim.dimension === "location" && g.group_id) {
      return locationNames.get(g.group_id) ?? `Location ${g.group_id.slice(0, 8)}`;
    }
    return "Unattributed";
  }

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <DollarSign className="h-6 w-6" />
          Revenue intelligence
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Where revenue comes from, broken down by campaign, source, location and
          the people dimensions. Gross is presented case value; collected is Net
          Collected (ENG-283); outstanding is gross − collected. Dimensions the
          data can’t attribute yet (vendor, caller, coordinator, doctor) collapse
          to a single “Unattributed” bucket until B1.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load revenue intelligence. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Totals */}
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
              { label: "Gross revenue", value: formatMoney(data.gross_total) },
              { label: "Collected", value: formatMoney(data.collected_total) },
              {
                label: "Outstanding",
                value: formatMoney(data.outstanding_total),
              },
              { label: "Cases", value: formatCount(data.case_count) },
              {
                label: "Avg case value",
                value: formatMoneyOrDash(data.avg_case_value),
              },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* By-dimension breakdowns */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Revenue by dimension</CardTitle>
          <CardDescription>
            Each tab groups the same window’s revenue by one dimension. Average
            case value is gross ÷ cases (“—” when a group has no cases).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <Tabs defaultValue={data.dimensions[0]?.dimension ?? "campaign"}>
              <TabsList className="flex flex-wrap">
                {data.dimensions.map((dim) => (
                  <TabsTrigger key={dim.dimension} value={dim.dimension}>
                    {DIMENSION_LABELS[dim.dimension] ?? dim.dimension}
                  </TabsTrigger>
                ))}
              </TabsList>

              {data.dimensions.map((dim) => (
                <TabsContent key={dim.dimension} value={dim.dimension}>
                  {!dim.resolved ? (
                    <p className="pb-2 text-xs text-muted-foreground">
                      This dimension isn’t attributed yet — every case shows as
                      “Unattributed” until B1 enablement resolves it.
                    </p>
                  ) : null}
                  {dim.groups.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No revenue for this window.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                            <th className="py-2 pr-2 font-medium">
                              {DIMENSION_LABELS[dim.dimension] ?? dim.dimension}
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Gross
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Collected
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Outstanding
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Cases
                            </th>
                            <th className="py-2 text-right font-medium">
                              Avg case
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {dim.groups.map((g, i) => (
                            <tr
                              key={g.group_id ?? `${dim.dimension}-${i}`}
                              className="border-b border-border/50"
                            >
                              <td className="py-1.5 pr-2 font-medium">
                                {groupName(dim, g)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatMoney(g.gross)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatMoney(g.collected)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatMoney(g.outstanding)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatCount(g.case_count)}
                              </td>
                              <td className="py-1.5 text-right tabular-nums">
                                {formatMoneyOrDash(g.avg_case_value)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </TabsContent>
              ))}
            </Tabs>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
