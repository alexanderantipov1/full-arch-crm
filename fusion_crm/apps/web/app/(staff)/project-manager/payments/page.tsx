"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Receipt,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  DashboardPmPaymentFilters,
  useDashboardPmPaymentGroups,
  useDashboardPmPayments,
  useDashboardPmPaymentsSummary,
} from "@/lib/api/hooks/useDashboard";
import { useRawEvent } from "@/lib/api/hooks/useInspector";
import { useLeadSourceTree } from "@/lib/api/hooks/useLeadSources";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import type {
  DashboardPmPayment,
  DashboardPmPaymentGroup,
  LeadSourceNode,
} from "@/lib/api/schemas";
import { formatCurrency as formatCurrencyShared, formatDateTime } from "@/lib/utils";

type PaymentDraftFilters = {
  from: string;
  to: string;
  location_id: string;
  source_provider: "" | "salesforce" | "carestack";
  q: string;
  // ENG-408: one lead-source explorer node, JSON-encoded
  // {channel?, source?, medium?, campaign?}. "" = all resources.
  lead_node: string;
};

type LeadSourceNodeValue = {
  channel?: string;
  source?: string;
  medium?: string;
  campaign?: string;
};

const PAGE_SIZE = 100;

function defaultDraft(): PaymentDraftFilters {
  // Default window: last 30 days, inclusive of "today". Mirrors the spec's
  // "filter bar (date window default last 30 days)" requirement.
  const today = new Date();
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - 30);
  return {
    from: start.toISOString().slice(0, 10),
    to: today.toISOString().slice(0, 10),
    location_id: "",
    source_provider: "",
    q: "",
    lead_node: "",
  };
}

function nextDayStartIso(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString();
}

// Same presets as the lead-sources explorer (ENG-399). "" = Custom — shown
// when the operator edits the date inputs by hand.
const PERIOD_PRESETS = [
  { value: "all", label: "All time", days: null },
  { value: "7", label: "Last 7 days", days: 7 },
  { value: "30", label: "Last 30 days", days: 30 },
  { value: "90", label: "Last 90 days", days: 90 },
  { value: "365", label: "Last 12 months", days: 365 },
] as const;

function presetDraft(days: number | null): Pick<PaymentDraftFilters, "from" | "to"> {
  if (days === null) return { from: "", to: "" };
  const today = new Date();
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - days);
  return {
    from: start.toISOString().slice(0, 10),
    to: today.toISOString().slice(0, 10),
  };
}

function draftToFilters(draft: PaymentDraftFilters): DashboardPmPaymentFilters {
  const next: DashboardPmPaymentFilters = { limit: PAGE_SIZE };
  if (draft.from) next.from = `${draft.from}T00:00:00Z`;
  if (draft.to) next.to = nextDayStartIso(draft.to);
  if (draft.source_provider) next.source_provider = draft.source_provider;
  if (draft.location_id.trim()) next.location_id = draft.location_id.trim();
  if (draft.q.trim()) next.q = draft.q.trim();
  if (draft.lead_node) {
    try {
      const node = JSON.parse(draft.lead_node) as LeadSourceNodeValue;
      if (node.channel) next.lead_channel = node.channel;
      if (node.source) next.lead_source = node.source;
      if (node.medium) next.lead_medium = node.medium;
      if (node.campaign) next.lead_campaign = node.campaign;
    } catch {
      // Malformed option value — treat as "all resources".
    }
  }
  return next;
}

type SourceNodeOption = { value: string; label: string };

// Flatten the explorer tree into indented <option> rows. The node params are
// rebuilt from the ancestor labels during the walk (the API `key` joins
// labels with "/" which is ambiguous when a label itself contains "/").
function flattenSourceOptions(nodes: LeadSourceNode[]): SourceNodeOption[] {
  const out: SourceNodeOption[] = [];
  const walk = (
    node: LeadSourceNode,
    depth: number,
    path: LeadSourceNodeValue,
  ) => {
    const next: LeadSourceNodeValue = { ...path };
    if (node.level === "channel") next.channel = node.label;
    else if (node.level === "source") next.source = node.label;
    else if (node.level === "medium") next.medium = node.label;
    else if (node.level === "campaign") next.campaign = node.label;
    out.push({
      value: JSON.stringify(next),
      label: `${"\u00A0".repeat(depth * 3)}${node.label} (${node.leads.toLocaleString()})`,
    });
    for (const child of node.children) walk(child, depth + 1, next);
  };
  for (const node of nodes) walk(node, 0, {});
  return out;
}

/** Debounce a value by `delay` ms — keeps free-text search from firing a
 * request per keystroke now that filters auto-apply (ENG-408). */
function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function ProjectManagerPaymentsPage() {
  const [draft, setDraft] = useState<PaymentDraftFilters>(defaultDraft);
  // ENG-283 / ENG-301: `payment_applied` rows are the offsetting allocation
  // leg of CareStack's double-entry ledger, not new money. They are now
  // EXCLUDED at the API by default (so a page is real cash movements, not
  // ~9:1 allocation noise). The toggle opts them back in via
  // `include_applied` so a PM can audit how recorded payments were applied
  // to invoices.
  const [includeApplied, setIncludeApplied] = useState(false);
  // ENG-410: CareStack splits one real-world payment into per-invoice legs;
  // grouped view (default) collapses them per person per clinic day with
  // expandable legs. Toggle off for the flat per-leg list.
  const [grouped, setGrouped] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    () => new Set(),
  );
  const [offset, setOffset] = useState(0);
  // Default draft is last-30-days, so the dropdown starts on "30".
  const [period, setPeriod] = useState<string>("30");
  // ENG-408: filters auto-apply on change — no Apply button. Free-text
  // search debounces so typing does not fire a request per keystroke;
  // selects and dates apply instantly.
  const debouncedQ = useDebounced(draft.q, 400);
  const baseFilters = useMemo<DashboardPmPaymentFilters>(
    () => draftToFilters({ ...draft, q: debouncedQ }),
    [draft, debouncedQ],
  );
  // Any change to what's in scope restarts pagination at page 1.
  const baseFiltersKey = JSON.stringify(baseFilters);
  useEffect(() => {
    setOffset(0);
  }, [baseFiltersKey]);
  const filters = useMemo<DashboardPmPaymentFilters>(
    () => ({
      ...baseFilters,
      include_applied: includeApplied || undefined,
      offset: offset || undefined,
    }),
    [baseFilters, includeApplied, offset],
  );
  const flatQuery = useDashboardPmPayments(filters, { enabled: !grouped });
  const groupQuery = useDashboardPmPaymentGroups(filters, { enabled: grouped });
  const data = grouped ? groupQuery.data : flatQuery.data;
  const isLoading = grouped ? groupQuery.isLoading : flatQuery.isLoading;
  const error = grouped ? groupQuery.error : flatQuery.error;
  // Window-wide totals — same applied window as the list, aggregated over the
  // whole range (not the page). Drives the summary bar (ENG-302).
  const { data: summary, isLoading: summaryLoading } =
    useDashboardPmPaymentsSummary(baseFilters);
  const { data: tenantData } = useCurrentTenant();
  // ENG-408 resource filter options: the same hierarchy the Lead Sources
  // explorer renders (channel → source → medium → campaign), unwindowed —
  // the node scopes WHO paid; the period scopes WHEN they paid.
  const { data: sourceTree } = useLeadSourceTree({});
  const sourceOptions = useMemo(
    () => flattenSourceOptions(sourceTree?.sources ?? []),
    [sourceTree],
  );
  const locationOptions = useMemo(() => {
    const list = tenantData?.locations ?? [];
    return [...list].sort((a, b) => {
      const an = a.short_name ?? a.name ?? "";
      const bn = b.short_name ?? b.name ?? "";
      return an.localeCompare(bn);
    });
  }, [tenantData]);
  const [selectedRawId, setSelectedRawId] = useState<string | null>(null);

  function resetFilters() {
    setDraft(defaultDraft());
    setPeriod("30");
  }

  function applyPeriodPreset(value: string) {
    setPeriod(value);
    const preset = PERIOD_PRESETS.find((p) => p.value === value);
    if (!preset) return; // "Custom" — keep the dates as typed.
    setDraft((v) => ({ ...v, ...presetDraft(preset.days) }));
  }

  function toggleApplied(checked: boolean) {
    // Changing what's in scope changes pagination — go back to page 1.
    setIncludeApplied(checked);
    setOffset(0);
  }

  function toggleGrouped(checked: boolean) {
    setGrouped(checked);
    setExpandedGroups(new Set());
    setOffset(0);
  }

  function toggleGroupExpanded(key: string) {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // The API already excludes `payment_applied` unless `include_applied` is
  // on, so the page rows are exactly what we render — no client-side filter.
  const flatRows = useMemo(
    () => flatQuery.data?.items ?? [],
    [flatQuery.data?.items],
  );
  const groupRows = useMemo(
    () => groupQuery.data?.items ?? [],
    [groupQuery.data?.items],
  );
  const total = data?.total ?? 0;
  const pageCount = grouped ? groupRows.length : flatRows.length;

  // Sum of the amounts on THIS page. With applied excluded this is the
  // cash-affecting total (recorded + refunded + reversed); when applied is
  // included, allocation amounts add on top to show gross ledger movement.
  const pageTotalAmount = useMemo(
    () =>
      grouped
        ? groupRows.reduce((acc, row) => acc + row.amount, 0)
        : flatRows.reduce((acc, row) => acc + (row.amount ?? 0), 0),
    [grouped, groupRows, flatRows],
  );

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = offset + pageCount;

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-end justify-between">
        <div className="space-y-1">
          <Button asChild variant="ghost" size="sm" className="w-fit px-0">
            <Link href="/project-manager">
              <ArrowLeft className="h-4 w-4" />
              Project Manager
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">Payments</h1>
            <Button
              asChild
              variant="outline"
              size="sm"
              className="h-7 gap-1 text-xs"
            >
              <Link href="/project-manager/payments/docs">
                <BookOpen className="h-3 w-3" />
                Docs
              </Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            CareStack transaction events with raw-payload drilldown.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <label
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            title="Collapse same-day payment legs (one CareStack payment split across invoices) into one row per person per day."
          >
            <input
              type="checkbox"
              className="h-3.5 w-3.5"
              checked={grouped}
              onChange={(event) => toggleGrouped(event.target.checked)}
              aria-label="Group same-day payments per person"
            />
            <span>Group by day</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="h-3.5 w-3.5"
              checked={includeApplied}
              onChange={(event) => toggleApplied(event.target.checked)}
              aria-label="Show applied (allocation) rows"
            />
            <span>Show applied</span>
          </label>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">
              {isLoading
                ? "..."
                : total === 0
                  ? "0 payments"
                  : `${rangeStart}–${rangeEnd} of ${total}`}
            </div>
            <div className="text-sm font-medium">
              {isLoading ? "" : `${formatCurrency(pageTotalAmount)} on page`}
            </div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-3">
        <SummaryTile
          label="Collected"
          hint="Net cash in the selected range (recorded − refunds − reversals)."
          loading={summaryLoading}
          value={
            summary ? formatCurrency(summary.collected_total) : undefined
          }
        />
        <SummaryTile
          label="Payments"
          hint="Number of recorded payments in the selected range."
          loading={summaryLoading}
          value={summary ? summary.payment_count.toLocaleString() : undefined}
        />
        <SummaryTile
          label="Patients"
          hint="Distinct patients who paid in the selected range."
          loading={summaryLoading}
          value={summary ? summary.patient_count.toLocaleString() : undefined}
        />
      </div>

      <form
        onSubmit={(event: FormEvent<HTMLFormElement>) => event.preventDefault()}
        className="grid grid-cols-2 gap-2 rounded-lg border bg-card p-3 xl:grid-cols-8"
      >
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Period</span>
          <NativeSelect
            className="h-8 text-xs"
            value={period}
            onChange={(e) => applyPeriodPreset(e.target.value)}
            aria-label="Period preset"
          >
            <option value="">Custom</option>
            {PERIOD_PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">From</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.from}
            onChange={(e) => {
              setPeriod("");
              setDraft((v) => ({ ...v, from: e.target.value }));
            }}
          />
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">To</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.to}
            onChange={(e) => {
              setPeriod("");
              setDraft((v) => ({ ...v, to: e.target.value }));
            }}
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
                source_provider: e.target.value as PaymentDraftFilters["source_provider"],
              }))
            }
          >
            <option value="">All</option>
            <option value="carestack">CareStack</option>
            <option value="salesforce">Salesforce</option>
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
          <span className="font-medium text-muted-foreground">Source</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.lead_node}
            onChange={(e) =>
              setDraft((v) => ({ ...v, lead_node: e.target.value }))
            }
            aria-label="Lead source resource"
          >
            <option value="">All resources</option>
            {sourceOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Search</span>
          <span className="relative block">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-8 pl-7 text-xs"
              value={draft.q}
              onChange={(e) => setDraft((v) => ({ ...v, q: e.target.value }))}
              placeholder="Name or external id"
            />
          </span>
        </label>
        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-full text-xs"
            onClick={resetFilters}
          >
            Reset
          </Button>
        </div>
      </form>

      {error && (
        <p className="text-sm text-destructive">Failed to load payments.</p>
      )}

      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="grid grid-cols-[1.3fr_0.9fr_0.8fr_0.7fr_0.6fr_0.8fr_0.9fr_0.9fr_0.8fr_0.8fr_0.5fr] gap-0 border-b bg-muted/40 px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Person</span>
          <span>Source</span>
          <span>Owner</span>
          <span className="text-right">Amount</span>
          <span>Type</span>
          <span>Operation</span>
          <span>Doctor</span>
          <span>Date</span>
          <span>Invoice</span>
          <span>Location</span>
          <span className="text-right">Raw</span>
        </div>

        {isLoading && (
          <div className="space-y-1 p-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}

        {!isLoading && pageCount === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No payment transactions in this window.
          </p>
        )}

        {!isLoading &&
          !grouped &&
          flatRows.map((row) => (
            <PaymentRow
              key={row.id}
              row={row}
              onViewRaw={() => setSelectedRawId(row.raw_event_id ?? null)}
            />
          ))}

        {!isLoading &&
          grouped &&
          groupRows.map((group) => {
            const key = `${group.person_uid}|${group.kind}|${group.day}`;
            // A single leg IS the payment — render it as a plain row.
            if (group.leg_count === 1 && group.legs[0]) {
              const leg = group.legs[0];
              return (
                <PaymentRow
                  key={key}
                  row={leg}
                  onViewRaw={() => setSelectedRawId(leg.raw_event_id ?? null)}
                />
              );
            }
            return (
              <PaymentGroupRow
                key={key}
                group={group}
                expanded={expandedGroups.has(key)}
                onToggle={() => toggleGroupExpanded(key)}
                onViewRaw={(leg) => setSelectedRawId(leg.raw_event_id ?? null)}
              />
            );
          })}
      </div>

      {!isLoading && total > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Showing {rangeStart}–{rangeEnd} of {total}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              disabled={!data?.has_previous}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
              disabled={!data?.has_next}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <RawPayloadDialog
        eventId={selectedRawId}
        onClose={() => setSelectedRawId(null)}
      />
    </div>
  );
}

function OperationCell({ row }: { row: DashboardPmPayment }) {
  // ENG-547: operation/procedure this payment was for. Resolved from the
  // accounting-transaction's procedureCodeId; absent for advances / unallocated
  // legs / adjustments (direct transaction fields only).
  if (!row.operation_code) {
    return <div className="text-muted-foreground">—</div>;
  }
  return (
    <div className="min-w-0 pr-2">
      <div
        className="truncate font-mono font-medium"
        title={
          row.operation_description
            ? `${row.operation_code} · ${row.operation_description}`
            : row.operation_code
        }
      >
        {row.operation_code}
      </div>
      {row.operation_description && (
        <div className="truncate text-[10px] text-muted-foreground">
          {row.operation_description}
        </div>
      )}
    </div>
  );
}

function InvoiceCell({ row }: { row: DashboardPmPayment }) {
  // No invoice linked to this payment leg.
  if (!row.invoice_id) {
    return <div className="text-muted-foreground">—</div>;
  }
  const label = row.invoice_number ? `#${row.invoice_number}` : row.invoice_id;
  return (
    <div className="min-w-0">
      <div
        className="truncate font-medium"
        title={`Invoice id ${row.invoice_id}`}
      >
        {label}
      </div>
      <div className="text-[10px] text-muted-foreground">
        {row.invoice_date ? formatInvoiceDate(row.invoice_date) : "—"}
      </div>
    </div>
  );
}

function SummaryTile({
  label,
  hint,
  value,
  loading,
}: {
  label: string;
  hint: string;
  value: string | undefined;
  loading: boolean;
}) {
  return (
    <div className="rounded-lg border bg-card p-3" title={hint}>
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      {loading || value === undefined ? (
        <Skeleton className="mt-1 h-7 w-24" />
      ) : (
        <div className="mt-0.5 text-2xl font-semibold tabular-nums">
          {value}
        </div>
      )}
    </div>
  );
}

function PaymentRow({
  row,
  onViewRaw,
}: {
  row: DashboardPmPayment;
  onViewRaw: () => void;
}) {
  return (
    <div className="grid grid-cols-[1.3fr_0.9fr_0.8fr_0.7fr_0.6fr_0.8fr_0.9fr_0.9fr_0.8fr_0.8fr_0.5fr] items-center gap-0 border-b px-3 py-2 text-xs last:border-b-0 hover:bg-muted/30">
      <div>
        <div className="flex items-center gap-1.5">
          <Link
            href={`/persons/${row.person_uid}`}
            className="text-sm font-medium text-primary hover:underline"
          >
            {row.display_name}
          </Link>
          <BalancePill balance={row.balance ?? null} />
        </div>
        {row.source_external_id && (
          <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
            {row.source_external_id}
          </div>
        )}
      </div>
      <div
        className="truncate pr-2 text-muted-foreground"
        title={row.lead_source_label ?? undefined}
      >
        {row.lead_source_label ?? "—"}
      </div>
      <div
        className="truncate pr-2 text-muted-foreground"
        title={row.lead_owner ?? undefined}
      >
        {row.lead_owner ?? "—"}
      </div>
      <div className={`text-right font-medium ${amountColor(row.kind)}`}>
        {row.amount === null || row.amount === undefined
          ? "—"
          : formatCurrency(row.amount)}
      </div>
      <div>
        <Badge variant="outline" className={`text-[10px] ${kindBadge(row.kind)}`}>
          {kindLabel(row.kind)}
        </Badge>
      </div>
      <OperationCell row={row} />
      <div className="truncate text-muted-foreground" title={row.doctor_name ?? undefined}>
        {row.doctor_name ?? "—"}
      </div>
      <div className="text-muted-foreground">
        {formatDateTime(row.occurred_at)}
      </div>
      <InvoiceCell row={row} />
      <div className="truncate text-muted-foreground" title={row.location_name ?? undefined}>
        {row.location_name ?? "—"}
      </div>
      <div className="text-right">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={onViewRaw}
          disabled={!row.raw_event_id}
          aria-label={`View raw payload for ${row.display_name}`}
        >
          <Receipt className="h-3 w-3" />
          View raw
        </Button>
      </div>
    </div>
  );
}

function PaymentGroupRow({
  group,
  expanded,
  onToggle,
  onViewRaw,
}: {
  group: DashboardPmPaymentGroup;
  expanded: boolean;
  onToggle: () => void;
  onViewRaw: (leg: DashboardPmPayment) => void;
}) {
  // Distinct per-leg facets roll up into a count when they differ.
  const invoiceNumbers = Array.from(
    new Set(
      group.legs
        .map((leg) => leg.invoice_number ?? leg.invoice_id)
        .filter((v): v is string => Boolean(v)),
    ),
  );
  const locations = Array.from(
    new Set(group.legs.map((leg) => leg.location_name).filter(Boolean)),
  );
  // ENG-547: distinct operation codes / doctors across the group's legs roll
  // up into a count when they differ (mirrors the invoice/location facets).
  const operationCodes = Array.from(
    new Set(
      group.legs
        .map((leg) => leg.operation_code)
        .filter((v): v is string => Boolean(v)),
    ),
  );
  const doctors = Array.from(
    new Set(
      group.legs
        .map((leg) => leg.doctor_name)
        .filter((v): v is string => Boolean(v)),
    ),
  );
  return (
    <div className="border-b last:border-b-0">
      <div
        className="grid cursor-pointer grid-cols-[1.3fr_0.9fr_0.8fr_0.7fr_0.6fr_0.8fr_0.9fr_0.9fr_0.8fr_0.8fr_0.5fr] items-center gap-0 px-3 py-2 text-xs hover:bg-muted/30"
        onClick={onToggle}
        role="button"
        aria-expanded={expanded}
        aria-label={`Toggle ${group.leg_count} payment legs for ${group.display_name} on ${group.day}`}
      >
        <div>
          <div className="flex items-center gap-1.5">
            <Link
              href={`/persons/${group.person_uid}`}
              className="text-sm font-medium text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {group.display_name}
            </Link>
            <BalancePill balance={group.balance ?? null} />
          </div>
          <div className="mt-0.5 text-[10px] text-muted-foreground">
            {group.leg_count} legs · same day
          </div>
        </div>
        <div
          className="truncate pr-2 text-muted-foreground"
          title={group.lead_source_label ?? undefined}
        >
          {group.lead_source_label ?? "—"}
        </div>
        <div
          className="truncate pr-2 text-muted-foreground"
          title={group.lead_owner ?? undefined}
        >
          {group.lead_owner ?? "—"}
        </div>
        <div className={`text-right font-semibold ${amountColor(group.kind)}`}>
          {formatCurrency(group.amount)}
        </div>
        <div>
          <Badge
            variant="outline"
            className={`text-[10px] ${kindBadge(group.kind)}`}
          >
            {kindLabel(group.kind)} ×{group.leg_count}
          </Badge>
        </div>
        <div
          className="truncate pr-2 font-mono text-muted-foreground"
          title={operationCodes.join(", ") || undefined}
        >
          {operationCodes.length === 0
            ? "—"
            : operationCodes.length === 1
              ? operationCodes[0]
              : `${operationCodes.length} codes`}
        </div>
        <div
          className="truncate pr-2 text-muted-foreground"
          title={doctors.join(", ") || undefined}
        >
          {doctors.length === 0
            ? "—"
            : doctors.length === 1
              ? doctors[0]
              : `${doctors.length} doctors`}
        </div>
        <div className="text-muted-foreground">
          {formatInvoiceDate(group.day)}
        </div>
        <div className="truncate text-muted-foreground">
          {invoiceNumbers.length === 0
            ? "—"
            : invoiceNumbers.length === 1
              ? `#${invoiceNumbers[0]}`
              : `${invoiceNumbers.length} invoices`}
        </div>
        <div
          className="truncate text-muted-foreground"
          title={locations.join(", ") || undefined}
        >
          {locations.length === 0
            ? "—"
            : locations.length === 1
              ? locations[0]
              : `${locations.length} locations`}
        </div>
        <div className="flex justify-end text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </div>
      </div>
      {expanded && (
        <div className="border-l-2 border-primary/30 bg-muted/20 pl-2">
          {group.legs.map((leg) => (
            <PaymentRow
              key={leg.id}
              row={leg}
              onViewRaw={() => onViewRaw(leg)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RawPayloadDialog({
  eventId,
  onClose,
}: {
  eventId: string | null;
  onClose: () => void;
}) {
  const { data, isLoading, error } = useRawEvent(eventId);
  return (
    <Dialog open={Boolean(eventId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Raw payload</DialogTitle>
          <DialogDescription>
            Verbatim {data?.provider ?? "provider"} payload — local dev only.
          </DialogDescription>
        </DialogHeader>
        {isLoading && <Skeleton className="h-48 w-full" />}
        {error && (
          <p className="text-sm text-destructive">Failed to load raw event.</p>
        )}
        {!isLoading && data && (
          <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
            {JSON.stringify(data.payload, null, 2)}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  );
}

function BalancePill({ balance }: { balance: number | null }) {
  // ENG-306: surfaces the authoritative latest payment-summary balance
  // next to the patient name. ``null`` (no snapshot captured yet) → "—"
  // so the operator never reads "$0" as proof the account is paid up.
  const label = balance === null ? "—" : formatCurrencyShared(balance);
  const titleText =
    balance === null
      ? "No balance snapshot captured yet"
      : `Outstanding balance: ${label}`;
  return (
    <Badge
      variant="outline"
      className="border-amber-400/50 bg-amber-50/40 px-1.5 py-0 text-[10px] font-medium tabular-nums text-amber-700"
      title={titleText}
      aria-label={titleText}
    >
      {label}
    </Badge>
  );
}

function formatInvoiceDate(isoDate: string): string {
  // invoice_date is a plain YYYY-MM-DD (no time/zone). Render it stably as a
  // local date without constructing a Date (which would shift across TZs).
  const [year, month, day] = isoDate.split("-");
  if (!year || !month || !day) return isoDate;
  const MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const monthLabel = MONTHS[Number(month) - 1] ?? month;
  return `${monthLabel} ${Number(day)}, ${year}`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function amountColor(kind: DashboardPmPayment["kind"]): string {
  if (kind === "payment_refunded" || kind === "payment_reversed") {
    return "text-red-600";
  }
  if (kind === "payment_applied") return "text-muted-foreground";
  return "text-emerald-700";
}

function kindBadge(kind: DashboardPmPayment["kind"]): string {
  if (kind === "payment_refunded") return "border-amber-400/50 text-amber-700";
  if (kind === "payment_reversed") return "border-red-400/50 text-red-700";
  if (kind === "payment_applied") return "border-slate-400/50 text-slate-600";
  return "border-emerald-400/50 text-emerald-700";
}

function kindLabel(kind: DashboardPmPayment["kind"]): string {
  switch (kind) {
    case "payment_recorded":
      return "Payment";
    case "payment_applied":
      return "Applied";
    case "payment_refunded":
      return "Refund";
    case "payment_reversed":
      return "Reversal";
  }
}
