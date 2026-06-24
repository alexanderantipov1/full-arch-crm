"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CalendarRange, Megaphone } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { NativeSelect } from "@/components/ui/native-select";
import { useMarketingAnalytics } from "@/lib/api/hooks/useMarketingAnalytics";
import type {
  LeadSourceNode,
  MarketingDailyPoint,
  MarketingKpi,
} from "@/lib/api/schemas";

const PERIOD_PRESETS = [
  { value: "7", label: "Last 7 days", days: 7 },
  { value: "30", label: "Last 30 days", days: 30 },
  { value: "90", label: "Last 90 days", days: 90 },
  { value: "365", label: "Last 12 months", days: 365 },
] as const;

const PROVIDER_LABELS: Record<string, string> = {
  google_ads: "Google Ads",
  meta_ads: "Meta Ads",
  tiktok_ads: "TikTok Ads",
};

// Stable per-provider colours for the trend chart (charts/series are keyed by
// provider, so colours stay consistent as the window changes).
const PROVIDER_COLORS: Record<string, string> = {
  google_ads: "#4285F4",
  meta_ads: "#0866FF",
  tiktok_ads: "#EE1D52",
};

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

function providerColor(provider: string, index: number): string {
  const palette = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
  return PROVIDER_COLORS[provider] ?? palette[index % palette.length]!;
}

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
      return kpi.value.toFixed(2);
    case "integer":
    default:
      return Math.round(kpi.value).toLocaleString("en-US");
  }
}

function formatMoney(amount: number): string {
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

/** Pivot the (day, provider) daily rows into one record per day with a column
 *  per provider, so recharts can stack the providers on a shared X axis. */
function pivotDaily(
  daily: MarketingDailyPoint[],
  providers: string[],
): Array<Record<string, number | string>> {
  const byDay = new Map<string, Record<string, number | string>>();
  for (const point of daily) {
    const row = byDay.get(point.metric_date) ?? { metric_date: point.metric_date };
    row[point.provider] = point.spend;
    byDay.set(point.metric_date, row);
  }
  // Fill missing provider keys with 0 so the stacked areas render continuously.
  return [...byDay.values()]
    .map((row) => {
      for (const provider of providers) {
        if (!(provider in row)) row[provider] = 0;
      }
      return row;
    })
    .sort((a, b) =>
      String(a.metric_date).localeCompare(String(b.metric_date)),
    );
}

function flattenLeadSources(
  nodes: LeadSourceNode[],
  depth = 0,
): Array<{ node: LeadSourceNode; depth: number }> {
  const rows: Array<{ node: LeadSourceNode; depth: number }> = [];
  for (const node of nodes) {
    rows.push({ node, depth });
    if (node.children.length > 0) {
      rows.push(...flattenLeadSources(node.children, depth + 1));
    }
  }
  return rows;
}

export default function MarketingAnalyticsPage() {
  const [period, setPeriod] = useState<string>("30");

  const preset =
    PERIOD_PRESETS.find((p) => p.value === period) ?? PERIOD_PRESETS[1];
  const start_date = useMemo(() => isoDate(preset.days), [preset.days]);

  const query = useMarketingAnalytics({ start_date });

  const providers = useMemo(
    () => (query.data ? query.data.providers.map((p) => p.provider) : []),
    [query.data],
  );
  const dailySeries = useMemo(
    () => (query.data ? pivotDaily(query.data.daily, providers) : []),
    [query.data, providers],
  );
  const leadSourceRows = useMemo(
    () => (query.data ? flattenLeadSources(query.data.lead_sources) : []),
    [query.data],
  );

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Megaphone className="h-6 w-6" />
            Marketing
          </h1>
          <p className="text-sm text-muted-foreground">
            Ad spend, clicks, and lead attribution across connected providers.
            Metrics without a connected source render “—”, never a fake zero.
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
            Failed to load marketing analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {query.isLoading
          ? Array.from({ length: 9 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : query.data?.kpis.map((kpi) => (
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

      {/* Daily spend trend */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Daily spend by provider</CardTitle>
          <CardDescription>
            Stacked spend per day across connected ad providers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : dailySeries.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No spend data for this period.
            </p>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dailySeries}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="metric_date"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                  />
                  <Tooltip
                    formatter={(value, name) => [
                      formatMoney(Number(value)),
                      providerLabel(String(name)),
                    ]}
                  />
                  <Legend formatter={(value) => providerLabel(String(value))} />
                  {providers.map((provider, index) => (
                    <Area
                      key={provider}
                      type="monotone"
                      dataKey={provider}
                      stackId="spend"
                      stroke={providerColor(provider, index)}
                      fill={providerColor(provider, index)}
                      fillOpacity={0.25}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Provider split + detail tabs */}
      <Tabs defaultValue="providers">
        <TabsList>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="lead-sources">Lead attribution</TabsTrigger>
        </TabsList>

        <TabsContent value="providers">
          <Card>
            <CardContent className="pt-6">
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : !query.data || query.data.providers.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No provider connected for this period.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Provider</th>
                      <th className="py-2 pr-2 text-right font-medium">Spend</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Impressions
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">Clicks</th>
                      <th className="py-2 text-right font-medium">Conversions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.providers.map((row) => (
                      <tr
                        key={row.provider}
                        className="border-b border-border/50"
                      >
                        <td className="py-1.5 pr-2 font-medium">
                          {providerLabel(row.provider)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {formatMoney(row.spend)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.impressions.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.clicks.toLocaleString()}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {row.conversions.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="campaigns">
          <Card>
            <CardContent className="pt-6">
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : !query.data || query.data.campaigns.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No campaign spend for this period.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Campaign</th>
                      <th className="py-2 pr-2 font-medium">Provider</th>
                      <th className="py-2 pr-2 text-right font-medium">Spend</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Impressions
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">Clicks</th>
                      <th className="py-2 text-right font-medium">Conversions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.campaigns.map((row) => (
                      <tr
                        key={`${row.provider}:${row.campaign_external_id}`}
                        className="border-b border-border/50"
                      >
                        <td className="py-1.5 pr-2 font-medium">
                          {row.campaign_name ?? (
                            <span className="text-muted-foreground">
                              {row.campaign_external_id}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-2">
                          <Badge variant="outline" className="text-[10px]">
                            {providerLabel(row.provider)}
                          </Badge>
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {formatMoney(row.spend)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.impressions.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.clicks.toLocaleString()}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {row.conversions.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lead-sources">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>
                Leads by raw UTM source › medium › campaign. Channel
                classification is limited to Google / Facebook / Other today;
                richer channels (Dima, Implant Engine, center) are not yet
                configured.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : leadSourceRows.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No leads with UTM attribution for this period.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Source</th>
                      <th className="py-2 pr-2 text-right font-medium">Leads</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Scheduled
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Attended
                      </th>
                      <th className="py-2 text-right font-medium">Collected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leadSourceRows.map(({ node, depth }) => (
                      <tr key={node.key} className="border-b border-border/50">
                        <td className="py-1.5 pr-2">
                          <span
                            className="flex items-center gap-1"
                            style={{ paddingLeft: `${depth * 1.25}rem` }}
                          >
                            <span className="truncate font-medium">
                              {node.label}
                            </span>
                            <Badge
                              variant="outline"
                              className="ml-1 hidden text-[10px] uppercase text-muted-foreground sm:inline-flex"
                            >
                              {node.level}
                            </Badge>
                          </span>
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {node.leads.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {node.consults_scheduled.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {node.consults_attended.toLocaleString()}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {node.collected_amount === 0
                            ? "—"
                            : formatMoney(node.collected_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
