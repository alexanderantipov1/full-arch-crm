"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  CalendarRange,
  ChevronDown,
  ChevronRight,
  GitBranch,
  Link2,
  TriangleAlert,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { AttributionDocsDialog } from "@/components/attribution/AttributionDocsDialog";
import {
  useAttributionNodeLeads,
  useAttributionTree,
  type AttributionNodeFilters,
} from "@/lib/api/hooks/useAttribution";
import type { AttributionTreeNode } from "@/lib/api/schemas";
import { cn, formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 50;

type DrillTarget = {
  key: string;
  label: string;
};

type FlatRow = {
  node: AttributionTreeNode;
  depth: number;
  path: string[];
};

function flattenTree(
  nodes: AttributionTreeNode[],
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

// A node's slug `key` is "vendor[/channel[/campaign]]" — split it back into the
// drill-down slug params the API expects (the `__none__` sentinel = NULL bucket).
function keyToNodeFilters(key: string): AttributionNodeFilters {
  const [vendor, channel, campaign] = key.split("/");
  return { vendor, channel, campaign, limit: PAGE_SIZE };
}

export default function AttributionPage() {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [drill, setDrill] = useState<DrillTarget | null>(null);
  const [offset, setOffset] = useState(0);
  const [period, setPeriod] = useState(""); // "" = all time; "YYYY-MM" = a month

  const tree = useAttributionTree(period || undefined);

  const drillFilters: AttributionNodeFilters | null = drill
    ? { ...keyToNodeFilters(drill.key), offset, period: period || undefined }
    : null;
  const leads = useAttributionNodeLeads(drillFilters);

  const rows = useMemo(
    () => (tree.data ? flattenTree(tree.data.nodes, expanded) : []),
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
    setDrill({ key: row.node.key, label: row.path.join(" › ") });
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-start justify-between gap-3">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <GitBranch className="h-6 w-6" />
            Source attribution
          </h1>
          <AttributionDocsDialog />
        </div>
        <p className="text-sm text-muted-foreground">
          Every lead&apos;s resolved origin as a distribution chain (vendor ›
          channel › campaign) with funnel counts — leads, consultations
          scheduled and attended, and collected revenue. This replaces the
          dashboard&apos;s &quot;unknown&quot; bucket; the{" "}
          <span className="font-medium">needs review</span> count is the gap
          still to resolve. Click a row to inspect the leads behind it.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-1.5 text-muted-foreground">
              <CalendarRange className="h-4 w-4" />
              Month
              <input
                type="month"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                aria-label="Month filter"
                className="rounded-md border bg-background px-2 py-1 text-sm text-foreground"
              />
              {period ? (
                <button
                  type="button"
                  onClick={() => setPeriod("")}
                  className="text-xs text-primary hover:underline"
                >
                  all time
                </button>
              ) : null}
            </label>
            {tree.data ? (
              <>
                <span className="text-muted-foreground">
                  Leads:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.total_leads.toLocaleString()}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  Scheduled:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.consults_scheduled.toLocaleString()}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  Attended:{" "}
                  <span className="font-medium text-foreground">
                    {tree.data.consults_attended.toLocaleString()}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  Collected:{" "}
                  <span className="font-medium text-foreground">
                    {formatMoney(tree.data.collected_amount)}
                  </span>
                </span>
                <div className="ml-auto flex items-center gap-2">
                  <Badge
                    variant={
                      tree.data.needs_review > 0 ? "destructive" : "outline"
                    }
                    className="flex items-center gap-1"
                  >
                    <TriangleAlert className="h-3.5 w-3.5" />
                    {tree.data.needs_review.toLocaleString()} need review
                  </Badge>
                  <Link
                    href="/settings/tenant?tab=vendors"
                    className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    title="Bind unassigned traffic to vendors in Settings"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    Distribute
                  </Link>
                </div>
              </>
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
              Failed to load attribution. Is the API running?
            </p>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No resolved attribution yet. Run the resolver to populate it.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-2 font-medium">Source</th>
                  <th className="w-24 py-2 pr-2 text-right font-medium">Leads</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Scheduled</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Attended</th>
                  <th className="w-28 py-2 pr-2 text-right font-medium">Collected</th>
                  {period ? (
                    <th className="w-32 py-2 pr-2 text-right font-medium">
                      Cost / CPL
                    </th>
                  ) : null}
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
                        {row.node.level === "vendor" && row.node.color ? (
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full border"
                            style={{ backgroundColor: row.node.color }}
                            aria-hidden
                          />
                        ) : null}
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
                    {period ? (
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        {row.node.cost_per_lead != null ? (
                          <div className="flex flex-col items-end leading-tight">
                            <span>
                              {formatMoney(row.node.cost_per_lead)}
                              <span className="text-[10px] text-muted-foreground">
                                /lead
                              </span>
                            </span>
                            {row.node.monthly_cost != null ? (
                              <span className="text-[10px] text-muted-foreground">
                                {formatMoney(row.node.monthly_cost)}/mo
                              </span>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    ) : null}
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
                    <th className="py-2 pr-2 font-medium">Resolved</th>
                    <th className="py-2 pr-2 font-medium">Person</th>
                    <th className="py-2 pr-2 font-medium">How</th>
                    <th className="py-2 pr-2 font-medium">Created by</th>
                    <th className="py-2 text-right font-medium">Collected</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.data.items.map((item) => (
                    <tr
                      key={item.person_uid}
                      className="border-b border-border/50 align-top"
                    >
                      <td className="whitespace-nowrap py-1.5 pr-2 tabular-nums">
                        {formatDateTime(item.resolved_at)}
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
                        </div>
                      </td>
                      <td className="py-1.5 pr-2">
                        <div className="flex flex-col gap-0.5">
                          <Badge variant="outline" className="w-fit">
                            {item.source_signal ?? item.method}
                          </Badge>
                          {item.method === "manual" ? (
                            <span className="text-[10px] uppercase text-muted-foreground">
                              manual
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-1.5 pr-2">
                        {item.created_by_name ?? "—"}
                      </td>
                      <td className="py-1.5 text-right tabular-nums">
                        {formatMoney(item.collected_amount)}
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
              No leads in this bucket.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
