"use client";

/**
 * ENG-419 — funnel responsibility analytics dashboard.
 *
 * Reads four endpoints (aggregate / dropoff / revenue-by-actor / owners)
 * and renders four panels in one screen:
 *
 *   1. Per-stage funnel chain with the top-3 operational owners per stage
 *      (answers "conversion by TC, by agent, by Sofia").
 *   2. Drop-off attribution table — "stopped here, owner X, N people,
 *      $Y" for every stage. Sorted by dollar_total desc within a stage.
 *   3. Revenue-by-actor table — net realized payments by TC / by caller
 *      (operational) + by doctor (clinical). Reuses the PM Payments
 *      formula so revenue slices reconcile.
 *   4. Filter bar consistent with ENG-251 PM dashboard (date, location,
 *      source, role).
 */

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Filter, Stethoscope, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FunnelFilters,
  useFunnelAggregate,
  useFunnelDropoff,
  useFunnelRevenueByActor,
} from "@/lib/api/hooks/useFunnel";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import type {
  FunnelStage,
  FunnelStageActorBucket,
  ResponsibilityRole,
} from "@/lib/api/schemas";
import { formatCurrency } from "@/lib/utils";

type FunnelDraft = {
  from: string;
  to: string;
  location_id: string;
  source_provider: "" | "salesforce" | "carestack";
  role: "" | ResponsibilityRole;
};

const STAGE_LABELS: Record<FunnelStage, string> = {
  lead_new: "Lead new",
  lead_contacted: "Lead contacted",
  consult_scheduled: "Consult scheduled",
  consult_no_show: "Consult no-show",
  consult_completed: "Consult completed",
  opportunity_open: "Opportunity open",
  opportunity_won: "Won",
  opportunity_lost: "Lost",
};

function defaultDraft(): FunnelDraft {
  const today = new Date();
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - 30);
  return {
    from: start.toISOString().slice(0, 10),
    to: today.toISOString().slice(0, 10),
    location_id: "",
    source_provider: "",
    role: "",
  };
}

function draftToFilters(draft: FunnelDraft): FunnelFilters {
  const next: FunnelFilters = {};
  if (draft.from) next.from = `${draft.from}T00:00:00Z`;
  if (draft.to) {
    const d = new Date(`${draft.to}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + 1);
    next.to = d.toISOString();
  }
  if (draft.source_provider) next.source_provider = draft.source_provider;
  if (draft.location_id.trim()) next.location_id = draft.location_id.trim();
  if (draft.role) next.role = draft.role;
  return next;
}

export default function ProjectManagerFunnelPage() {
  const [draft, setDraft] = useState<FunnelDraft>(defaultDraft);
  const [filters, setFilters] = useState<FunnelFilters>(() =>
    draftToFilters(defaultDraft()),
  );
  const { data: aggregate, isLoading: aggregateLoading } =
    useFunnelAggregate(filters);
  const { data: dropoff, isLoading: dropoffLoading } =
    useFunnelDropoff(filters);
  const { data: revenue, isLoading: revenueLoading } =
    useFunnelRevenueByActor(filters);
  const { data: tenantData } = useCurrentTenant();
  const locationOptions = useMemo(
    () =>
      [...(tenantData?.locations ?? [])].sort((a, b) => {
        const an = a.short_name ?? a.name ?? "";
        const bn = b.short_name ?? b.name ?? "";
        return an.localeCompare(bn);
      }),
    [tenantData],
  );

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters(draftToFilters(draft));
  }

  function resetFilters() {
    const next = defaultDraft();
    setDraft(next);
    setFilters(draftToFilters(next));
  }

  // Headline KPIs — pulled from the per-stage aggregate so they always
  // reconcile with the funnel chart below.
  const leadToConsult = useMemo(() => {
    if (!aggregate) return null;
    const lead = aggregate.stages.find((s) => s.stage === "lead_new");
    const consult = aggregate.stages.find((s) => s.stage === "consult_scheduled");
    if (!lead || lead.person_count === 0) return null;
    return ((consult?.person_count ?? 0) / lead.person_count) * 100;
  }, [aggregate]);
  const consultToWon = useMemo(() => {
    if (!aggregate) return null;
    const consult = aggregate.stages.find((s) => s.stage === "consult_completed");
    const won = aggregate.stages.find((s) => s.stage === "opportunity_won");
    if (!consult || consult.person_count === 0) return null;
    return ((won?.person_count ?? 0) / consult.person_count) * 100;
  }, [aggregate]);
  const totalDropoffDollars = useMemo(() => {
    if (!dropoff) return 0;
    return dropoff.stages
      .filter(
        (s) => s.stage !== "opportunity_won" && s.stage !== "opportunity_lost",
      )
      .reduce((acc, s) => acc + s.dollar_total, 0);
  }, [dropoff]);
  const totalRevenue = useMemo(() => {
    if (!revenue) return 0;
    return revenue.items
      .filter((r) => r.actor.role === "operational")
      .reduce((acc, r) => acc + r.collected_total, 0);
  }, [revenue]);

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <Button asChild variant="ghost" size="sm" className="w-fit px-0">
          <Link href="/project-manager">
            <ArrowLeft className="h-4 w-4" />
            Project Manager
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold">Funnel responsibility</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Conversion, no-show, and drop-off attributed to the responsible
          party — call-center agent / TC / doctor.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryTile
          label="Lead → consult"
          loading={aggregateLoading}
          value={leadToConsult === null ? "—" : `${leadToConsult.toFixed(1)}%`}
          hint="Persons who scheduled a consult ÷ persons with a Lead event in the range."
        />
        <SummaryTile
          label="Consult → won"
          loading={aggregateLoading}
          value={consultToWon === null ? "—" : `${consultToWon.toFixed(1)}%`}
          hint="Persons whose Opportunity won ÷ persons whose consult completed."
        />
        <SummaryTile
          label="Drop-off ($ at risk)"
          loading={dropoffLoading}
          value={formatCurrency(totalDropoffDollars)}
          hint="Σ Opportunity.Amount across people stuck before the won/lost stages."
        />
        <SummaryTile
          label="Collected (operational)"
          loading={revenueLoading}
          value={formatCurrency(totalRevenue)}
          hint="Net realized payments attributed to operational owners (TC + caller)."
        />
      </div>

      <form
        onSubmit={applyFilters}
        className="grid grid-cols-2 gap-2 rounded-lg border bg-card p-3 xl:grid-cols-6"
      >
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">From</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.from}
            onChange={(e) => setDraft((v) => ({ ...v, from: e.target.value }))}
          />
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">To</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.to}
            onChange={(e) => setDraft((v) => ({ ...v, to: e.target.value }))}
          />
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Provider</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.source_provider}
            onChange={(e) =>
              setDraft((v) => ({
                ...v,
                source_provider:
                  e.target.value as FunnelDraft["source_provider"],
              }))
            }
          >
            <option value="">All</option>
            <option value="salesforce">Salesforce</option>
            <option value="carestack">CareStack</option>
          </NativeSelect>
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Location</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.location_id}
            onChange={(e) =>
              setDraft((v) => ({ ...v, location_id: e.target.value }))
            }
          >
            <option value="">All locations</option>
            {locationOptions.map((loc) => {
              const label = loc.short_name ?? loc.name ?? loc.id.slice(0, 8);
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
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Role</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.role}
            onChange={(e) =>
              setDraft((v) => ({
                ...v,
                role: e.target.value as FunnelDraft["role"],
              }))
            }
          >
            <option value="">All</option>
            <option value="operational">Operational (agent / TC)</option>
            <option value="clinical">Clinical (doctor)</option>
          </NativeSelect>
        </label>
        <div className="col-span-2 flex items-end gap-2 xl:col-span-1">
          <Button type="submit" size="sm" className="h-8 gap-1 text-xs">
            <Filter className="h-3 w-3" />
            Filter
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 text-xs"
            onClick={resetFilters}
          >
            Reset
          </Button>
        </div>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>Funnel chain</CardTitle>
          <CardDescription>
            Persons that ever reached each stage in the selected window.
            Top-3 owners per stage shown inline.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {aggregateLoading && <Skeleton className="h-32 w-full" />}
          {aggregate?.stages.map((stage) => (
            <FunnelStageRow
              key={stage.stage}
              stage={stage.stage}
              personCount={stage.person_count}
              eventCount={stage.event_count}
              top={[...stage.by_actor]
                .sort((a, b) => b.person_count - a.person_count)
                .slice(0, 3)}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Drop-off attribution</CardTitle>
          <CardDescription>
            “Stopped here, owner X, N people, $Y.” Dollar basis: realized
            payments for won; Opportunity.Amount for everything else.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {dropoffLoading && <Skeleton className="h-32 w-full" />}
          {dropoff?.stages.map((stage) => (
            <div key={stage.stage} className="rounded-md border bg-card p-3">
              <div className="flex items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="capitalize">
                    {STAGE_LABELS[stage.stage]}
                  </Badge>
                  <span className="font-medium">
                    {stage.person_count.toLocaleString()} people
                  </span>
                </div>
                <span className="font-medium">
                  {formatCurrency(stage.dollar_total)}
                </span>
              </div>
              {stage.by_operational_actor.length > 0 ? (
                <table className="mt-2 w-full text-left text-xs">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th className="py-1 font-medium">Owner</th>
                      <th className="py-1 font-medium">People</th>
                      <th className="py-1 font-medium">$</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stage.by_operational_actor.map((b, idx) => (
                      <tr key={`${b.actor?.actor_id ?? "no-actor"}-${idx}`} className="border-t">
                        <td className="py-1.5">
                          {b.actor ? (
                            <span className="inline-flex items-center gap-1.5">
                              <ActorGlyph
                                actorType={b.actor.actor_type}
                                role={b.actor.role}
                              />
                              {b.actor.name}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">
                              No owner attributed
                            </span>
                          )}
                        </td>
                        <td className="py-1.5">{b.person_count}</td>
                        <td className="py-1.5">{formatCurrency(b.dollar_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground">
                  No persons dropped here in the selected window.
                </p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Revenue by actor</CardTitle>
          <CardDescription>
            Net realized payments attributed to operational + clinical
            owners. Uses the same Collected formula as PM Payments.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {revenueLoading && <Skeleton className="h-24 w-full" />}
          {revenue && revenue.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No revenue in the selected window.
            </p>
          ) : null}
          {revenue && revenue.items.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr>
                  <th className="py-1 font-medium">Owner</th>
                  <th className="py-1 font-medium">Role</th>
                  <th className="py-1 font-medium">Payments</th>
                  <th className="py-1 font-medium">Collected</th>
                </tr>
              </thead>
              <tbody>
                {revenue.items.map((r, idx) => (
                  <tr
                    key={`${r.actor.actor_id}-${r.actor.role}-${idx}`}
                    className="border-t"
                  >
                    <td className="py-1.5">
                      <span className="inline-flex items-center gap-1.5">
                        <ActorGlyph
                          actorType={r.actor.actor_type}
                          role={r.actor.role}
                        />
                        {r.actor.name}
                      </span>
                    </td>
                    <td className="py-1.5 capitalize text-xs text-muted-foreground">
                      {r.actor.role}
                    </td>
                    <td className="py-1.5">{r.payment_count}</td>
                    <td className="py-1.5 font-medium">
                      {formatCurrency(r.collected_total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function FunnelStageRow({
  stage,
  personCount,
  eventCount,
  top,
}: {
  stage: FunnelStage;
  personCount: number;
  eventCount: number;
  top: FunnelStageActorBucket[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-card px-3 py-2">
      <Badge variant="outline" className="min-w-[8rem] capitalize">
        {STAGE_LABELS[stage]}
      </Badge>
      <span className="text-sm font-medium">
        {personCount.toLocaleString()} people
      </span>
      <span className="text-xs text-muted-foreground">
        ({eventCount.toLocaleString()} events)
      </span>
      <span className="ml-auto flex flex-wrap items-center gap-1.5">
        {top.length === 0 ? (
          <span className="text-xs text-muted-foreground">
            No responsibility rows
          </span>
        ) : (
          top.map((b, idx) => (
            <span
              key={`${b.actor.actor_id}-${b.actor.role}-${idx}`}
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px]"
              title={`${b.actor.name} · ${b.person_count} people, ${b.event_count} events`}
            >
              <ActorGlyph actorType={b.actor.actor_type} role={b.actor.role} />
              <span>{b.actor.name}</span>
              <span className="text-muted-foreground">
                · {b.person_count}
              </span>
            </span>
          ))
        )}
      </span>
    </div>
  );
}

function ActorGlyph({
  actorType,
  role,
}: {
  actorType: string;
  role: ResponsibilityRole;
}) {
  if (role === "clinical") {
    return <Stethoscope className="h-3 w-3 text-violet-600" />;
  }
  if (actorType === "ai") {
    return <User className="h-3 w-3 text-amber-600" />;
  }
  return <User className="h-3 w-3 text-slate-600" />;
}

function SummaryTile({
  label,
  value,
  loading,
  hint,
}: {
  label: string;
  value?: string;
  loading: boolean;
  hint: string;
}) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">
        {loading ? <Skeleton className="h-6 w-20" /> : (value ?? "—")}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}
