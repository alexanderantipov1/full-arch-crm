"use client";

import { useState } from "react";
import { PhoneCall } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCallerPerformance } from "@/lib/api/hooks/useCallerPerformance";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type CallerGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatRatio,
  NO_DATA_DASH,
} from "../_components/format";

function callerLabel(g: CallerGroup): string {
  return g.caller_id ? `Caller ${g.caller_id.slice(0, 8)}` : "Unassigned";
}

export default function CallerPerformancePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useCallerPerformance(filters);
  const data = query.data;

  const totalLeads = data?.callers.reduce((s, c) => s + c.leads, 0) ?? 0;
  const totalReached = data?.callers.reduce((s, c) => s + c.reached, 0) ?? 0;
  const totalConsults = data?.callers.reduce((s, c) => s + c.consults, 0) ?? 0;
  const totalCollected =
    data?.callers.reduce((s, c) => s + c.collected, 0) ?? 0;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <PhoneCall className="h-6 w-6" />
          Caller performance
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Per-caller lead pipeline: leads assigned, contacts made (first_contact_date),
          consultations booked. Revenue Influenced = Net Collected for caller's
          persons. "Calls Made" is not available — the fact records whether contact
          was made, not call attempts. Cohort anchor: lead_date in window.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load caller performance. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Window totals */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {query.isLoading || !data
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : [
              { label: "Total leads", value: formatCount(totalLeads) },
              { label: "Leads reached", value: formatCount(totalReached) },
              {
                label: "Consultations booked",
                value: formatCount(totalConsults),
              },
              { label: "Revenue influenced", value: formatMoney(totalCollected) },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Per-caller ranking table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Caller ranking</CardTitle>
          <CardDescription>
            Sorted by consultations booked desc, then revenue influenced desc.
            "Calls Made" is always "—" (no dialer count in the data).
            Null caller_id = Unassigned.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : data.callers.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No caller data for this window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Caller</th>
                    <th className="py-2 pr-3 text-right font-medium">Leads</th>
                    <th className="py-2 pr-3 text-right font-medium">Reached</th>
                    <th className="py-2 pr-3 text-right font-medium">Consults</th>
                    <th className="py-2 pr-3 text-right font-medium">Calls Made</th>
                    <th className="py-2 pr-3 text-right font-medium">Lead→Contact</th>
                    <th className="py-2 pr-3 text-right font-medium">Lead→Consult</th>
                    <th className="py-2 pr-3 text-right font-medium">Rev Influenced</th>
                    <th className="py-2 pr-3 text-right font-medium">Rev/Lead</th>
                    <th className="py-2 text-right font-medium">Rev/Consult</th>
                  </tr>
                </thead>
                <tbody>
                  {data.callers.map((g, i) => (
                    <tr
                      key={g.caller_id ?? `unassigned-${i}`}
                      className="border-b border-border/50"
                    >
                      <td className="py-1.5 pr-3 font-medium">
                        {callerLabel(g)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.leads)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.reached)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.consults)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">
                        {NO_DATA_DASH}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.lead_to_contact)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.lead_to_consult)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoney(g.collected)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoneyOrDash(g.revenue_per_lead)}
                      </td>
                      <td className="py-1.5 text-right tabular-nums">
                        {formatMoneyOrDash(g.revenue_per_consult)}
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
