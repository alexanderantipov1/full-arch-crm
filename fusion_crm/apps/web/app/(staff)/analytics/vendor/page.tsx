"use client";

import { useState } from "react";
import { Store } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useVendorPerformance } from "@/lib/api/hooks/useVendorPerformance";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type VendorGroup,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { MetricCard } from "../_components/MetricCard";
import {
  formatCount,
  formatMoney,
  NO_DATA_DASH,
} from "../_components/format";

function vendorLabel(g: VendorGroup): string {
  return g.vendor_id ? `Vendor ${g.vendor_id.slice(0, 8)}` : "Unassigned";
}

export default function VendorPerformancePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useVendorPerformance(filters);
  const data = query.data;

  const totalLeads = data?.vendors.reduce((s, v) => s + v.leads, 0) ?? 0;
  const totalConsults = data?.vendors.reduce((s, v) => s + v.consults, 0) ?? 0;
  const totalSurgeries =
    data?.vendors.reduce((s, v) => s + v.surgeries, 0) ?? 0;
  const totalCollected =
    data?.vendors.reduce((s, v) => s + v.collected, 0) ?? 0;

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Store className="h-6 w-6" />
          Vendor performance
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Per-vendor lead pipeline: leads generated, consultations, shows,
          surgeries, and revenue. Cohort anchor: lead_date in window. Spend
          Managed and ROI are not available — vendor costs live in a separate
          data layer. Name resolution is tracked as ENG-578.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load vendor performance. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Honest no-data notice when vendor attribution is not yet wired */}
      {data && !data.vendor_attribution_wired && data.note ? (
        <Card className="border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30">
          <CardContent className="py-4 text-sm text-amber-800 dark:text-amber-300">
            <span className="font-semibold">No per-vendor data.</span>{" "}
            {data.note}
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
              {
                label: "Consultations",
                value: formatCount(totalConsults),
              },
              { label: "Surgeries", value: formatCount(totalSurgeries) },
              {
                label: "Revenue collected",
                value: formatMoney(totalCollected),
              },
            ].map((m) => <MetricCard key={m.label} {...m} />)}
      </div>

      {/* Per-vendor ranking table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Vendor ranking</CardTitle>
          <CardDescription>
            Grouped by vendor_id (NULL = Unassigned). Spend Managed and ROI
            are always &ldquo;—&rdquo; — no vendor→spend column on the
            analytics fact. Today all rows are Unassigned (vendor attribution
            not yet wired — ENG-569).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading || !data ? (
            <Skeleton className="h-48 w-full" />
          ) : data.vendors.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No vendor data for this window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Vendor</th>
                    <th className="py-2 pr-3 text-right font-medium">Leads</th>
                    <th className="py-2 pr-3 text-right font-medium">
                      Consults
                    </th>
                    <th className="py-2 pr-3 text-right font-medium">Shows</th>
                    <th className="py-2 pr-3 text-right font-medium">
                      Surgeries
                    </th>
                    <th className="py-2 pr-3 text-right font-medium">
                      Revenue
                    </th>
                    <th className="py-2 pr-3 text-right font-medium">
                      Collected
                    </th>
                    <th className="py-2 pr-3 text-right font-medium">
                      Spend Managed
                    </th>
                    <th className="py-2 text-right font-medium">ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {data.vendors.map((g, i) => (
                    <tr
                      key={g.vendor_id ?? `unassigned-${i}`}
                      className="border-b border-border/50"
                    >
                      <td className="py-1.5 pr-3 font-medium">
                        {vendorLabel(g)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.leads)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.consults)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.shows)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatCount(g.surgeries)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoney(g.revenue)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {formatMoney(g.collected)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">
                        {NO_DATA_DASH}
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                        {NO_DATA_DASH}
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
