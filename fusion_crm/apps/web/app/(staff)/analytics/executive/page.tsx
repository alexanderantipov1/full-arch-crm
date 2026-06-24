"use client";

import { useState } from "react";
import { LayoutDashboard } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useExecutiveOverview } from "@/lib/api/hooks/useExecutiveOverview";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatMultiple,
  formatRatio,
} from "../_components/format";

export default function ExecutiveOverviewPage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useExecutiveOverview(filters);
  const data = query.data;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <LayoutDashboard className="h-6 w-6" />
          Executive overview
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Owner snapshot over the patient-journey fact: revenue, the full
          patient funnel, marketing efficiency and ROI. Cost / ROI and the later
          funnel stages (treatment accepted, surgeries) render “—” / 0 until the
          B1 enablement data lands — never a fabricated value.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load the executive overview. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Headline money + ROI */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {query.isLoading || !data
          ? Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : [
              {
                label: "Gross revenue",
                value: formatMoney(data.revenue_total),
                sub: "Presented case value (window cohort)",
              },
              {
                label: "Collected",
                value: formatMoney(data.collected_total),
                sub: "Net collected (ENG-283)",
              },
              {
                label: "Outstanding",
                value: formatMoney(data.outstanding_total),
                sub: "Gross − collected",
              },
              {
                label: "Patients",
                value: formatCount(data.patients),
                sub: "Distinct persons in window",
              },
              {
                label: "Marketing spend",
                value: formatMoneyOrDash(data.spend),
                sub: "Connected ad sources",
              },
              {
                label: "ROI",
                value: formatMultiple(data.derived.roi),
                sub: "Revenue ÷ spend",
              },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Realized-cash widgets (Today…YTD), anchored on payment date. */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Revenue</CardTitle>
          <CardDescription>
            Collected cash by the date it was received (independent of the
            filter above). Gross presented value and payer count shown beneath
            each period.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
              {data.revenue_widgets.map((w) => (
                <MetricCard
                  key={w.preset}
                  label={w.label}
                  value={formatMoney(w.collected)}
                  sub={`${formatMoney(w.gross)} gross · ${formatCount(
                    w.payers,
                  )} payers`}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Patient funnel: count / conversion / cost / revenue per stage. */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Patient funnel</CardTitle>
          <CardDescription>
            Counts are persons in the window’s lead cohort reaching each stage.
            Conversion is the share of the previous stage; cost = spend ÷ count
            (“—” until ad spend connects); revenue is collected cash carried by
            persons reaching the stage.
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
                  {data.funnel.map((s) => (
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
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cost-per-stage + conversions from the shared derived layer. */}
      {!query.isLoading && data ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              { label: "Cost / lead", value: data.derived.cost_per_lead },
              { label: "Cost / consult", value: data.derived.cost_per_consult },
              { label: "Cost / show", value: data.derived.cost_per_show },
              { label: "Cost / surgery", value: data.derived.cost_per_surgery },
              {
                label: "Revenue / lead",
                value: data.derived.revenue_per_lead,
              },
            ].map((m) => (
              <MetricCard
                key={m.label}
                label={m.label}
                value={formatMoneyOrDash(m.value)}
              />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              { label: "Lead → contact", value: data.derived.lead_to_contact },
              {
                label: "Contact → consult",
                value: data.derived.contact_to_consult,
              },
              { label: "Consult → show", value: data.derived.consult_to_show },
              {
                label: "Show → surgery",
                value: data.derived.show_to_surgery,
              },
              {
                label: "Surgery → revenue",
                value: data.derived.surgery_to_revenue,
              },
            ].map((m) => (
              <MetricCard
                key={m.label}
                label={m.label}
                value={
                  m.label === "Surgery → revenue"
                    ? formatMoneyOrDash(m.value)
                    : formatRatio(m.value)
                }
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
