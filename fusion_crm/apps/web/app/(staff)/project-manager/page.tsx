"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, Filter, Info, RefreshCw, Search } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import {
  DashboardPmFilters,
  useDashboardPm,
} from "@/lib/api/hooks/useDashboard";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import { formatDateTime, formatRelative } from "@/lib/utils";
import type {
  DashboardBreakdown,
  DashboardKpi,
  DashboardSemanticReadModel,
} from "@/lib/api/schemas";

type DashboardDraftFilters = {
  from: string;
  to: string;
  source_provider: "" | "salesforce" | "carestack";
  lead_source: string;
  location_id: string;
  q: string;
};

const DEFAULT_DRAFT: DashboardDraftFilters = {
  from: "",
  to: "",
  source_provider: "",
  lead_source: "",
  location_id: "",
  q: "",
};

// Default the dashboard to "last 30 days" so it lands populated instead of
// blank. The reset button still clears to the empty draft above.
function thirtyDayDraft(): DashboardDraftFilters {
  const today = new Date();
  const thirtyAgo = new Date(today);
  thirtyAgo.setUTCDate(thirtyAgo.getUTCDate() - 30);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { ...DEFAULT_DRAFT, from: fmt(thirtyAgo), to: fmt(today) };
}

function thirtyDayFilters(draft: DashboardDraftFilters): DashboardPmFilters {
  return {
    from: `${draft.from}T00:00:00Z`,
    to: nextDayStartIso(draft.to),
  };
}

export default function DashboardPage() {
  const initialDraft = useMemo(thirtyDayDraft, []);
  const [draft, setDraft] = useState<DashboardDraftFilters>(initialDraft);
  const [filters, setFilters] = useState<DashboardPmFilters>(() =>
    thirtyDayFilters(initialDraft),
  );
  const { data, isLoading, isFetching, error, refetch } = useDashboardPm(filters);
  const { data: tenantData } = useCurrentTenant();
  const locationOptions = useMemo(() => {
    const list = tenantData?.locations ?? [];
    return [...list].sort((a, b) => {
      const an = a.short_name ?? a.name ?? "";
      const bn = b.short_name ?? b.name ?? "";
      return an.localeCompare(bn);
    });
  }, [tenantData]);

  const kpis = useMemo(() => {
    const byKey = new Map<string, DashboardKpi>();
    data?.kpis.forEach((kpi) => byKey.set(kpi.key, kpi));
    return byKey;
  }, [data]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: DashboardPmFilters = {};
    if (draft.from) next.from = `${draft.from}T00:00:00Z`;
    if (draft.to) next.to = nextDayStartIso(draft.to);
    if (draft.source_provider) next.source_provider = draft.source_provider;
    if (draft.lead_source.trim()) next.lead_source = draft.lead_source.trim();
    if (draft.location_id) next.location_id = draft.location_id;
    if (draft.q.trim()) next.q = draft.q.trim();
    setFilters(next);
  }

  function resetFilters() {
    setDraft(DEFAULT_DRAFT);
    setFilters({});
  }

  return (
    <div className="space-y-6 p-8">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Project Manager</h1>
          <p className="text-sm text-muted-foreground">
            Salesforce and CareStack pipeline for PM and analyst workflows.
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="w-fit">
          <Link href="/project-manager/leads">Open leads</Link>
        </Button>
        <Button asChild variant="outline" size="sm" className="w-fit">
          <Link href="/project-manager/funnel">Funnel responsibility</Link>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-fit gap-2"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </header>

      <form
        onSubmit={applyFilters}
        className="grid grid-cols-1 gap-3 rounded-lg border bg-card p-4 md:grid-cols-2 xl:grid-cols-6"
      >
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">From</span>
          <Input
            type="date"
            value={draft.from}
            onChange={(event) =>
              setDraft((value) => ({ ...value, from: event.target.value }))
            }
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">To</span>
          <Input
            type="date"
            value={draft.to}
            onChange={(event) =>
              setDraft((value) => ({ ...value, to: event.target.value }))
            }
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Provider</span>
          <NativeSelect
            value={draft.source_provider}
            onChange={(event) =>
              setDraft((value) => ({
                ...value,
                source_provider: event.target.value as DashboardDraftFilters["source_provider"],
              }))
            }
          >
            <option value="">All providers</option>
            <option value="salesforce">Salesforce</option>
            <option value="carestack">CareStack</option>
          </NativeSelect>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Lead source</span>
          <Input
            value={draft.lead_source}
            onChange={(event) =>
              setDraft((value) => ({ ...value, lead_source: event.target.value }))
            }
            placeholder="Website"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Location</span>
          <NativeSelect
            value={draft.location_id}
            onChange={(event) =>
              setDraft((value) => ({ ...value, location_id: event.target.value }))
            }
          >
            <option value="">All locations</option>
            {locationOptions.map((loc) => {
              const label =
                loc.short_name ?? loc.name ?? loc.id.slice(0, 8);
              const sub = loc.city ? ` · ${loc.city}` : "";
              return (
                <option key={loc.id} value={loc.id}>
                  {label}
                  {sub}
                </option>
              );
            })}
          </NativeSelect>
        </label>
        <label className="space-y-1 text-sm xl:col-span-2">
          <span className="text-xs font-medium text-muted-foreground">Search</span>
          <span className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={draft.q}
              onChange={(event) =>
                setDraft((value) => ({ ...value, q: event.target.value }))
              }
              className="pl-9"
              placeholder="Source id or activity summary"
            />
          </span>
        </label>
        <div className="flex gap-2 md:col-span-2 xl:col-span-6">
          <Button type="submit" className="gap-2">
            <Filter className="h-4 w-4" />
            Apply filters
          </Button>
          <Button type="button" variant="outline" onClick={resetFilters}>
            Reset
          </Button>
        </div>
      </form>

      {error && (
        <Card className="border-destructive">
          <CardContent className="py-6 text-sm text-destructive">
            Failed to load dashboard.
          </CardContent>
        </Card>
      )}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Stat
          label="Pipeline"
          value={isLoading ? null : kpis.get("pipeline_total")?.value ?? 0}
          hint="Active leads"
        />
        <Stat
          label="Consultations"
          value={isLoading ? null : kpis.get("consultations_total")?.value ?? 0}
          hint="Selected window"
        />
        <Stat
          label="Completed"
          value={isLoading ? null : kpis.get("completed_consultations")?.value ?? 0}
          hint="Consults"
        />
        <Stat
          label="Open followups"
          value={isLoading ? null : kpis.get("open_followups")?.value ?? 0}
          hint="Tenant-wide"
        />
        <Stat
          label="Overdue"
          value={isLoading ? null : kpis.get("overdue_followups")?.value ?? 0}
          hint="Followups"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Funnel</CardTitle>
            <CardDescription>Lead status through consultation completion.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading
              ? [...Array(6)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)
              : data?.funnel.map((stage) => (
                  <div
                    key={stage.key}
                    className="grid grid-cols-[minmax(8rem,1fr)_minmax(8rem,3fr)_3rem] items-center gap-3 text-sm"
                    title={stage.hint ?? undefined}
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{stage.label}</span>
                      {stage.hint && (
                        <span className="text-[10px] text-muted-foreground">
                          {stage.hint}
                        </span>
                      )}
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary"
                        style={{ width: `${barWidth(stage.count, data.funnel)}%` }}
                      />
                    </div>
                    <span className="text-right font-mono text-muted-foreground">
                      {stage.count}
                    </span>
                  </div>
                ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Treatment & payments</CardTitle>
            <CardDescription>Read-only aggregate track.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Badge variant="outline">
              {data?.treatment_payments.status.replace("_", " ") ?? "loading"}
            </Badge>
            <p className="text-sm text-muted-foreground">
              {data?.treatment_payments.message ??
                "Treatment and payment aggregates are loading."}
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Metric
                label="Presented"
                hint="Treatment procedures presented or proposed to patients in CareStack."
                value={
                  isLoading
                    ? null
                    : data?.treatment_payments.treatment_presented_count ?? 0
                }
              />
              <Metric
                label="Completed"
                hint="Treatment procedures marked completed in CareStack."
                value={
                  isLoading
                    ? null
                    : data?.treatment_payments.treatment_completed_count ?? 0
                }
              />
              <Metric
                label="Invoices"
                hint="Number of CareStack invoices captured."
                value={isLoading ? null : data?.treatment_payments.invoice_count ?? 0}
              />
              <Metric
                label="Payments"
                hint="Total invoiced amount from CareStack invoice events (invoice-level total)."
                value={
                  isLoading
                    ? null
                    : formatMoney(data?.treatment_payments.payment_total_amount ?? 0)
                }
              />
              <Metric
                label="Collected"
                hint="Money actually received, summed from CareStack payment events — includes partial payments."
                value={
                  isLoading
                    ? null
                    : formatMoney(data?.treatment_payments.collected_total ?? 0)
                }
              />
              <Metric
                label="Payments (count)"
                hint="Number of CareStack payment transactions making up Collected, for the selected window and location."
                value={
                  isLoading ? null : data?.treatment_payments.payment_event_count ?? 0
                }
              />
              <Metric
                label="Outstanding"
                hint="Amount still owed — sum of each patient's latest CareStack balance (patient + insurance). Tenant-wide: not scoped by the location filter (CareStack payment summary has no location)."
                value={
                  isLoading
                    ? null
                    : formatMoney(data?.treatment_payments.outstanding_total ?? 0)
                }
              />
            </div>
            {data?.treatment_payments.has_partial_payments && (
              <span className="inline-flex items-center gap-1">
                <Badge variant="secondary">Partial payments outstanding</Badge>
                <InfoHint text="Some patients have paid part of what they owe and still have a balance left." />
              </span>
            )}
            {typeof data?.treatment_payments.ar_risk_count === "number" && (
              <span className="inline-flex items-center gap-1">
                <Badge variant="destructive">
                  {data.treatment_payments.ar_risk_count} patients at AR risk
                </Badge>
                <InfoHint text="Patients whose latest CareStack balance owed is over $500 — accounts-receivable risk. Tenant-wide: not scoped by the location filter (CareStack payment summary has no location)." />
              </span>
            )}
            {data?.treatment_payments.last_payment_at && (
              <div className="text-xs text-muted-foreground">
                Last payment {formatDateTime(data.treatment_payments.last_payment_at)}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <SemanticAnalyticsPanel
        data={data?.semantic_analytics}
        isLoading={isLoading}
      />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Breakdowns data={data?.breakdowns} isLoading={isLoading} />
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Operational timeline events across providers.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading &&
              [...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            {data?.recent_activity.map((event, index) => (
              <div
                key={`${event.kind}-${event.occurred_at}-${index}`}
                className="rounded-md border bg-card px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{event.summary}</span>
                  <Badge variant="secondary" className="capitalize">
                    {event.source_provider}
                  </Badge>
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{formatRelative(event.occurred_at)}</span>
                  {event.source_external_id && <span>{event.source_external_id}</span>}
                  {event.projection?.status && <span>{event.projection.status}</span>}
                </div>
              </div>
            ))}
            {data && data.recent_activity.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No matching activity in this filter set.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Sync health</CardTitle>
          <CardDescription>Latest provider sync runs.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {isLoading &&
            [...Array(2)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
          {data?.sync_health.map((run, index) => (
            <div
              key={`${run.provider}-${run.started_at}-${index}`}
              className="rounded-md border px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium capitalize">
                  {run.provider} {run.object_scope ? `· ${run.object_scope}` : ""}
                </div>
                <Badge variant={run.status === "failed" ? "destructive" : "outline"}>
                  {run.status}
                </Badge>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {run.records_succeeded}/{run.records_total} records ·{" "}
                {formatDateTime(run.started_at)}
              </div>
              {run.error && <div className="mt-1 text-xs text-destructive">{run.error}</div>}
            </div>
          ))}
          {data && data.sync_health.length === 0 && (
            <p className="text-sm text-muted-foreground">No sync runs found.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SemanticAnalyticsPanel({
  data,
  isLoading,
}: {
  data: DashboardSemanticReadModel[] | undefined;
  isLoading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Semantic analytics
          </CardTitle>
          <CardDescription>
            Approved read models powering this dashboard.
          </CardDescription>
        </div>
        <Button asChild variant="outline" size="sm" className="w-fit">
          <Link href="/dev/semantic-analytics?doc=read-models">Open docs</Link>
        </Button>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 xl:grid-cols-5">
        {isLoading &&
          [...Array(5)].map((_, i) => <Skeleton key={i} className="h-36 w-full" />)}
        {data?.map((model) => (
          <div key={model.query_id} className="rounded-md border p-3">
            <div className="min-h-12">
              <div className="text-sm font-medium">{model.title}</div>
              <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                {model.query_id}
              </div>
            </div>
            <div className="mt-3 space-y-2">
              {model.metrics.map((metric) => (
                <div
                  key={metric.key}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="text-muted-foreground">{metric.label}</span>
                  <span className="font-mono">
                    {formatSemanticMetric(metric.key, metric.value)}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {model.data_classes.map((dataClass) => (
                <Badge key={dataClass} variant="secondary" className="text-[10px]">
                  {dataClass}
                </Badge>
              ))}
              {model.export_available && (
                <Badge variant="outline" className="text-[10px]">
                  CSV
                </Badge>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | null;
  hint: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        {value === null ? (
          <Skeleton className="h-7 w-16" />
        ) : (
          <CardTitle className="text-3xl">{value}</CardTitle>
        )}
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground">{hint}</CardContent>
    </Card>
  );
}

function InfoHint({ text }: { text: string }) {
  // Tiny "?" helper: shows the explanation on hover AND on click/focus
  // (keyboard + touch friendly). Pure Tailwind, no extra dependency.
  return (
    <span className="group relative inline-flex items-center align-middle">
      <button
        type="button"
        aria-label={text}
        className="inline-flex rounded-full text-muted-foreground/70 transition-colors hover:text-foreground focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <Info className="h-3 w-3" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-0 z-30 mb-1 hidden w-56 rounded-md bg-foreground px-2 py-1.5 text-xs font-normal normal-case leading-snug text-background shadow-md group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string | null;
  hint?: string;
}) {
  return (
    <div className="rounded-md border px-2 py-2">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <span>{label}</span>
        {hint ? <InfoHint text={hint} /> : null}
      </div>
      {value === null ? (
        <Skeleton className="mt-1 h-5 w-14" />
      ) : (
        <div className="mt-1 font-mono text-sm">{value}</div>
      )}
    </div>
  );
}

function Breakdowns({
  data,
  isLoading,
}: {
  data: DashboardBreakdown[] | undefined;
  isLoading: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Breakdowns</CardTitle>
        <CardDescription>Status, source, and provider distribution.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {isLoading &&
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}
        {data?.map((breakdown) => (
          <div key={breakdown.key} className="space-y-2">
            <div className="text-sm font-medium">{breakdown.label}</div>
            <div className="space-y-1">
              {breakdown.items.map((item) => (
                <div
                  key={item.key}
                  className="flex items-center justify-between rounded-md border px-2 py-1.5 text-sm"
                >
                  <span className="truncate">{item.label}</span>
                  <span className="font-mono text-muted-foreground">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function barWidth(
  value: number,
  stages: Array<{ count: number }>,
): number {
  const max = Math.max(1, ...stages.map((stage) => stage.count));
  return Math.max(4, Math.round((value / max) * 100));
}

function nextDayStartIso(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString();
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatSemanticMetric(key: string, value: number): string {
  if (key.includes("total") && key.includes("collected")) {
    return formatMoney(value);
  }
  if (key === "collected_total") {
    return formatMoney(value);
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}
