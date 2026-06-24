"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CalendarRange,
  ChevronDown,
  ChevronRight,
  ListTree,
  MapPin,
  Search,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useLeadSourceLeads,
  useLeadSourceTree,
  type LeadSourceLeadsFilters,
} from "@/lib/api/hooks/useLeadSources";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import type { LeadSourceNode } from "@/lib/api/schemas";
import { cn, formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 50;

const PERIOD_PRESETS = [
  { value: "all", label: "All time", days: null },
  { value: "7", label: "Last 7 days", days: 7 },
  { value: "30", label: "Last 30 days", days: 30 },
  { value: "90", label: "Last 90 days", days: 90 },
  { value: "365", label: "Last 12 months", days: 365 },
] as const;

type DrillTarget = {
  path: string[];
  label: string;
};

type FlatRow = {
  node: LeadSourceNode;
  depth: number;
  path: string[];
};

function flattenTree(
  nodes: LeadSourceNode[],
  expanded: Set<string>,
  depth = 0,
  parentPath: string[] = [],
): FlatRow[] {
  const rows: FlatRow[] = [];
  for (const node of nodes) {
    const path = [...parentPath, node.label];
    rows.push({ node, depth, path });
    if (node.children.length > 0 && expanded.has(node.key)) {
      rows.push(...flattenTree(node.children, expanded, depth + 1, path));
    }
  }
  return rows;
}

function conversionRate(leads: number, attended: number): string {
  if (leads === 0) return "—";
  return `${((attended / leads) * 100).toFixed(1)}%`;
}

function formatMoney(amount: number): string {
  if (amount === 0) return "—";
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function isoFrom(days: number | null): string | undefined {
  if (days === null) return undefined;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  d.setUTCHours(0, 0, 0, 0);
  return d.toISOString();
}

export default function LeadSourcesPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState<string>("all");
  const [locationId, setLocationId] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [drill, setDrill] = useState<DrillTarget | null>(null);
  const [offset, setOffset] = useState(0);
  const [drillSort, setDrillSort] = useState<"created" | "collected">("created");

  // Debounce the search box so each keystroke does not refetch the tree.
  useEffect(() => {
    const handle = setTimeout(() => setSearch(searchInput.trim()), 400);
    return () => clearTimeout(handle);
  }, [searchInput]);

  const preset = PERIOD_PRESETS.find((p) => p.value === period) ?? PERIOD_PRESETS[0];
  const from = useMemo(() => isoFrom(preset.days), [preset.days]);

  const tenant = useCurrentTenant();
  const locations = tenant.data?.locations ?? [];

  const tree = useLeadSourceTree({
    from,
    search: search || undefined,
    location_id: locationId || undefined,
  });

  const drillFilters: LeadSourceLeadsFilters | null = drill
    ? {
        channel: drill.path[0] ?? "",
        source: drill.path[1],
        medium: drill.path[2],
        campaign: drill.path[3],
        from,
        limit: PAGE_SIZE,
        offset,
        sort: drillSort,
        location_id: locationId || undefined,
      }
    : null;
  const leads = useLeadSourceLeads(drillFilters);

  const rows = useMemo(
    () => (tree.data ? flattenTree(tree.data.sources, expanded) : []),
    [tree.data, expanded],
  );

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function openDrill(row: FlatRow) {
    setOffset(0);
    setDrillSort("created");
    setDrill({ path: row.path, label: row.path.join(" › ") });
  }

  function toggleDrillSort() {
    setOffset(0);
    setDrillSort((prev) => (prev === "collected" ? "created" : "collected"));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ListTree className="h-6 w-6" />
          Lead sources
        </h1>
        <p className="text-sm text-muted-foreground">
          Every acquisition resource in hierarchical order (source › medium ›
          campaign) with funnel counts: leads, consultations scheduled, and
          consultations attended. Click a row to inspect the leads behind it.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search source / medium / campaign…"
                className="w-72 pl-8"
                aria-label="Search resources"
              />
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
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <NativeSelect
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
                aria-label="Location"
                className="w-52"
              >
                <option value="">All locations</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.short_name ?? loc.name}
                    {loc.city ? ` · ${loc.city}` : ""}
                  </option>
                ))}
              </NativeSelect>
            </div>
            {tree.data ? (
              <div className="ml-auto flex items-center gap-4 text-sm text-muted-foreground">
                <span>
                  Leads:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.total_leads.toLocaleString()}
                  </span>
                </span>
                <span>
                  Scheduled:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.consults_scheduled.toLocaleString()}
                  </span>
                </span>
                <span>
                  Attended:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.consults_attended.toLocaleString()}
                  </span>
                </span>
                <span>
                  Collected:{" "}
                  <span className="font-medium text-foreground">
                    {formatMoney(tree.data.collected_amount)}
                  </span>
                </span>
              </div>
            ) : null}
          </div>
        </CardHeader>
        <CardContent>
          {tree.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : tree.isError ? (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load lead sources. Is the API running?
            </p>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No resources match the current filters.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-2 font-medium">Resource</th>
                  <th className="w-24 py-2 pr-2 text-right font-medium">Leads</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Scheduled</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Attended</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Collected</th>
                  <th className="w-24 py-2 text-right font-medium">Conv.</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.node.key}
                    className="border-b border-border/50 hover:bg-muted/50"
                  >
                    <td className="py-1.5 pr-2">
                      <div
                        className="flex items-center gap-1"
                        style={{ paddingLeft: `${row.depth * 1.5}rem` }}
                      >
                        {row.node.children.length > 0 ? (
                          <button
                            type="button"
                            onClick={() => toggle(row.node.key)}
                            aria-label={
                              expanded.has(row.node.key)
                                ? `Collapse ${row.node.label}`
                                : `Expand ${row.node.label}`
                            }
                            className="rounded p-0.5 hover:bg-muted"
                          >
                            {expanded.has(row.node.key) ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </button>
                        ) : (
                          <span className="w-5" />
                        )}
                        <button
                          type="button"
                          onClick={() => openDrill(row)}
                          className="truncate text-left font-medium hover:underline"
                          title={`Show leads for ${row.path.join(" › ")}`}
                        >
                          {row.node.label}
                        </button>
                        <Badge
                          variant="outline"
                          className="ml-1 hidden text-[10px] uppercase text-muted-foreground sm:inline-flex"
                        >
                          {row.node.level}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {row.node.leads.toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {row.node.consults_scheduled.toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {row.node.consults_attended.toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {formatMoney(row.node.collected_amount)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                      {conversionRate(row.node.leads, row.node.consults_attended)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Dialog open={drill !== null} onOpenChange={(open) => !open && setDrill(null)}>
        <DialogContent className="max-h-[85vh] max-w-4xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              {drill?.label}
            </DialogTitle>
            <DialogDescription>
              {leads.data
                ? `${leads.data.total.toLocaleString()} lead${leads.data.total === 1 ? "" : "s"} in this bucket`
                : "Loading leads…"}
            </DialogDescription>
          </DialogHeader>
          {leads.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : leads.isError ? (
            <p className="py-4 text-center text-sm text-destructive">
              Failed to load leads for this node.
            </p>
          ) : leads.data && leads.data.items.length > 0 ? (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-2 font-medium">Created</th>
                    <th className="py-2 pr-2 font-medium">Status</th>
                    <th className="py-2 pr-2 font-medium">Person</th>
                    <th className="py-2 pr-2 text-right font-medium">
                      <button
                        type="button"
                        onClick={toggleDrillSort}
                        className="hover:text-foreground hover:underline"
                        title={
                          drillSort === "collected"
                            ? "Sorted by money — click to sort by date"
                            : "Click to float paying clients to the top"
                        }
                      >
                        Collected{drillSort === "collected" ? " ↓" : ""}
                      </button>
                    </th>
                    <th className="py-2 pr-2 font-medium">Medium</th>
                    <th className="py-2 font-medium">Campaign</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.data.items.map((item) => (
                    <tr
                      key={item.id}
                      className={cn(
                        "border-b border-border/50 align-top",
                        item.location_mismatch && "bg-destructive/5",
                      )}
                    >
                      <td className="whitespace-nowrap py-1.5 pr-2 tabular-nums">
                        {formatDateTime(item.provider_created_at ?? item.created_at)}
                      </td>
                      <td className="py-1.5 pr-2">
                        <Badge variant="outline">{item.status}</Badge>
                      </td>
                      <td className="py-1.5 pr-2">
                        <div className="flex flex-col">
                          <Link
                            href={`/persons/${item.person_uid}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {item.display_name ?? `${item.person_uid.slice(0, 8)}…`}
                          </Link>
                          {item.phone ? (
                            <span className="text-xs text-muted-foreground">
                              {item.phone}
                            </span>
                          ) : null}
                          {item.email ? (
                            <span className="text-xs text-muted-foreground">
                              {item.email}
                            </span>
                          ) : null}
                          {item.location_mismatch ? (
                            <span className="text-xs font-medium text-destructive">
                              lead: {item.assigned_center ?? "no center"} → consults
                              here
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        {formatMoney(item.collected_amount)}
                      </td>
                      <td className="py-1.5 pr-2">{item.utm_medium ?? "—"}</td>
                      <td className="py-1.5">
                        <div className="flex flex-col gap-1">
                          <span>{item.utm_campaign ?? "—"}</span>
                          {Object.keys(item.attribution).length > 0 ? (
                            <details className="text-xs text-muted-foreground">
                              <summary className="cursor-pointer select-none">
                                attribution ({Object.keys(item.attribution).length})
                              </summary>
                              <dl className="mt-1 space-y-0.5">
                                {Object.entries(item.attribution).map(([k, v]) => (
                                  <div key={k} className="flex gap-2">
                                    <dt className="shrink-0 font-mono">{k}:</dt>
                                    <dd className="break-all">{String(v)}</dd>
                                  </div>
                                ))}
                              </dl>
                            </details>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {leads.data.total > PAGE_SIZE ? (
                <div className="flex items-center justify-between pt-2 text-sm">
                  <span className="text-muted-foreground">
                    {offset + 1}–{Math.min(offset + PAGE_SIZE, leads.data.total)} of{" "}
                    {leads.data.total.toLocaleString()}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset + PAGE_SIZE >= leads.data.total}
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className={cn("py-4 text-center text-sm text-muted-foreground")}>
              No leads in this bucket for the selected period.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
