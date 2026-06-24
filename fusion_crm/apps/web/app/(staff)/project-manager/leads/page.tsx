"use client";

import { Fragment, FormEvent, ReactNode, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronDown, ChevronRight, Filter, Search } from "lucide-react";
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
  DashboardPmLeadFilters,
  useDashboardPmLeads,
  useDashboardPmLeadSources,
} from "@/lib/api/hooks/useDashboard";
import type {
  DashboardPmLeadList,
  DashboardPmLeadLocationTab,
  DashboardPmLeadSort,
} from "@/lib/api/schemas";
import { formatDateTime, formatRelative } from "@/lib/utils";

// Location tabs (ENG-561). The values match the backend `location_tab` query
// param exactly; "all"/"linked" are the non-location tabs that omit the param.
type LeadTab = "all" | "linked" | DashboardPmLeadLocationTab;

const LOCATION_TABS: { value: DashboardPmLeadLocationTab; label: string }[] = [
  { value: "galleria", label: "Galleria" },
  { value: "fusion", label: "Fusion" },
  { value: "el_dorado", label: "El Dorado" },
  { value: "cosmo", label: "Cosmo" },
];

type LeadDraftFilters = {
  from: string;
  to: string;
  status: string;
  // Encoded Source dropdown value: "" (all), "provider:<provider>" for a
  // whole provider, or "source:<value>" for one lead-source bucket.
  source: string;
  q: string;
};

// Server-side filters shared by both provider columns on the "All leads"
// tab. Each column adds its own `source_provider` + offset on top of this.
// `linked_only` is intentionally NOT part of this shape — the two tabs run
// independent queries so they never fight over a single filter object.
type SharedLeadFilters = {
  from?: string;
  to?: string;
  status?: string;
  lead_source?: string;
  lead_source_match?: "exact";
  source_provider?: "salesforce" | "carestack";
  q?: string;
};

const DEFAULT_DRAFT: LeadDraftFilters = {
  from: "",
  to: "",
  status: "",
  source: "",
  q: "",
};

const PROVIDER_OPTION_PREFIX = "provider:";
const SOURCE_OPTION_PREFIX = "source:";

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
  "new",
  "qualified",
  "contacted",
  "booked",
  "lost",
  "scheduled",
  "completed",
  "cancelled",
  "rescheduled",
  "no_show",
  "carestack_patient",
];

export default function ProjectManagerLeadsPage() {
  // Default tab is "galleria" (ENG-561): the page opens on the primary clinic
  // location so operators land on the most-used tab without a click.
  const [activeTab, setActiveTab] = useState<LeadTab>("galleria");
  const [draft, setDraft] = useState<LeadDraftFilters>(DEFAULT_DRAFT);

  // Applied (server-side) filters shared by both provider columns.
  const [sharedFilters, setSharedFilters] = useState<SharedLeadFilters>({});

  // Source dropdown options grouped by provider (with row counts).
  const sourcesQuery = useDashboardPmLeadSources();

  // Independent per-provider pagination on the "All leads" tab. Each column
  // has its own offset so the 62k SF leads and 55k CareStack leads page
  // through independently — fixing the old "12 SF rows per page" bug.
  const [sfOffset, setSfOffset] = useState(0);
  const [csOffset, setCsOffset] = useState(0);

  // Linked tab keeps a single offset + query.
  const [linkedOffset, setLinkedOffset] = useState(0);

  // Location tabs share one offset (only one is active at a time; switching
  // tabs resets it via selectTab).
  const [locationOffset, setLocationOffset] = useState(0);

  // Location-tab ordering. Default "lead" (funnel date). Clicking the CareStack
  // column header flips to "appointment" (most recently booked first).
  const [locationSort, setLocationSort] = useState<DashboardPmLeadSort>("lead");

  function selectLocationSort(next: DashboardPmLeadSort) {
    setLocationSort(next);
    setLocationOffset(0);
  }

  const isAllTab = activeTab === "all";
  const isLinkedTab = activeTab === "linked";
  // The active location tab value (galleria | fusion | el_dorado | cosmo), or
  // undefined when on the "all"/"linked" tabs. Doubles as the request param.
  const locationTab = LOCATION_TABS.find((t) => t.value === activeTab)?.value;
  const isLocationTab = locationTab !== undefined;

  // A provider-level Source selection narrows the "All leads" tab to that
  // provider's column; the other column is hidden instead of querying with
  // a contradictory provider filter.
  const providerFilter = sharedFilters.source_provider;
  const showSfColumn = providerFilter !== "carestack";
  const showCsColumn = providerFilter !== "salesforce";

  const sfQuery = useDashboardPmLeads(
    {
      ...sharedFilters,
      source_provider: "salesforce",
      limit: PAGE_SIZE,
      offset: sfOffset,
    },
    { enabled: isAllTab && showSfColumn },
  );

  const csQuery = useDashboardPmLeads(
    {
      ...sharedFilters,
      source_provider: "carestack",
      limit: PAGE_SIZE,
      offset: csOffset,
    },
    { enabled: isAllTab && showCsColumn },
  );

  const linkedQuery = useDashboardPmLeads(
    {
      ...sharedFilters,
      linked_only: true,
      limit: PAGE_SIZE,
      offset: linkedOffset,
    },
    { enabled: isLinkedTab },
  );

  // One query for whichever location tab is active. `location_tab` is the only
  // server-side semantic — the page just selects the param and renders the
  // returned persons as unified cards.
  const locationQuery = useDashboardPmLeads(
    {
      ...sharedFilters,
      location_tab: locationTab,
      sort: locationSort,
      limit: PAGE_SIZE,
      offset: locationOffset,
    },
    { enabled: isLocationTab },
  );

  function selectTab(tab: LeadTab) {
    setActiveTab(tab);
    // Reset all offsets so switching tabs starts each view at page 1.
    setSfOffset(0);
    setCsOffset(0);
    setLinkedOffset(0);
    setLocationOffset(0);
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: SharedLeadFilters = {};
    if (draft.from) next.from = `${draft.from}T00:00:00Z`;
    if (draft.to) next.to = nextDayStartIso(draft.to);
    if (draft.status) next.status = draft.status;
    if (draft.source.startsWith(PROVIDER_OPTION_PREFIX)) {
      next.source_provider = draft.source.slice(
        PROVIDER_OPTION_PREFIX.length,
      ) as "salesforce" | "carestack";
    } else if (draft.source.startsWith(SOURCE_OPTION_PREFIX)) {
      // Dropdown values are exact bucket labels; exact match keeps the
      // result count equal to the count shown next to the option.
      next.lead_source = draft.source.slice(SOURCE_OPTION_PREFIX.length);
      next.lead_source_match = "exact";
    }
    if (draft.q.trim()) next.q = draft.q.trim();
    // Applying filters resets every column to page 1.
    setSfOffset(0);
    setCsOffset(0);
    setLinkedOffset(0);
    setLocationOffset(0);
    setSharedFilters(next);
  }

  function resetFilters() {
    setDraft(DEFAULT_DRAFT);
    setSfOffset(0);
    setCsOffset(0);
    setLinkedOffset(0);
    setLocationOffset(0);
    setSharedFilters({});
  }

  // Window-wide totals for the header. On the All tab the two providers don't
  // share a total, so sum each column's authoritative `total`.
  const headerTotal = useMemo(() => {
    if (isAllTab) {
      const sf = showSfColumn ? (sfQuery.data?.total ?? 0) : 0;
      const cs = showCsColumn ? (csQuery.data?.total ?? 0) : 0;
      return sf + cs;
    }
    if (isLocationTab) {
      return locationQuery.data?.total ?? 0;
    }
    return linkedQuery.data?.total ?? 0;
  }, [
    isAllTab,
    isLocationTab,
    showSfColumn,
    showCsColumn,
    sfQuery.data?.total,
    csQuery.data?.total,
    linkedQuery.data?.total,
    locationQuery.data?.total,
  ]);

  const headerLoading = isAllTab
    ? (showSfColumn && sfQuery.isLoading) || (showCsColumn && csQuery.isLoading)
    : isLocationTab
      ? locationQuery.isLoading
      : linkedQuery.isLoading;

  const anyError = isAllTab
    ? Boolean(
        (showSfColumn && sfQuery.error) || (showCsColumn && csQuery.error),
      )
    : isLocationTab
      ? Boolean(locationQuery.error)
      : Boolean(linkedQuery.error);

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
          <h1 className="text-xl font-semibold">Leads</h1>
        </div>
        <span className="text-sm text-muted-foreground">
          {headerLoading ? "..." : `${headerTotal} total`}
        </span>
      </header>

      <form
        onSubmit={applyFilters}
        className="grid grid-cols-2 gap-2 rounded-lg border bg-card p-3 xl:grid-cols-7"
      >
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">From</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.from}
            onChange={(e) =>
              setDraft((v) => ({ ...v, from: e.target.value }))
            }
          />
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">To</span>
          <Input
            type="date"
            className="h-8 text-xs"
            value={draft.to}
            onChange={(e) =>
              setDraft((v) => ({ ...v, to: e.target.value }))
            }
          />
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Status</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.status}
            onChange={(e) =>
              setDraft((v) => ({ ...v, status: e.target.value }))
            }
          >
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-0.5 text-xs">
          <span className="font-medium text-muted-foreground">Source</span>
          <NativeSelect
            className="h-8 text-xs"
            value={draft.source}
            onChange={(e) =>
              setDraft((v) => ({ ...v, source: e.target.value }))
            }
          >
            <option value="">All</option>
            {(sourcesQuery.data?.providers ?? []).map((provider) => (
              <optgroup
                key={provider.provider}
                label={
                  provider.provider === "salesforce" ? "Salesforce" : "CareStack"
                }
              >
                <option value={`${PROVIDER_OPTION_PREFIX}${provider.provider}`}>
                  All{" "}
                  {provider.provider === "salesforce"
                    ? "Salesforce"
                    : "CareStack"}{" "}
                  ({provider.total.toLocaleString()})
                </option>
                {provider.sources.map((bucket) => (
                  <option
                    key={bucket.key}
                    value={`${SOURCE_OPTION_PREFIX}${bucket.key}`}
                  >
                    {bucket.key === "unknown" ? "No source" : bucket.key} (
                    {bucket.count.toLocaleString()})
                  </option>
                ))}
              </optgroup>
            ))}
          </NativeSelect>
        </label>
        <label className="col-span-2 space-y-0.5 text-xs xl:col-span-2">
          <span className="font-medium text-muted-foreground">Search</span>
          <span className="relative block">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-8 pl-7 text-xs"
              value={draft.q}
              onChange={(e) =>
                setDraft((v) => ({ ...v, q: e.target.value }))
              }
              placeholder="Name, phone, email"
            />
          </span>
        </label>
        <div className="flex items-end gap-2">
          <Button type="submit" size="sm" className="h-8 gap-1 text-xs">
            <Filter className="h-3 w-3" />
            Filter
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={resetFilters}
          >
            Reset
          </Button>
        </div>
      </form>

      {anyError && (
        <p className="text-sm text-destructive">Failed to load leads.</p>
      )}

      <div className="flex items-center justify-between">
        <div className="inline-flex flex-wrap gap-0.5 rounded-md border bg-background p-0.5">
          <TabButton active={isAllTab} onClick={() => selectTab("all")}>
            All leads
          </TabButton>
          <TabButton active={isLinkedTab} onClick={() => selectTab("linked")}>
            Linked SF + CareStack
          </TabButton>
          {LOCATION_TABS.map((tab) => (
            <TabButton
              key={tab.value}
              active={activeTab === tab.value}
              onClick={() => selectTab(tab.value)}
            >
              {tab.label}
            </TabButton>
          ))}
        </div>
      </div>

      {isAllTab ? (
        <div
          className={`grid grid-cols-1 gap-4 ${
            showSfColumn && showCsColumn ? "lg:grid-cols-2" : ""
          }`}
        >
          {showSfColumn && (
            <ProviderColumn
              title="Salesforce"
              accent="blue"
              data={sfQuery.data}
              isLoading={sfQuery.isLoading}
              offset={sfOffset}
              onOffsetChange={setSfOffset}
              emptyLabel="No Salesforce leads"
            />
          )}
          {showCsColumn && (
            <ProviderColumn
              title="CareStack"
              accent="emerald"
              data={csQuery.data}
              isLoading={csQuery.isLoading}
              offset={csOffset}
              onOffsetChange={setCsOffset}
              emptyLabel="No CareStack leads"
            />
          )}
        </div>
      ) : isLinkedTab ? (
        <>
          <LinkedPersonsView
            items={linkedQuery.data?.items ?? []}
            isLoading={linkedQuery.isLoading}
          />
          <LinkedPagination
            data={linkedQuery.data}
            isLoading={linkedQuery.isLoading}
            offset={linkedOffset}
            onOffsetChange={setLinkedOffset}
          />
        </>
      ) : (
        <>
          <LocationSortHeader sort={locationSort} onSortChange={selectLocationSort} />
          <UnifiedPersonsView
            items={locationQuery.data?.items ?? []}
            isLoading={locationQuery.isLoading}
          />
          <LinkedPagination
            data={locationQuery.data}
            isLoading={locationQuery.isLoading}
            offset={locationOffset}
            onOffsetChange={setLocationOffset}
          />
        </>
      )}
    </div>
  );
}

/** Tab strip button — keeps the active/ghost styling in one place. */
function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "ghost"}
      size="sm"
      className="h-7 text-xs"
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

/**
 * A single provider column on the "All leads" tab. Renders the rows from its
 * own server-filtered query and owns its own Prev/Next pagination bound to the
 * column's offset. The per-column `total` is authoritative (e.g. the SF column
 * shows 62,309 even though only PAGE_SIZE rows are on screen).
 */
function ProviderColumn({
  title,
  accent,
  data,
  isLoading,
  offset,
  onOffsetChange,
  emptyLabel,
}: {
  title: string;
  accent: "blue" | "emerald";
  data: DashboardPmLeadList | undefined;
  isLoading: boolean;
  offset: number;
  onOffsetChange: (next: number) => void;
  emptyLabel: string;
}) {
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const titleClass = accent === "blue" ? "text-blue-700" : "text-emerald-700";
  const borderClass =
    accent === "blue"
      ? "border-blue-400/30 bg-blue-50/30"
      : "border-emerald-400/30 bg-emerald-50/30";

  const pageStart = total > 0 ? offset + 1 : 0;
  const pageEnd = Math.min(offset + items.length, total);

  const hasPrevious = offset > 0;
  const hasNext = offset + items.length < total;

  return (
    <Card className={borderClass}>
      <CardHeader className="pb-2">
        <CardTitle className={`text-sm font-semibold ${titleClass}`}>
          {title}
        </CardTitle>
        <CardDescription className="text-xs">
          {isLoading
            ? "Loading…"
            : total > 0
              ? `Showing ${pageStart}–${pageEnd} of ${total}`
              : "0 leads"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 p-3 pt-0">
        {isLoading &&
          [...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        {!isLoading && items.length === 0 && (
          <p className="py-4 text-center text-xs text-muted-foreground">
            {emptyLabel}
          </p>
        )}
        {!isLoading &&
          items.map((lead) => (
            <LeadRow key={lead.id} lead={lead} accent={accent} />
          ))}

        {(items.length > 0 || hasPrevious) && (
          <div className="flex items-center justify-end gap-1 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() =>
                onOffsetChange(Math.max(0, offset - PAGE_SIZE))
              }
              disabled={isLoading || !hasPrevious}
            >
              Prev
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => onOffsetChange(offset + PAGE_SIZE)}
              disabled={isLoading || !hasNext}
            >
              Next
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LeadRow({
  lead,
  accent,
}: {
  lead: {
    id: string;
    person_uid: string;
    display_name: string;
    email: string | null;
    phone: string | null;
    status: string;
    lead_source: string | null;
    source_external_id: string | null;
    created_at: string;
    updated_at: string;
  };
  accent: "blue" | "emerald";
}) {
  const borderClass =
    accent === "blue"
      ? "border-blue-200/60 hover:bg-blue-50/60"
      : "border-emerald-200/60 hover:bg-emerald-50/60";
  return (
    <div
      className={`rounded-md border bg-white/80 px-3 py-2 transition-colors ${borderClass}`}
    >
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/persons/${lead.person_uid}`}
          className="text-sm font-medium text-primary hover:underline"
        >
          {lead.display_name}
        </Link>
        <Badge variant="outline" className="text-[10px]">
          {lead.status}
        </Badge>
      </div>
      <div className="mt-0.5 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground">
        <span>{lead.email ?? lead.phone ?? "no contact"}</span>
        {lead.lead_source && <span>{lead.lead_source}</span>}
        {lead.source_external_id && (
          <span className="font-mono">{lead.source_external_id}</span>
        )}
      </div>
      <div className="mt-0.5 text-[10px] text-muted-foreground/70">
        {formatDateTime(lead.created_at)} · {formatRelative(lead.updated_at)}
      </div>
    </div>
  );
}

type LeadItem = {
  id: string;
  person_uid: string;
  display_name: string;
  email: string | null;
  phone: string | null;
  status: string;
  lead_source: string | null;
  source_provider: string;
  source_providers?: string[];
  source_external_id: string | null;
  created_at: string;
  updated_at: string;
  consultation_status?: string | null;
  consultation_scheduled_at?: string | null;
  consultation_provider_created_at?: string | null;
  consultation_provider?: string | null;
  location_name?: string | null;
};

function LinkedPagination({
  data,
  isLoading,
  offset,
  onOffsetChange,
}: {
  data: DashboardPmLeadList | undefined;
  isLoading: boolean;
  offset: number;
  onOffsetChange: (next: number) => void;
}) {
  // Linked rows are grouped by person, so the on-screen count is the number of
  // distinct persons on the page; the server `total` remains authoritative.
  const personCount = useMemo(() => {
    if (!data?.items) return 0;
    return new Set(data.items.map((item) => item.person_uid)).size;
  }, [data?.items]);

  const total = data?.total ?? 0;
  const pageStart = total > 0 ? offset + 1 : 0;
  const pageEnd = Math.min(offset + personCount, total);
  const hasPrevious = offset > 0;
  const hasNext = data ? offset + data.items.length < total : false;

  return (
    <div className="flex items-center justify-between rounded-lg border bg-card px-4 py-3">
      <div className="text-sm text-muted-foreground">
        {total > 0 ? `${pageStart}–${pageEnd} of ${total}` : "0 results"}
      </div>
      <div className="flex gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          onClick={() => onOffsetChange(Math.max(0, offset - PAGE_SIZE))}
          disabled={isLoading || !hasPrevious}
        >
          Prev
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          onClick={() => onOffsetChange(offset + PAGE_SIZE)}
          disabled={isLoading || !hasNext}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function LinkedPersonsView({
  items,
  isLoading,
}: {
  items: LeadItem[];
  isLoading: boolean;
}) {
  const grouped = useMemo(() => {
    const map = new Map<
      string,
      { person: LeadItem; sf: LeadItem[]; cs: LeadItem[] }
    >();
    for (const item of items) {
      const existing = map.get(item.person_uid) ?? {
        person: item,
        sf: [],
        cs: [],
      };
      if (item.source_provider === "salesforce") {
        existing.sf.push(item);
      } else {
        existing.cs.push(item);
      }
      map.set(item.person_uid, existing);
    }
    return [...map.values()];
  }, [items]);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[1fr_1fr_1fr] gap-0 rounded-t-md border-b px-2 py-1.5 text-[10px] uppercase text-muted-foreground">
        <span className="font-medium">Person</span>
        <span className="font-medium text-blue-600">Salesforce</span>
        <span className="font-medium text-emerald-600">CareStack</span>
      </div>
      {isLoading &&
        [...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      {grouped.map((g) => {
        const anyItem = g.sf[0] ?? g.cs[0] ?? g.person;
        return (
          <div
            key={g.person.person_uid}
            className="grid grid-cols-[1fr_1fr_1fr] gap-0 rounded-md border transition-colors hover:bg-muted/30"
          >
            {/* Person */}
            <div className="border-r px-4 py-3">
              <Link
                href={`/persons/${g.person.person_uid}`}
                className="text-base font-semibold text-primary hover:underline"
              >
                {g.person.display_name}
              </Link>
              <div className="mt-1 space-y-0.5 text-sm text-muted-foreground">
                {g.person.email && <div>{g.person.email}</div>}
                {g.person.phone && <div>{g.person.phone}</div>}
              </div>
              {anyItem?.location_name && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {anyItem.location_name}
                </div>
              )}
            </div>

            {/* SF column */}
            <div className="border-r bg-blue-50/30 px-4 py-3">
              {g.sf.length === 0 ? (
                <span className="text-sm font-medium text-red-400">
                  No Salesforce lead
                </span>
              ) : (
                g.sf.map((s) => {
                  const sfConsult =
                    s.consultation_provider === "salesforce" && s.consultation_scheduled_at;
                  return (
                    <div key={s.id} className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="border-blue-400/50 bg-blue-50 text-xs text-blue-700"
                        >
                          {s.status}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">
                          {s.source_external_id}
                        </span>
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground">Lead created: </span>
                        <span className="font-medium">{formatDateTime(s.created_at)}</span>
                      </div>
                      {s.lead_source && (
                        <div className="text-sm">
                          <span className="text-muted-foreground">Source: </span>
                          <span>{s.lead_source}</span>
                        </div>
                      )}
                      {sfConsult ? (
                        <div className="text-sm">
                          <span className="text-muted-foreground">SF Event: </span>
                          <Badge variant="outline" className="mr-1 text-[10px]">
                            {s.consultation_status}
                          </Badge>
                          <span className="font-medium">
                            {formatDateTime(s.consultation_scheduled_at!)}
                          </span>
                        </div>
                      ) : (
                        <div className="text-xs text-red-400">
                          No SF Event
                        </div>
                      )}
                      {s.consultation_provider_created_at && (
                        <div className="text-xs text-muted-foreground">
                          Booked: {formatDateTime(s.consultation_provider_created_at)}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* CS column */}
            <div className="bg-emerald-50/30 px-4 py-3">
              {g.cs.length === 0 ? (
                <span className="text-sm font-medium text-red-400">
                  No CareStack patient
                </span>
              ) : (
                g.cs.map((c) => {
                  const csConsult =
                    c.consultation_provider === "carestack" && c.consultation_scheduled_at;
                  return (
                    <div key={c.id} className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="border-emerald-400/50 bg-emerald-50 text-xs text-emerald-700"
                        >
                          {c.status}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">
                          Patient #{c.source_external_id}
                        </span>
                      </div>
                      {c.consultation_provider_created_at && (
                        <div className="text-sm">
                          <span className="text-muted-foreground">Booked: </span>
                          <span className="font-semibold">
                            {formatDateTime(c.consultation_provider_created_at)}
                          </span>
                        </div>
                      )}
                      {csConsult ? (
                        <div className="text-sm">
                          <span className="text-muted-foreground">CS Appt: </span>
                          <Badge variant="outline" className="mr-1 text-[10px]">
                            {c.consultation_status}
                          </Badge>
                          <span className="font-medium">
                            {formatDateTime(c.consultation_scheduled_at!)}
                          </span>
                        </div>
                      ) : (
                        <div className="text-xs text-red-400">
                          No CS Appointment
                        </div>
                      )}
                      {c.location_name && (
                        <div className="text-sm">
                          <span className="text-muted-foreground">Location: </span>
                          <span>{c.location_name}</span>
                        </div>
                      )}
                      <div className="text-[10px] text-muted-foreground/60">
                        Patient since: {formatDateTime(c.created_at)}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        );
      })}
      {!isLoading && grouped.length === 0 && (
        <p className="py-6 text-center text-xs text-muted-foreground">
          No linked leads found.
        </p>
      )}
    </div>
  );
}

// ── Unified person card (ENG-561) ───────────────────────────────────────────
// One card per person merging the Salesforce lead(s) and the linked CareStack
// contact/consultation(s) into a single creation-ordered timeline. Reuses the
// same person grouping as LinkedPersonsView; the location tabs render persons
// this way instead of as two bare provider columns.

type TimelineEvent = {
  key: string;
  time: string;
  provider: "salesforce" | "carestack";
  label: string;
  detail?: string;
  status?: string | null;
};

function buildPersonTimeline(sf: LeadItem[], cs: LeadItem[]): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  for (const s of sf) {
    events.push({
      key: `${s.id}-created`,
      time: s.created_at,
      provider: "salesforce",
      label: "SF lead created",
      detail: s.lead_source ?? undefined,
      status: s.status,
    });
  }

  for (const c of cs) {
    events.push({
      key: `${c.id}-patient`,
      time: c.created_at,
      provider: "carestack",
      label: "CareStack patient since",
      detail: c.location_name ?? undefined,
      status: c.status,
    });
  }

  // The consultation is per-person (the backend attaches the same latest
  // consultation to whichever rows it returns), so render it ONCE — from
  // whichever row carries it — and label it by `consultation_provider`, not by
  // the row's source. Otherwise a CareStack appointment that rides on the SF
  // lead row gets mislabeled "SF event booked" (and never shows as CareStack).
  const consultRow = [...sf, ...cs].find(
    (r) => r.consultation_provider_created_at || r.consultation_scheduled_at,
  );
  if (consultRow) {
    const isCareStack = consultRow.consultation_provider === "carestack";
    const provider = isCareStack ? "carestack" : "salesforce";
    if (consultRow.consultation_provider_created_at) {
      events.push({
        key: `${consultRow.person_uid}-booked`,
        time: consultRow.consultation_provider_created_at,
        provider,
        label: isCareStack ? "CS appointment booked" : "SF event booked",
      });
    }
    if (consultRow.consultation_scheduled_at) {
      events.push({
        key: `${consultRow.person_uid}-appt`,
        time: consultRow.consultation_scheduled_at,
        provider,
        label: isCareStack ? "CS appointment" : "SF event",
        status: consultRow.consultation_status,
      });
    }
  }

  // Order by creation/scheduling time so the card reads as one SF→CareStack
  // path. Stable sort keeps same-timestamp events in insertion order.
  return events.sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
  );
}

/**
 * Clickable ordering control for the location tabs. "Lead date" (default) sorts
 * by lead/funnel date so the newest leads lead; "CareStack appointment" flips the
 * server `sort` to appointment-creation order so the most recently booked persons
 * surface (and lead→appointment "double" cards rise to the top).
 */
function LocationSortHeader({
  sort,
  onSortChange,
}: {
  sort: DashboardPmLeadSort;
  onSortChange: (next: DashboardPmLeadSort) => void;
}) {
  return (
    <div className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
      <span className="uppercase tracking-wide">Sort by</span>
      <button
        type="button"
        onClick={() => onSortChange("lead")}
        className={`rounded px-2 py-0.5 transition-colors ${
          sort === "lead"
            ? "bg-primary/10 font-semibold text-primary"
            : "hover:bg-muted"
        }`}
      >
        Lead date
      </button>
      <button
        type="button"
        onClick={() => onSortChange("appointment")}
        className={`rounded px-2 py-0.5 transition-colors ${
          sort === "appointment"
            ? "bg-emerald-100 font-semibold text-emerald-700"
            : "hover:bg-muted"
        }`}
      >
        CareStack appointment
      </button>
    </div>
  );
}

function UnifiedPersonsView({
  items,
  isLoading,
}: {
  items: LeadItem[];
  isLoading: boolean;
}) {
  const grouped = useMemo(() => {
    const map = new Map<
      string,
      { person: LeadItem; sf: LeadItem[]; cs: LeadItem[] }
    >();
    for (const item of items) {
      const existing = map.get(item.person_uid) ?? {
        person: item,
        sf: [],
        cs: [],
      };
      if (item.source_provider === "salesforce") {
        existing.sf.push(item);
      } else {
        existing.cs.push(item);
      }
      map.set(item.person_uid, existing);
    }
    return [...map.values()];
  }, [items]);

  return (
    <div className="space-y-2">
      {isLoading &&
        [...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      {!isLoading &&
        grouped.map((g) => (
          <UnifiedPersonCard
            key={g.person.person_uid}
            person={g.person}
            sf={g.sf}
            cs={g.cs}
          />
        ))}
      {!isLoading && grouped.length === 0 && (
        <p className="py-6 text-center text-xs text-muted-foreground">
          No persons in this location.
        </p>
      )}
    </div>
  );
}

/**
 * Dedicated Salesforce details panel for the expanded unified card — the
 * symmetric counterpart of CareStackBlock. Lead fields (status, source, lead id,
 * created, SF event) live only on a Salesforce row; if the linked person was
 * returned as a CareStack-only row we show the linked-but-no-details fallback.
 */
function SalesforceBlock({ sf }: { sf: LeadItem[] }) {
  const sfRow = sf[0];
  const status = sfRow?.status ?? null;
  const eventRow = sf.find(
    (r) =>
      r.consultation_provider === "salesforce" &&
      (r.consultation_scheduled_at || r.consultation_provider_created_at),
  );

  const rows: { label: string; value: string }[] = [];
  if (sfRow?.lead_source) rows.push({ label: "Source", value: sfRow.lead_source });
  if (sfRow?.source_external_id)
    rows.push({ label: "SF Lead #", value: sfRow.source_external_id });
  if (sfRow?.created_at)
    rows.push({ label: "Lead created", value: formatDateTime(sfRow.created_at) });
  if (eventRow?.consultation_scheduled_at)
    rows.push({ label: "SF event", value: formatDateTime(eventRow.consultation_scheduled_at) });

  return (
    <div className="border-b bg-blue-50/40 px-4 py-3 pl-12">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-blue-700">
          Salesforce lead
        </span>
        {status && (
          <Badge
            variant="outline"
            className="border-blue-400/50 bg-blue-50 text-[10px] text-blue-700"
          >
            {status}
          </Badge>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Linked Salesforce lead — no lead details on this row.
        </p>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
          {rows.map((r) => (
            <Fragment key={r.label}>
              <dt className="text-muted-foreground">{r.label}</dt>
              <dd className="font-medium">{r.value}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </div>
  );
}

/**
 * Dedicated CareStack details panel for the expanded unified card. The
 * consultation can ride on either a CareStack patient row or (for a linked
 * person returned as a single Salesforce row) the SF lead row, so the
 * appointment fields are read from whichever row carries them.
 */
function CareStackBlock({ sf, cs }: { sf: LeadItem[]; cs: LeadItem[] }) {
  const csRow = cs[0];
  const consultRow =
    [...cs, ...sf].find(
      (r) =>
        r.consultation_provider === "carestack" &&
        (r.consultation_scheduled_at || r.consultation_provider_created_at),
    ) ?? csRow;

  const status = consultRow?.consultation_status ?? csRow?.status ?? null;
  const scheduledAt = consultRow?.consultation_scheduled_at ?? null;
  const bookedAt = consultRow?.consultation_provider_created_at ?? null;
  const location = consultRow?.location_name ?? csRow?.location_name ?? null;
  const patientId = csRow?.source_external_id ?? null;
  const patientSince = csRow?.created_at ?? null;

  const rows: { label: string; value: string }[] = [];
  if (scheduledAt) rows.push({ label: "Appointment", value: formatDateTime(scheduledAt) });
  if (bookedAt) rows.push({ label: "Booked", value: formatDateTime(bookedAt) });
  if (location) rows.push({ label: "Location", value: location });
  if (patientId) rows.push({ label: "Patient #", value: patientId });
  if (patientSince) rows.push({ label: "Patient since", value: formatDateTime(patientSince) });

  return (
    <div className="border-b bg-emerald-50/40 px-4 py-3 pl-12">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
          CareStack appointment
        </span>
        {status && (
          <Badge
            variant="outline"
            className="border-emerald-400/50 bg-emerald-50 text-[10px] text-emerald-700"
          >
            {status}
          </Badge>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Linked CareStack patient — no appointment details on this row.
        </p>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
          {rows.map((r) => (
            <Fragment key={r.label}>
              <dt className="text-muted-foreground">{r.label}</dt>
              <dd className="font-medium">{r.value}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </div>
  );
}

function UnifiedPersonCard({
  person,
  sf,
  cs,
}: {
  person: LeadItem;
  sf: LeadItem[];
  cs: LeadItem[];
}) {
  const [expanded, setExpanded] = useState(false);
  const timeline = useMemo(() => buildPersonTimeline(sf, cs), [sf, cs]);
  // First non-empty location across all rows (the SF lead row often has no
  // location_name while the CareStack row carries it), person as last resort.
  const locationName =
    [...sf, ...cs].map((r) => r.location_name).find((n) => n) ??
    person.location_name ??
    null;

  // Provider presence comes from the person's linked providers + consultation
  // origin, NOT from whether a separate provider ROW was returned. The backend
  // often returns just the Salesforce lead row even when the person is also
  // linked to CareStack (the consultation rides on that row), so keying the
  // badge off `cs.length` mislabels linked patients as "No CareStack".
  const linkedProviders = useMemo(() => {
    const set = new Set<string>();
    for (const row of [...sf, ...cs]) {
      set.add(row.source_provider);
      for (const p of row.source_providers ?? []) set.add(p);
      if (row.consultation_provider) set.add(row.consultation_provider);
    }
    return set;
  }, [sf, cs]);
  const hasSalesforce = linkedProviders.has("salesforce");
  const hasCareStack = linkedProviders.has("carestack");

  return (
    <div className="rounded-md border transition-colors hover:bg-muted/30">
      {/* The expand control is a real <button> (chevron only) and the person
          name is a sibling <Link> — no focusable element nested inside another,
          so accessibility tooling and jsx-a11y stay clean (ENG-559 Codex nit). */}
      <div className="flex w-full items-start justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-start gap-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse details" : "Expand details"}
            className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
          <div className="min-w-0 space-y-1">
            <Link
              href={`/persons/${person.person_uid}`}
              className="block truncate text-base font-semibold text-primary hover:underline"
            >
              {person.display_name}
            </Link>
            <div className="flex flex-wrap gap-x-3 text-sm text-muted-foreground">
              {person.email && <span>{person.email}</span>}
              {person.phone && <span>{person.phone}</span>}
              {locationName && <span>{locationName}</span>}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Badge
            variant="outline"
            className={
              hasSalesforce
                ? "border-blue-400/50 bg-blue-50 text-xs text-blue-700"
                : "text-xs text-muted-foreground/60"
            }
          >
            {hasSalesforce ? "Salesforce" : "No Salesforce"}
          </Badge>
          <Badge
            variant="outline"
            className={
              hasCareStack
                ? "border-emerald-400/50 bg-emerald-50 text-xs text-emerald-700"
                : "text-xs text-muted-foreground/60"
            }
          >
            {hasCareStack ? "CareStack" : "No CareStack"}
          </Badge>
        </div>
      </div>

      {expanded && (
        <div className="border-t">
          {hasSalesforce && <SalesforceBlock sf={sf} />}
          {hasCareStack && <CareStackBlock sf={sf} cs={cs} />}
          <ol className="space-y-2 px-4 py-3 pl-12">
          {timeline.length === 0 && (
            <li className="text-xs text-muted-foreground">No events.</li>
          )}
          {timeline.map((event) => (
            <li key={event.key} className="flex items-start gap-2 text-sm">
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                  event.provider === "salesforce"
                    ? "bg-blue-500"
                    : "bg-emerald-500"
                }`}
              />
              <div className="space-y-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{event.label}</span>
                  {event.status && (
                    <Badge variant="outline" className="text-[10px]">
                      {event.status}
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDateTime(event.time)}
                  {event.detail ? ` · ${event.detail}` : ""}
                </div>
              </div>
            </li>
          ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function nextDayStartIso(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString();
}
