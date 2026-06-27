"use client";

import { useMemo, useState } from "react";
import { Megaphone } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarketingPerformance } from "@/lib/api/hooks/useMarketingPerformance";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type MarketingGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatMultiple,
} from "../_components/format";

const DIMENSION_LABELS: Record<string, string> = {
  campaign: "Campaign",
  source: "Source",
  ad_set: "Ad set",
  ad: "Ad",
};

function groupName(g: MarketingGroup): string {
  return g.group_label ?? "Unattributed";
}

export default function MarketingPerformancePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useMarketingPerformance(filters);
  const data = query.data;

  const totals = useMemo(() => {
    if (!data) return [];
    return [
      { label: "Total spend", value: formatMoneyOrDash(data.total_spend) },
      {
        label: "Allocated to leads",
        value: formatMoneyOrDash(data.allocated_spend),
      },
      {
        label: "Spend without leads",
        value: formatMoneyOrDash(data.spend_without_leads),
      },
      { label: "Leads", value: formatCount(data.leads) },
      { label: "Revenue", value: formatMoney(data.revenue_total) },
      { label: "ROI", value: formatMultiple(data.roi) },
    ];
  }, [data]);

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Megaphone className="h-6 w-6" />
          Marketing performance
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Ad spend versus the patient outcomes it produced, broken down by
          campaign and source. Spend is the cost-per-lead allocation (the spend
          tied to leads); ROI is revenue ÷ spend. “Spend without leads” is ad
          spend that produced no attributed leads. Ad set / ad attribution isn’t
          resolved on the journey fact yet, so those tabs show “no data”.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load marketing performance. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Totals */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        {query.isLoading || !data
          ? Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : totals.map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* By-dimension breakdowns */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Spend by dimension</CardTitle>
          <CardDescription>
            Each tab groups the same window by one dimension. Cost-per-stage and
            ROI are “—” when a group has no spend (or no denominator). Counts are
            cohort-anchored on the lead date, so they reconcile with the funnel
            and revenue pages.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <Tabs defaultValue={data.breakdowns[0]?.dimension ?? "campaign"}>
              <TabsList className="flex flex-wrap">
                {data.breakdowns.map((dim) => (
                  <TabsTrigger key={dim.dimension} value={dim.dimension}>
                    {DIMENSION_LABELS[dim.dimension] ?? dim.dimension}
                  </TabsTrigger>
                ))}
              </TabsList>

              {data.breakdowns.map((dim) => (
                <TabsContent key={dim.dimension} value={dim.dimension}>
                  {!dim.resolved ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      {dim.note ??
                        "This dimension isn’t attributed yet — no data to show."}
                    </p>
                  ) : dim.groups.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No marketing activity for this window.
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
                              Spend
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Leads
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Consults
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Shows
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Surgeries
                            </th>
                            <th className="py-2 pr-2 text-right font-medium">
                              Revenue
                            </th>
                            <th className="py-2 text-right font-medium">ROI</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dim.groups.map((g, i) => (
                            <tr
                              key={g.group_id ?? `${dim.dimension}-${i}`}
                              className="border-b border-border/50"
                            >
                              <td className="py-1.5 pr-2 font-medium">
                                {groupName(g)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatMoneyOrDash(g.spend)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatCount(g.leads)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatCount(g.consults)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatCount(g.shows)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatCount(g.surgeries)}
                              </td>
                              <td className="py-1.5 pr-2 text-right tabular-nums">
                                {formatMoney(g.revenue)}
                              </td>
                              <td className="py-1.5 text-right tabular-nums">
                                {formatMultiple(g.roi)}
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
