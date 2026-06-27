"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Info, TrendingUp } from "lucide-react";
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
import { useSalesAnalytics } from "@/lib/api/hooks/useSalesAnalytics";
import type {
  FullFunnelNotConfigured,
  MarketingKpi,
  SalesConsultation,
} from "@/lib/api/schemas";

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
      return `${(kpi.value * 100).toFixed(1)}%`;
    case "ratio":
      return kpi.value.toFixed(1);
    case "integer":
    default:
      return Math.round(kpi.value).toLocaleString("en-US");
  }
}

function money(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function percent(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function consultDate(row: SalesConsultation): string {
  return new Date(row.scheduled_at).toLocaleDateString("en-US");
}

function NotConfiguredCard({ marker }: { marker: FullFunnelNotConfigured }) {
  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base text-muted-foreground">
          <Info className="h-4 w-4" />
          Patient follow-up breakdown
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

export default function SalesAnalyticsPage() {
  const query = useSalesAnalytics();

  const stageData = useMemo(
    () => (query.data ? query.data.pipeline_by_stage : []),
    [query.data],
  );

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <TrendingUp className="h-6 w-6" />
          Sales Pipeline
        </h1>
        <p className="text-sm text-muted-foreground">
          Pipeline value, close rate, treatment-coordinator leaderboard, and
          consultations from opportunities. Won/closed read the opportunity
          flags; ratios with no closed deals render “—”, never a fake zero.
        </p>
      </div>

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load sales analytics. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      <KpiGrid loading={query.isLoading} kpis={query.data?.kpis} />

      <Tabs defaultValue="pipeline">
        <TabsList>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="coordinators">Coordinators</TabsTrigger>
          <TabsTrigger value="consultations">Consultations</TabsTrigger>
        </TabsList>

        {/* Pipeline by stage */}
        <TabsContent value="pipeline" className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Pipeline by stage</CardTitle>
              <CardDescription>
                Opportunity value grouped by stage (raw stage strings).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : stageData.length === 0 ? (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  No opportunities yet.
                </p>
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stageData} layout="vertical">
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
                        dataKey="stage"
                        width={150}
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        formatter={(value, name) => [
                          name === "value"
                            ? money(Number(value))
                            : Number(value).toLocaleString(),
                          name === "value" ? "Value" : "Count",
                        ]}
                      />
                      <Bar
                        dataKey="value"
                        fill="#6366f1"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {query.data ? (
            <NotConfiguredCard marker={query.data.followups} />
          ) : null}
        </TabsContent>

        {/* TC leaderboard */}
        <TabsContent value="coordinators" className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                Treatment-coordinator leaderboard
              </CardTitle>
              <CardDescription>
                Opportunities grouped by owner. Collected is net cash of the
                persons behind each coordinator’s opportunities.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : !query.data || query.data.tc_leaderboard.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No coordinators yet.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Coordinator</th>
                      <th className="py-2 pr-2 text-right font-medium">Opps</th>
                      <th className="py-2 pr-2 text-right font-medium">Won</th>
                      <th className="py-2 pr-2 text-right font-medium">Lost</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Close rate
                      </th>
                      <th className="py-2 pr-2 text-right font-medium">Value</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Won revenue
                      </th>
                      <th className="py-2 text-right font-medium">Collected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.tc_leaderboard.map((row) => (
                      <tr key={row.tc} className="border-b border-border/50">
                        <td className="py-1.5 pr-2 font-medium">{row.tc}</td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.opps.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.won.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {row.lost.toLocaleString()}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {percent(row.close_rate)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {money(row.value)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {money(row.won_revenue)}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {money(row.collected)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Consultations table */}
        <TabsContent value="consultations" className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Consultations</CardTitle>
              <CardDescription>
                Recent consultations with their covering opportunity (TC, stage,
                value, paid, balance).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : !query.data || query.data.consultations.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No consultations yet.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-2 font-medium">Patient</th>
                      <th className="py-2 pr-2 font-medium">Coordinator</th>
                      <th className="py-2 pr-2 font-medium">Status</th>
                      <th className="py-2 pr-2 font-medium">Stage</th>
                      <th className="py-2 pr-2 text-right font-medium">Value</th>
                      <th className="py-2 pr-2 text-right font-medium">Paid</th>
                      <th className="py-2 pr-2 text-right font-medium">
                        Balance
                      </th>
                      <th className="py-2 text-right font-medium">Scheduled</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.consultations.map((row) => (
                      <tr
                        key={row.consultation_id}
                        className="border-b border-border/50"
                      >
                        <td className="py-1.5 pr-2 font-medium">
                          {row.patient ?? "—"}
                        </td>
                        <td className="py-1.5 pr-2">{row.tc ?? "—"}</td>
                        <td className="py-1.5 pr-2">
                          <Badge variant="outline" className="text-[10px]">
                            {row.status}
                          </Badge>
                        </td>
                        <td className="py-1.5 pr-2">{row.stage ?? "—"}</td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {money(row.opp_value)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {money(row.paid)}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">
                          {money(row.balance)}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {consultDate(row)}
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
