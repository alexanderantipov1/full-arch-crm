"use client";

import { useState } from "react";
import { Stethoscope } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDoctorPerformance } from "@/lib/api/hooks/useDoctorPerformance";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type DoctorGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  formatMoneyOrDash,
  formatRatio,
} from "../_components/format";

function doctorLabel(g: DoctorGroup): string {
  return g.doctor_id ? `Doctor ${g.doctor_id.slice(0, 8)}` : "Unassigned";
}

export default function DoctorPerformancePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useDoctorPerformance(filters);
  const data = query.data;

  const totalConsults =
    data?.doctors.reduce((s, d) => s + d.consults, 0) ?? 0;
  const totalAccepted =
    data?.doctors.reduce((s, d) => s + d.treatment_accepted, 0) ?? 0;
  const totalSurgeries =
    data?.doctors.reduce((s, d) => s + d.surgery_completed, 0) ?? 0;
  const totalCollected =
    data?.doctors.reduce((s, d) => s + d.collected, 0) ?? 0;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Stethoscope className="h-6 w-6" />
          Doctor performance
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Per doctor: consultations, treatment plans presented and accepted,
          surgeries completed, and Net Collected revenue. Conversions:
          Consult→Accepted and Accepted→Surgery. Revenue per Consultation /
          Surgery. Cohort anchor: lead_date in window.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load doctor performance. Is the API running?
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
              { label: "Consultations", value: formatCount(totalConsults) },
              { label: "Accepted cases", value: formatCount(totalAccepted) },
              { label: "Surgeries completed", value: formatCount(totalSurgeries) },
              { label: "Revenue collected", value: formatMoney(totalCollected) },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Per-doctor ranking table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Doctor ranking</CardTitle>
          <CardDescription>
            Sorted by surgeries completed desc, then collected desc.
            Null doctor_id = Unassigned (no doctor mapped to the fact row).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : data.doctors.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No doctor data for this window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Doctor</th>
                    <th className="py-2 pr-3 text-right font-medium">Consults</th>
                    <th className="py-2 pr-3 text-right font-medium">Tx Presented</th>
                    <th className="py-2 pr-3 text-right font-medium">Accepted</th>
                    <th className="py-2 pr-3 text-right font-medium">Surgeries</th>
                    <th className="py-2 pr-3 text-right font-medium">Consult→Accepted</th>
                    <th className="py-2 pr-3 text-right font-medium">Accepted→Surgery</th>
                    <th className="py-2 pr-3 text-right font-medium">Collected</th>
                    <th className="py-2 pr-3 text-right font-medium">Rev/Consult</th>
                    <th className="py-2 text-right font-medium">Rev/Surgery</th>
                  </tr>
                </thead>
                <tbody>
                  {data.doctors.map((g, i) => (
                    <tr
                      key={g.doctor_id ?? `unassigned-${i}`}
                      className="border-b border-border/50"
                    >
                      <td className="py-1.5 pr-3 font-medium">
                        {doctorLabel(g)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.consults)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.treatment_presented)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.treatment_accepted)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.surgery_completed)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.consult_to_accepted)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatRatio(g.accepted_to_surgery)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoney(g.collected)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoneyOrDash(g.revenue_per_consult)}
                      </td>
                      <td className="py-1.5 text-right tabular-nums">
                        {formatMoneyOrDash(g.revenue_per_surgery)}
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
