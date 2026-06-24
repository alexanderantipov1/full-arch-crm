"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CalendarRange, Info, Search } from "lucide-react";
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
import { useSeoAnalytics } from "@/lib/api/hooks/useSeoAnalytics";
import type {
  FullFunnelNotConfigured,
  MarketingKpi,
  SeoGaDailyPoint,
} from "@/lib/api/schemas";

const PERIOD_PRESETS = [
  { value: "7", label: "Last 7 days", days: 7 },
  { value: "30", label: "Last 30 days", days: 30 },
  { value: "90", label: "Last 90 days", days: 90 },
  { value: "365", label: "Last 12 months", days: 365 },
] as const;

// Stable colours for the GA4 traffic-trend series (keyed by metric).
const GA_SERIES: Array<{ key: keyof SeoGaDailyPoint; label: string; color: string }> = [
  { key: "sessions", label: "Sessions", color: "#6366f1" },
  { key: "total_users", label: "Total users", color: "#10b981" },
  { key: "screen_page_views", label: "Page views", color: "#f59e0b" },
];

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

function NotConnectedCard({ name }: { name: string }) {
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
          Not connected
        </Badge>
      </CardContent>
    </Card>
  );
}

function NotConfiguredCard({ marker }: { marker: FullFunnelNotConfigured }) {
  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base text-muted-foreground">
          <Info className="h-4 w-4" />
          Top pages
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-muted-foreground">{marker.reason}</p>
        <Badge variant="outline" className="text-[10px] uppercase">
          Not connected · {marker.ticket}
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
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {loading
        ? Array.from({ length: 5 }).map((_, i) => (
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

export default function SeoAnalyticsPage() {
  const [period, setPeriod] = useState<string>("30");

  const preset =
    PERIOD_PRESETS.find((p) => p.value === period) ?? PERIOD_PRESETS[1];
  const start_date = useMemo(() => isoDate(preset.days), [preset.days]);

  const query = useSeoAnalytics({ start_date });

  const gaDaily = useMemo(
    () => (query.data ? query.data.ga.daily : []),
    [query.data],
  );
  const gaChannels = useMemo(
    () => (query.data ? query.data.ga.channels : []),
    [query.data],
  );
  const gaTopPages = useMemo(
    () => (query.data ? query.data.ga.top_pages : []),
    [query.data],
  );

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Search className="h-6 w-6" />
            SEO &amp; Web Analytics
          </h1>
          <p className="text-sm text-muted-foreground">
            Organic search (GSC) and web traffic (GA4) from connected sources.
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
            Failed to load SEO analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      <Tabs defaultValue="ga4">
        <TabsList>
          <TabsTrigger value="ga4">GA4</TabsTrigger>
          <TabsTrigger value="gsc">Search Console</TabsTrigger>
          <TabsTrigger value="future">Other sources</TabsTrigger>
        </TabsList>

        {/* GA4 tab — web traffic */}
        <TabsContent value="ga4" className="space-y-6">
          <KpiGrid loading={query.isLoading} kpis={query.data?.ga.kpis} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Daily traffic</CardTitle>
              <CardDescription>
                Sessions, users, and page views per day across GA4 properties.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : gaDaily.length === 0 ? (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  No GA4 data for this period.
                </p>
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={gaDaily}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        className="stroke-muted"
                      />
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
                        tickFormatter={(v) => Number(v).toLocaleString()}
                      />
                      <Tooltip
                        formatter={(value, name) => [
                          Number(value).toLocaleString(),
                          String(name),
                        ]}
                      />
                      <Legend />
                      {GA_SERIES.map((series) => (
                        <Area
                          key={series.key}
                          type="monotone"
                          name={series.label}
                          dataKey={series.key}
                          stroke={series.color}
                          fill={series.color}
                          fillOpacity={0.15}
                        />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Engagement rollup (ENG-478) — "—" when not captured. */}
          <div>
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">
              Engagement
            </h2>
            <KpiGrid
              loading={query.isLoading}
              kpis={query.data?.ga.engagement_kpis}
            />
          </div>

          {/* Acquisition-channel split (ENG-478) — organic / paid / direct. */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Channels</CardTitle>
              <CardDescription>
                Sessions by acquisition channel (organic / paid / direct / …)
                over the window.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : gaChannels.length === 0 ? (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  No channel data for this period.
                </p>
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={gaChannels} layout="vertical">
                      <CartesianGrid
                        strokeDasharray="3 3"
                        className="stroke-muted"
                      />
                      <XAxis
                        type="number"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(v) => Number(v).toLocaleString()}
                      />
                      <YAxis
                        type="category"
                        dataKey="channel"
                        width={120}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        formatter={(value) => [
                          Number(value).toLocaleString(),
                          "Sessions",
                        ]}
                      />
                      <Bar
                        dataKey="sessions"
                        name="Sessions"
                        fill="#6366f1"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Top landing pages (ENG-478). */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Top pages</CardTitle>
              <CardDescription>
                Landing pages by sessions over the window.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : gaTopPages.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No page data for this period.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Page</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Sessions
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">Users</th>
                      <th className="py-2 text-right font-medium">Page views</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gaTopPages.map((row) => (
                      <tr
                        key={row.page_path}
                        className="border-b border-border/50"
                      >
                        <td className="py-1.5 pr-2 font-medium">
                          <span
                            className="block max-w-md truncate"
                            title={row.page_path}
                          >
                            {row.page_path}
                          </span>
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.sessions.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.total_users.toLocaleString()}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {row.screen_page_views.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* GSC tab — organic search */}
        <TabsContent value="gsc" className="space-y-6">
          <KpiGrid loading={query.isLoading} kpis={query.data?.gsc.kpis} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Top queries</CardTitle>
              <CardDescription>
                Search queries by clicks over the window (impression-weighted
                CTR and position).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : !query.data || query.data.gsc.top_queries.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No search-query data for this period.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Query</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Clicks
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Impressions
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">CTR</th>
                      <th className="py-2 text-right font-medium">Position</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.gsc.top_queries.map((row) => (
                      <tr key={row.query} className="border-b border-border/50">
                        <td className="py-1.5 pr-2 font-medium">
                          <span className="block max-w-md truncate" title={row.query}>
                            {row.query}
                          </span>
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.clicks.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.impressions.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.ctr === null
                            ? "—"
                            : `${(row.ctr * 100).toFixed(2)}%`}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {row.position === null ? "—" : row.position.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {query.data ? (
            <NotConfiguredCard marker={query.data.gsc.top_pages} />
          ) : null}
        </TabsContent>

        {/* Future sources — not ingested */}
        <TabsContent value="future">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {(query.data?.not_connected ?? []).map((name) => (
              <NotConnectedCard key={name} name={name} />
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
