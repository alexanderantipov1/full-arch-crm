"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CalendarRange, GitFork, HelpCircle, Info } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { FactFunnelSection } from "../_components/FactFunnelSection";
import { useFullFunnel } from "@/lib/api/hooks/useFullFunnel";
import type {
  FullFunnelAudience,
  FullFunnelHeadline,
} from "@/lib/api/schemas";

const PERIOD_PRESETS = [
  { value: "3", label: "Last 3 months", months: 3 },
  { value: "6", label: "Last 6 months", months: 6 },
  { value: "12", label: "Last 12 months", months: 12 },
  { value: "24", label: "Last 24 months", months: 24 },
] as const;

const AUDIENCE_OPTIONS: { value: FullFunnelAudience; label: string }[] = [
  { value: "all", label: "All" },
  { value: "marketing", label: "Marketing" },
];

const CHANNEL_LABELS: Record<string, string> = {
  google: "Google",
  facebook: "Facebook",
  other: "Other",
};

const CHANNEL_COLORS: Record<string, string> = {
  google: "#4285F4",
  facebook: "#0866FF",
  other: "#94a3b8",
};

// The ordered funnel stages rendered as an aggregate bar funnel. Each maps to a
// numeric field on the headline. The consult stages (scheduled / showed /
// no-show / cancelled / rescheduled / pending) are APPOINTMENT counts and
// balance: scheduled = showed + no-show + cancelled + rescheduled + pending.
// "Closed won" is the count of paying persons (money received — CareStack
// collected cash > 0), not the Salesforce is_won flag.
const FUNNEL_STAGES = [
  { key: "leads", label: "Leads", color: "#6366f1" },
  { key: "consults_scheduled", label: "Consults scheduled", color: "#8b5cf6" },
  { key: "showed", label: "Showed", color: "#a855f7" },
  { key: "no_show", label: "No-show", color: "#f59e0b" },
  { key: "cancelled", label: "Cancelled", color: "#ef4444" },
  { key: "rescheduled", label: "Rescheduled", color: "#06b6d4" },
  { key: "pending", label: "Pending", color: "#64748b" },
  { key: "closed_won", label: "Closed won", color: "#10b981" },
] as const satisfies readonly {
  key: keyof FullFunnelHeadline;
  label: string;
  color: string;
}[];

function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] ?? channel;
}

function isoDateMonthsAgo(months: number): string {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - (months - 1));
  return d.toISOString().slice(0, 10);
}

function formatMoney(amount: number): string {
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

/** Render a spend value: `null` (no ingested spend / unconnected source) →
 *  "—", never a fake 0. A real numeric spend (incl. 0) renders as money. */
function formatSpend(spend: number | null): string {
  return spend === null ? "—" : formatMoney(spend);
}

/** Display-derived ratio as a percentage with one decimal (e.g. "57.6%").
 *  Divide-by-zero (or a non-finite result) renders "—", never NaN/Infinity. */
function formatRate(numerator: number, denominator: number): string {
  if (!denominator) return "—";
  const ratio = (numerator / denominator) * 100;
  return Number.isFinite(ratio) ? `${ratio.toFixed(1)}%` : "—";
}

/** Display-derived dollars-per-unit, rounded to whole dollars. Divide-by-zero
 *  (or a non-finite result) renders "—". */
function formatPerUnitMoney(amount: number, units: number): string {
  if (!units) return "—";
  const perUnit = amount / units;
  return Number.isFinite(perUnit) ? formatMoney(perUnit) : "—";
}

/** Cost to acquire one person at a funnel stage: ad Spend ÷ stage count.
 *  `null` spend (no ingested ad data) or a zero denominator renders "—",
 *  never a fake $0 / NaN. Ad spend only attributes to marketing-channel
 *  persons, so this is most meaningful on the Marketing audience. */
function formatCostPer(spend: number | null, units: number): string {
  if (spend === null || !units) return "—";
  const cost = spend / units;
  return Number.isFinite(cost) ? formatMoney(cost) : "—";
}

/** Return on ad spend = Revenue ÷ Spend, rendered like "3.2×". `null`/zero
 *  spend renders "—". Meaningful on the Marketing audience (spend is
 *  marketing-channel only). */
function formatRoas(revenue: number, spend: number | null): string {
  if (spend === null || !spend) return "—";
  const x = revenue / spend;
  return Number.isFinite(x) ? `${x.toFixed(1)}×` : "—";
}

/** KPI card with a click-to-reveal help note. The label carries a small info
 *  icon; clicking it toggles the formula/explanation below the value (instead
 *  of a hover-only native tooltip). */
function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <CardContent className="space-y-1 py-4">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </span>
          {hint && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label={`What is ${label}?`}
              aria-expanded={open}
              title="What does this mean?"
              className="rounded-full text-muted-foreground transition-colors hover:text-foreground"
            >
              <Info className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {open && hint && (
          <p className="text-xs leading-snug text-muted-foreground">{hint}</p>
        )}
      </CardContent>
    </Card>
  );
}

/** A monthly-table funnel-stage cell that stacks three numbers:
 *  count (top), cost = Spend ÷ count (acquisition cost at this stage), and
 *  conversion from the previous stage. `cost`/`conv` are pre-formatted strings
 *  ("$24" / "79%" / "—"). */
function StageCell({
  count,
  cost,
  conv,
}: {
  count: number;
  cost: string;
  conv: string;
}) {
  return (
    <td className="py-1.5 pr-2 text-right align-top tabular-nums">
      {/* Same size, distinguished by colour: count (default) · cost (amber) ·
          conversion (emerald). */}
      <div className="text-foreground">{count.toLocaleString()}</div>
      <div className="text-amber-600 dark:text-amber-500">{cost}</div>
      <div className="text-emerald-600 dark:text-emerald-500">{conv}</div>
    </td>
  );
}

/** Monthly-table columns + a detailed description shown in a click-to-open
 *  panel above the table (the `?` on each header). Stage columns that stack
 *  three numbers spell out what each number is. */
const MONTHLY_COLUMNS: {
  key: string;
  label: string;
  align: "left" | "right";
  help: string;
}[] = [
  {
    key: "month",
    label: "Month",
    align: "left",
    help: "The calendar month each row sums up. Each funnel stage is dated on its own system-of-truth timestamp (Salesforce for leads, CareStack for consultations and collected cash).",
  },
  {
    key: "spend",
    label: "Spend",
    align: "right",
    help: "Ad spend for the month across connected marketing channels (Google + Facebook). “—” when no spend is loaded for the month — never a fake $0.",
  },
  {
    key: "leads",
    label: "Leads",
    align: "right",
    help: "New people who entered as a lead this month — a Salesforce lead or a CareStack patient — each counted once.\n\nThree numbers:\n• count\n• cost per lead = Spend ÷ Leads\n• conversion: “—” (Leads is the funnel entry, no prior stage).",
  },
  {
    key: "scheduled",
    label: "Scheduled",
    align: "right",
    help: "Consultation appointments booked this month (every status; CareStack is the source of truth).\n\nThree numbers:\n• count\n• cost per scheduled = Spend ÷ Scheduled\n• conversion Leads → Scheduled.",
  },
  {
    key: "showed",
    label: "Showed",
    align: "right",
    help: "Patients who actually came in — your real chance to close.\n\nThree numbers:\n• count\n• cost per show = Spend ÷ Showed\n• conversion Scheduled → Showed.",
  },
  {
    key: "no_show",
    label: "No-show",
    align: "right",
    help: "Booked appointments where the patient never came. High no-show wastes ad money.",
  },
  {
    key: "cancelled",
    label: "Cancelled",
    align: "right",
    help: "Appointments cancelled before the date.",
  },
  {
    key: "resched",
    label: "Resched.",
    align: "right",
    help: "Appointments moved to another date (rescheduled).",
  },
  {
    key: "pending",
    label: "Pending",
    align: "right",
    help: "Appointments still upcoming or not yet resolved.",
  },
  {
    key: "closed_won",
    label: "Closed won",
    align: "right",
    help: "Patients who actually paid — net cash collected > 0. Real closure (money in the door), not a CRM “won” flag.\n\nThree numbers:\n• paying patients (count)\n• cost per paying patient = your acquisition cost (CAC) = Spend ÷ Closed won\n• conversion Showed → paid.",
  },
  {
    key: "show_rate",
    label: "Show rate",
    align: "right",
    help: "Show-up rate = Showed ÷ Scheduled. Of the people who booked, how many actually came. Higher = fewer no-shows.",
  },
  {
    key: "roas",
    label: "ROAS",
    align: "right",
    help: "Return on ad spend = Revenue ÷ Spend. For every $1 spent on ads, how many dollars came back. Reads truest on the Marketing audience. “—” when no spend is loaded.",
  },
  {
    key: "paid_rate",
    label: "Paid rate",
    align: "right",
    help: "Of those who showed, how many ended up paying = paying patients ÷ Showed. Directional — payers are people, shows are appointments.",
  },
  {
    key: "revenue",
    label: "Revenue",
    align: "right",
    help: "Total money collected this month — payments received minus refunds and reversals.",
  },
];

/** A monthly-table column header with a `?` that toggles the description
 *  panel for that column. */
function MonthlyColHeader({
  col,
  openCol,
  onToggle,
}: {
  col: (typeof MONTHLY_COLUMNS)[number];
  openCol: string | null;
  onToggle: (key: string) => void;
}) {
  const right = col.align === "right";
  return (
    <th className="py-2 pr-2 font-medium">
      <button
        type="button"
        onClick={() => onToggle(col.key)}
        aria-label={`What is ${col.label}?`}
        aria-expanded={openCol === col.key}
        className={`inline-flex w-full items-center gap-1 hover:text-foreground ${
          right ? "justify-end" : ""
        } ${openCol === col.key ? "text-foreground" : ""}`}
      >
        {col.label}
        <HelpCircle className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>
    </th>
  );
}

export default function FullFunnelPage() {
  const [period, setPeriod] = useState<string>("6");
  const [audience, setAudience] = useState<FullFunnelAudience>("all");
  const [audienceHelpOpen, setAudienceHelpOpen] = useState(false);
  const [openCol, setOpenCol] = useState<string | null>(null);
  const toggleCol = (key: string) =>
    setOpenCol((cur) => (cur === key ? null : key));

  const preset =
    PERIOD_PRESETS.find((p) => p.value === period) ?? PERIOD_PRESETS[1];
  const start_date = useMemo(
    () => isoDateMonthsAgo(preset.months),
    [preset.months],
  );

  // audience is part of the filters object → part of the query key, so toggling
  // refetches the report for the new audience.
  const query = useFullFunnel({ audience, start_date });

  const headline = query.data?.headline;
  const byMonth = useMemo(() => query.data?.by_month ?? [], [query.data]);
  const byChannel = useMemo(() => query.data?.by_channel ?? [], [query.data]);

  // Aggregate funnel from the headline (window totals, distinct persons / cash).
  const funnelData = useMemo(
    () =>
      FUNNEL_STAGES.map((stage) => ({
        stage: stage.label,
        value: headline ? headline[stage.key] : 0,
        color: stage.color,
      })),
    [headline],
  );

  const totalRevenue = headline?.revenue ?? 0;
  // Spend is per-month / per-channel only; sum the non-null monthly values for
  // the funnel caption.
  const totalSpend = useMemo(
    () =>
      byMonth.reduce((acc, m) => (m.spend === null ? acc : acc + m.spend), 0),
    [byMonth],
  );

  const kpis: { label: string; value: string; hint?: string }[] = headline
    ? [
        {
          label: "Leads",
          value: headline.leads.toLocaleString(),
          hint: "New people who entered as a lead in this period — a Salesforce lead or a CareStack patient. Each person is counted once, even if merged.",
        },
        {
          label: "Consults scheduled",
          value: headline.consults_scheduled.toLocaleString(),
          hint: "Consultation appointments booked in this period (every status). CareStack is the source of truth. Scheduled = Showed + No-show + Cancelled + Rescheduled + Pending.",
        },
        {
          label: "Showed",
          value: headline.showed.toLocaleString(),
          hint: "Appointments where the patient actually came in. The ones that matter — a real chance to close.",
        },
        {
          label: "No-show",
          value: headline.no_show.toLocaleString(),
          hint: "Booked appointments where the patient never came. High no-show eats your ad money.",
        },
        {
          label: "Cancelled",
          value: headline.cancelled.toLocaleString(),
          hint: "Appointments cancelled before the date.",
        },
        {
          label: "Rescheduled",
          value: headline.rescheduled.toLocaleString(),
          hint: "Appointments moved to another date.",
        },
        {
          label: "Pending",
          value: headline.pending.toLocaleString(),
          hint: "Appointments still upcoming or not yet resolved.",
        },
        {
          label: "Closed won",
          value: formatMoney(totalRevenue),
          hint: `Patients who actually paid — net cash collected in CareStack (${headline.closed_won.toLocaleString()} paying people). Real closure is money in the door, not a CRM "won" flag.`,
        },
        {
          label: "Revenue",
          value: formatMoney(totalRevenue),
          hint: "Total money collected — payments received minus refunds and reversals.",
        },
      ]
    : [];

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <GitFork className="h-6 w-6" />
            Full funnel
          </h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Person-anchored funnel: leads → consults scheduled → showed /
            no-show / cancelled / rescheduled / pending → closed won (money) →
            revenue. Each stage buckets on its own system-of-truth timestamp —
            Salesforce for marketing leads, CareStack for consultations and
            collected cash. <strong>Leads and closed-won are people</strong>,
            but the <strong>consultation stages are counted by appointment</strong>{" "}
            (one count per consultation row), so they balance:{" "}
            <strong>
              Scheduled = Showed + No-show + Cancelled + Rescheduled + Pending
            </strong>
            . Closed won is money received, not the Salesforce is-won flag.
            Toggle Marketing (ad-sourced leads only) vs All (incl.
            CareStack-direct, referral, manual). Spend with no connected source
            renders “—”, never a fake zero; a real zero count stays a zero.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Marketing / All audience toggle + click-to-reveal help */}
          <div className="relative flex items-center gap-1">
            <div className="inline-flex rounded-md border p-0.5" role="group">
              {AUDIENCE_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  type="button"
                  size="sm"
                  variant={audience === opt.value ? "default" : "ghost"}
                  aria-pressed={audience === opt.value}
                  onClick={() => setAudience(opt.value)}
                  className="h-7 px-3"
                >
                  {opt.label}
                </Button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setAudienceHelpOpen((v) => !v)}
              aria-label="What do Marketing and All mean?"
              aria-expanded={audienceHelpOpen}
              title="What does this mean?"
              className="rounded-full text-muted-foreground transition-colors hover:text-foreground"
            >
              <Info className="h-4 w-4" />
            </button>
            {audienceHelpOpen && (
              <div className="absolute left-0 top-full z-20 mt-2 w-80 rounded-md border bg-background p-3 text-xs leading-snug shadow-md">
                <p className="font-medium">Marketing vs All</p>
                <p className="mt-1 text-muted-foreground">
                  <strong className="text-foreground">Marketing</strong> keeps
                  only leads whose source resolves to a paid ad channel —{" "}
                  <strong className="text-foreground">Google</strong> or{" "}
                  <strong className="text-foreground">Facebook</strong> (from the
                  lead&apos;s utm / last-touch tracking). These are the leads your
                  ad spend brought in, so ROAS and cost-per-stage read truest
                  here.
                </p>
                <p className="mt-1.5 text-muted-foreground">
                  <strong className="text-foreground">All</strong> is everyone —
                  ad leads plus CareStack-direct patients, referrals, walk-ins
                  and manual entries.
                </p>
                <p className="mt-1.5 text-muted-foreground">
                  Other ad platforms (e.g. TikTok) aren&apos;t split out yet —
                  they currently fall under All.
                </p>
              </div>
            )}
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
        </div>
      </div>

      {/* ENG-515: nine-point patient funnel over the shared fact + global
          filters. Added above the existing Full-Funnel v2 so v2's numbers do
          not regress. */}
      <FactFunnelSection />

      {query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load the full funnel. Is the API running?
          </CardContent>
        </Card>
      ) : null}

      {/* Headline KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-9">
        {query.isLoading || !headline
          ? Array.from({ length: 9 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 py-4">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))
          : kpis.map((kpi) => (
              <MetricCard key={kpi.label} {...kpi} />
            ))}
      </div>

      {/* Conversions (display-derived from the headline totals) */}
      {query.isLoading || !headline ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-2 py-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-7 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {[
              {
                label: "Show rate",
                value: formatRate(headline.showed, headline.consults_scheduled),
                hint: "Show-up rate — showed ÷ consults scheduled. Share of booked appointments that actually showed up.",
              },
              {
                label: "ROAS",
                value: formatRoas(totalRevenue, totalSpend),
                hint: "Return on ad spend — Revenue ÷ Spend (dollars earned per $1 of ad spend). Most meaningful on the Marketing audience.",
              },
              {
                label: "Paid rate",
                value: formatRate(headline.closed_won, headline.showed),
                hint: "Paying persons ÷ shows — closed_won (paying persons) ÷ showed (appointments). Directional ratio (different units).",
              },
            ].map((conv) => (
              <MetricCard key={conv.label} {...conv} />
            ))}
          </div>
          {/* Marketing efficiency — cost to acquire one person at each funnel
              stage + return on ad spend. Spend attributes to marketing-channel
              persons only, so these read truest on the Marketing audience. */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              {
                label: "CPL",
                value: formatCostPer(totalSpend, headline.leads),
                hint: "Cost per lead — Spend ÷ Leads. How much ad money it takes to get one lead.",
              },
              {
                label: "Cost / scheduled",
                value: formatCostPer(totalSpend, headline.consults_scheduled),
                hint: "Spend ÷ Scheduled — cost of one scheduled consultation.",
              },
              {
                label: "Cost / show",
                value: formatCostPer(totalSpend, headline.showed),
                hint: "Spend ÷ Showed — cost to get one person into the chair (actually showed up).",
              },
              {
                label: "Cost / paid",
                value: formatCostPer(totalSpend, headline.closed_won),
                hint: "Spend ÷ Closed won — CAC: cost of one paying patient.",
              },
              {
                label: "Revenue / lead",
                value: formatPerUnitMoney(totalRevenue, headline.leads),
                hint: "Revenue ÷ Leads — average revenue per lead.",
              },
            ].map((m) => (
              <MetricCard key={m.label} {...m} />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            <strong>Conversions:</strong> Show rate = showed ÷ scheduled; Paid
            rate = paying persons ÷ shows.{" "}
            <strong>Marketing efficiency:</strong> cost per stage = Spend ÷
            stage (lead / scheduled / show / paid), ROAS = Revenue ÷ Spend. Ad
            spend attributes to marketing channels only, so these read truest on
            the <strong>Marketing</strong> toggle. &quot;—&quot; means spend for
            the period isn&apos;t loaded (not a fake $0). Click the info icon on
            any card for its formula.
          </p>
        </div>
      )}

      {/* Funnel bar chart (aggregate across the window) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Funnel</CardTitle>
          <CardDescription>
            Leads → consults scheduled → showed / no-show / cancelled /
            rescheduled / pending → closed won. Leads and closed-won are window
            totals as distinct persons; the consult stages are appointment
            counts (Scheduled = Showed + No-show + Cancelled + Rescheduled +
            Pending). Spend ({formatMoney(totalSpend)}) is shown per month in
            the table below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : funnelData.every((d) => d.value === 0) ? (
            <p className="py-16 text-center text-sm text-muted-foreground">
              No funnel data for this period.
            </p>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={funnelData} layout="vertical">
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="stroke-muted"
                    horizontal={false}
                  />
                  <XAxis type="number" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="stage"
                    width={130}
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    formatter={(value, _name, item) => {
                      const stage = String(item?.payload?.stage ?? "");
                      // Leads / Closed won are people; consult stages are
                      // appointment (consultation-row) counts.
                      const unit =
                        stage === "Leads" || stage === "Closed won"
                          ? "Persons"
                          : "Appointments";
                      return [Number(value).toLocaleString(), unit];
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {funnelData.map((d, index) => (
                      <Cell key={index} fill={d.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Monthly + by-channel tables */}
      <Tabs defaultValue="monthly">
        <TabsList>
          <TabsTrigger value="monthly">Monthly</TabsTrigger>
          <TabsTrigger value="channels">By channel</TabsTrigger>
        </TabsList>

        <TabsContent value="monthly">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>
                The <strong>Leads, Scheduled, Showed and Closed won</strong>{" "}
                columns stack three numbers (same size, by colour):{" "}
                <strong>count</strong> ·{" "}
                <strong className="text-amber-600 dark:text-amber-500">
                  cost = Spend ÷ count
                </strong>{" "}
                (acquisition cost at that stage; Closed won&apos;s cost is your
                CAC) ·{" "}
                <strong className="text-emerald-600 dark:text-emerald-500">
                  conversion from the previous stage
                </strong>{" "}
                (Leads → Scheduled → Showed → Closed won). Leads and Closed-won are
                people; the consult stages are counted by appointment, so they
                balance: Scheduled = Showed + No-show + Cancelled + Rescheduled +
                Pending. Cost shows &quot;—&quot; when spend for the month
                isn&apos;t loaded. Hover any column&apos;s info icon for its
                exact formula.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-2">
              <Dialog
                open={openCol !== null}
                onOpenChange={(o) => !o && setOpenCol(null)}
              >
                <DialogContent className="max-w-md">
                  <DialogHeader>
                    <DialogTitle className="text-xl">
                      {MONTHLY_COLUMNS.find((x) => x.key === openCol)?.label}
                    </DialogTitle>
                    <DialogDescription className="whitespace-pre-line pt-2 text-base leading-relaxed text-foreground">
                      {MONTHLY_COLUMNS.find((x) => x.key === openCol)?.help}
                    </DialogDescription>
                  </DialogHeader>
                </DialogContent>
              </Dialog>
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : byMonth.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No data for this period.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                        {MONTHLY_COLUMNS.map((col) => (
                          <MonthlyColHeader
                            key={col.key}
                            col={col}
                            openCol={openCol}
                            onToggle={toggleCol}
                          />
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {byMonth.map((m) => (
                        <tr key={m.month} className="border-b border-border/50">
                          <td className="py-1.5 pr-2 font-medium tabular-nums">
                            {m.month}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {formatSpend(m.spend)}
                          </td>
                          <StageCell
                            count={m.leads}
                            cost={formatCostPer(m.spend, m.leads)}
                            conv="—"
                          />
                          <StageCell
                            count={m.consults_scheduled}
                            cost={formatCostPer(m.spend, m.consults_scheduled)}
                            conv={formatRate(m.consults_scheduled, m.leads)}
                          />
                          <StageCell
                            count={m.showed}
                            cost={formatCostPer(m.spend, m.showed)}
                            conv={formatRate(m.showed, m.consults_scheduled)}
                          />
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {m.no_show.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {m.cancelled.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {m.rescheduled.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {m.pending.toLocaleString()}
                          </td>
                          <StageCell
                            count={m.closed_won}
                            cost={formatCostPer(m.spend, m.closed_won)}
                            conv={formatRate(m.closed_won, m.showed)}
                          />
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {formatRate(m.showed, m.consults_scheduled)}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {formatRoas(m.revenue, m.spend)}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {formatRate(m.closed_won, m.showed)}
                          </td>
                          <td className="py-1.5 text-right tabular-nums">
                            {formatMoney(m.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="channels">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>
                Per-month channel breakdown (Google / Facebook / Other). The
                consultation stages are counted by appointment (Scheduled =
                Showed + No-show + Cancelled + Rescheduled + Pending); Leads are
                people. Closed-won is reported at the month level only (the
                “Monthly” tab) — opportunity→channel attribution is deferred.
                Spend is “—” for the Other channel and for months with no
                ingested ad spend.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : byChannel.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No data for this period.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-2 font-medium">Month</th>
                        <th className="py-2 pr-2 font-medium">Channel</th>
                        <th className="py-2 pr-2 text-right font-medium">Spend</th>
                        <th className="py-2 pr-2 text-right font-medium">Leads</th>
                        <th className="py-2 pr-2 text-right font-medium">
                          Scheduled
                        </th>
                        <th className="py-2 pr-2 text-right font-medium">Showed</th>
                        <th className="py-2 pr-2 text-right font-medium">
                          No-show
                        </th>
                        <th className="py-2 pr-2 text-right font-medium">
                          Cancelled
                        </th>
                        <th className="py-2 pr-2 text-right font-medium">
                          Resched.
                        </th>
                        <th className="py-2 pr-2 text-right font-medium">
                          Pending
                        </th>
                        <th className="py-2 text-right font-medium">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {byChannel.map((row) => (
                        <tr
                          key={`${row.month}:${row.channel}`}
                          className="border-b border-border/50"
                        >
                          <td className="py-1.5 pr-2 tabular-nums text-muted-foreground">
                            {row.month}
                          </td>
                          <td className="py-1.5 pr-2">
                            <Badge
                              variant="outline"
                              className="text-[10px]"
                              style={{
                                borderColor: CHANNEL_COLORS[row.channel],
                                color: CHANNEL_COLORS[row.channel],
                              }}
                            >
                              {channelLabel(row.channel)}
                            </Badge>
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {formatSpend(row.spend)}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.leads.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.consults_scheduled.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.showed.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.no_show.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.cancelled.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.rescheduled.toLocaleString()}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">
                            {row.pending.toLocaleString()}
                          </td>
                          <td className="py-1.5 text-right tabular-nums">
                            {formatMoney(row.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
