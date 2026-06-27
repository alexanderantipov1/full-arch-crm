"use client";

import { useState } from "react";
import { BarChart2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRevenueInfluence } from "@/lib/api/hooks/useRevenueInfluence";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type InfluenceRow,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { formatCount, formatMoney } from "../_components/format";

const ROLE_LABELS: Record<string, string> = {
  vendor: "Vendor",
  caller: "Caller",
  coordinator: "Coordinator",
  doctor: "Doctor",
};

const ROLES_ORDERED = ["vendor", "caller", "coordinator", "doctor"];

export default function RevenueInfluencePage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useRevenueInfluence(filters);
  const data = query.data;

  // Group rows by role for per-role sections
  const byRole: Record<string, InfluenceRow[]> = {};
  if (data) {
    for (const row of data.rows) {
      const existing = byRole[row.role];
      if (existing === undefined) {
        byRole[row.role] = [row];
      } else {
        existing.push(row);
      }
    }
  }

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <BarChart2 className="h-6 w-6" />
          Revenue influence matrix
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Employee &times; role &times; revenue influenced. For each role
          (Vendor / Caller / Coordinator / Doctor), shows the collected revenue
          from patients where that employee held that role.
        </p>
        <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
          <span className="font-semibold">Double-counting note:</span> The same
          patient&apos;s revenue is counted once per role they touch. A patient
          with both a caller and a coordinator assigned contributes their revenue
          to both the Caller and Coordinator rows. This is intentional —
          &ldquo;Revenue Influenced&rdquo; measures influence per role, not an
          additive breakdown. Do not sum across roles.
        </div>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load influence matrix. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {query.isLoading || !data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="space-y-6">
          {ROLES_ORDERED.map((role) => {
            const rows = byRole[role] ?? [];
            return (
              <Card key={role}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    {ROLE_LABELS[role] ?? role}
                  </CardTitle>
                  {role === "vendor" && (
                    <CardDescription className="text-amber-700 dark:text-amber-400">
                      No vendor data today — vendor_id is 100% NULL on the fact
                      (ENG-569 wires this). The table will populate automatically
                      once vendor attribution is wired.
                    </CardDescription>
                  )}
                  {role !== "vendor" && rows.length > 0 && (
                    <CardDescription>
                      Sorted by revenue influenced desc. NULL id = Unassigned.
                      Name resolution tracked as ENG-578.
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  {rows.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      {role === "vendor"
                        ? "No vendor rows — vendor_id not yet populated."
                        : "No data for this role in the selected window."}
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                            <th className="py-2 pr-3 font-medium">
                              {ROLE_LABELS[role] ?? role}
                            </th>
                            <th className="py-2 pr-3 text-right font-medium">
                              Cases
                            </th>
                            <th className="py-2 text-right font-medium">
                              Revenue Influenced
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((r, i) => (
                            <tr
                              key={r.employee_id ?? `unassigned-${i}`}
                              className="border-b border-border/50"
                            >
                              <td className="py-1.5 pr-3 font-medium">
                                {r.employee_label}
                              </td>
                              <td className="py-1.5 pr-3 text-right tabular-nums">
                                {formatCount(r.case_count)}
                              </td>
                              <td className="py-1.5 text-right tabular-nums">
                                {formatMoney(r.revenue_influenced)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
