"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useBottlenecks } from "@/lib/api/hooks/useBottlenecks";
import {
  DEFAULT_ANALYTICS_FILTERS,
  type AnalyticsFilterValue,
  type Bottleneck,
  type BottleneckSeverity,
} from "@/lib/api/schemas";
import { AnalyticsFilterBar } from "../_components/AnalyticsFilterBar";
import { formatMoneyOrDash } from "../_components/format";

/** Badge colour per severity. */
function severityClass(severity: BottleneckSeverity): string {
  switch (severity) {
    case "high":
      return "bg-destructive/10 text-destructive border-destructive/20";
    case "medium":
      return "bg-amber-500/10 text-amber-700 border-amber-500/20";
    case "low":
      return "bg-muted text-muted-foreground border-border";
  }
}

/** Human-readable category label. */
function categoryLabel(category: Bottleneck["category"]): string {
  switch (category) {
    case "campaign_low_show":
      return "Campaign — Low show rate";
    case "coordinator_low_surgery_conversion":
      return "Coordinator — Low surgery conversion";
    case "doctor_low_acceptance":
      return "Doctor — Low treatment acceptance";
    case "caller_low_booking":
      return "Caller — Low consult booking";
  }
}

/** One bottleneck finding card. */
function FindingCard({ finding }: { finding: Bottleneck }) {
  return (
    <Card
      className={cn(
        "border",
        finding.severity === "high" && "border-destructive/30",
        finding.severity === "medium" && "border-amber-500/30",
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs font-medium",
                  severityClass(finding.severity),
                )}
              >
                {finding.severity.toUpperCase()}
              </span>
              <span className="text-xs text-muted-foreground">
                {categoryLabel(finding.category)}
              </span>
            </div>
            <CardTitle className="text-sm font-medium leading-snug">
              {finding.description}
            </CardTitle>
          </div>
          {finding.estimated_revenue_loss !== null && (
            <div className="shrink-0 text-right">
              <p className="text-xs text-muted-foreground">Est. revenue loss</p>
              <p className="text-base font-semibold text-destructive">
                {formatMoneyOrDash(finding.estimated_revenue_loss)}
              </p>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-start gap-1.5 text-sm text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{finding.suggested_action}</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Entity: {finding.entity.label}
        </p>
      </CardContent>
    </Card>
  );
}

export default function BottlenecksPage() {
  const [filters, setFilters] = useState<AnalyticsFilterValue>(
    DEFAULT_ANALYTICS_FILTERS,
  );
  const query = useBottlenecks(filters);
  const data = query.data;

  const highCount = data?.findings.filter((f) => f.severity === "high").length ?? 0;
  const medCount = data?.findings.filter((f) => f.severity === "medium").length ?? 0;
  const lowCount = data?.findings.filter((f) => f.severity === "low").length ?? 0;
  const totalLoss = data?.findings.reduce(
    (s, f) => s + (f.estimated_revenue_loss ?? 0),
    0,
  );

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <AlertTriangle className="h-6 w-6" />
          Bottleneck detection
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Rule-based funnel bottleneck finder. Evaluates campaigns, coordinators,
          doctors, and callers against their cohort peers. Only entities with
          sufficient sample sizes are evaluated — no findings are invented from noise.
          Revenue loss estimates compare each entity to the cohort median performer.
        </p>
      </div>

      <AnalyticsFilterBar value={filters} onChange={setFilters} />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load bottleneck analysis. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {query.isLoading || !data
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-16" />
                </CardContent>
              </Card>
            ))
          : [
              {
                label: "High severity",
                value: String(highCount),
                highlight: highCount > 0,
              },
              { label: "Medium severity", value: String(medCount) },
              { label: "Low severity", value: String(lowCount) },
              {
                label: "Est. total revenue loss",
                value:
                  totalLoss !== undefined && totalLoss > 0
                    ? formatMoneyOrDash(totalLoss)
                    : "—",
              },
            ].map((m) => (
              <Card key={m.label}>
                <CardContent className="py-4">
                  <p className="text-sm text-muted-foreground">{m.label}</p>
                  <p
                    className={cn(
                      "text-2xl font-bold tabular-nums",
                      "highlight" in m && m.highlight && "text-destructive",
                    )}
                  >
                    {m.value}
                  </p>
                </CardContent>
              </Card>
            ))}
      </div>

      {/* Findings list */}
      {query.isLoading || !data ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : data.findings.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
            <CheckCircle className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm font-medium text-muted-foreground">
              No bottlenecks detected for this window.
            </p>
            <p className="max-w-sm text-xs text-muted-foreground">
              Either no entity is more than 40% below the cohort median, the
              cohort median is zero (no baseline to compare against), or the
              cohort is too sparse (entities below the minimum sample threshold
              are excluded to avoid noise).
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {data.findings.map((finding, i) => (
            <FindingCard key={`${finding.category}-${finding.entity.id ?? i}`} finding={finding} />
          ))}
        </div>
      )}

      {/* Methodology note */}
      <Card className="bg-muted/30">
        <CardHeader className="pb-1">
          <CardTitle className="text-sm">Detection methodology</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          <p>
            Each rule compares an entity's conversion rate to the cohort median
            using a <strong>relative shortfall</strong>, so it works at any base
            rate (a caller booking 0% is flagged even when the typical peer only
            books ~6%). An entity is flagged when its rate is at least 40% below
            the cohort median, with a small 2 pp absolute floor so entities that
            are trivially close to the median at high base rates aren't flagged.
            Rules: campaigns (show rate), coordinators (show→surgery), doctors
            (consult→acceptance), callers (lead→consult). Severity by relative
            shortfall s = (median − rate) / median: high s ≥ 0.75, medium s ≥
            0.55, otherwise low. Minimum sample sizes: campaigns 10 leads,
            coordinators 5 consults, doctors 5 consults, callers 10 leads. No
            findings are produced when the cohort median is zero (no baseline to
            compare against). Revenue loss = lost conversions × cohort
            revenue-per-unit. Unassigned entities are never flagged.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
