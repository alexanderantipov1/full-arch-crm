"use client";

import {
  Activity,
  Banknote,
  Briefcase,
  CalendarClock,
  CalendarCheck,
  CalendarPlus,
  CalendarX,
  CheckCircle2,
  Clock,
  FileText,
  Phone,
  GitMerge,
  HeartPulse,
  Mail,
  Receipt,
  RotateCcw,
  Sparkles,
  Stethoscope,
  TrendingUp,
  Trophy,
  User,
  UserPlus,
  XCircle,
} from "lucide-react";
import type {
  OperationalTimelineEntry,
  OperationalTimelineEventKind,
  PersonTimelineResponsible,
  TimelineEvent,
  TimelineEventKind,
  TimelineNodeDetail,
} from "@/lib/api/schemas";
import { Badge } from "@/components/ui/badge";
import { formatEventTimestamp } from "@/lib/utils";

const ICON: Record<TimelineEventKind, typeof Activity> = {
  lead_created: Sparkles,
  lead_updated: Activity,
  consultation_scheduled: CalendarPlus,
  consultation_completed: CalendarCheck,
  consultation_cancelled: CalendarX,
  merge: GitMerge,
  note: Mail,
};

const OPERATIONAL_ICON: Record<OperationalTimelineEventKind, typeof Activity> = {
  lead_created: Sparkles,
  lead_updated: Activity,
  consultation_scheduled: CalendarPlus,
  consultation_created: CalendarPlus,
  consultation_rescheduled: CalendarClock,
  consultation_cancelled: CalendarX,
  consultation_completed: CalendarCheck,
  consultation_no_show: CalendarX,
  task_created: Clock,
  task_completed: CheckCircle2,
  call_logged: Phone,
  call_reference_found: Phone,
  case_opened: FileText,
  case_closed: CheckCircle2,
  opportunity_created: Briefcase,
  opportunity_won: Trophy,
  opportunity_lost: XCircle,
  // ENG-382 funnel segments.
  opportunity_stage_changed: TrendingUp,
  contact_created: UserPlus,
  treatment_proposed: HeartPulse,
  treatment_completed: HeartPulse,
  invoice_created: Receipt,
  // CareStack money events (ENG-283).
  payment_recorded: Banknote,
  payment_refunded: RotateCcw,
  payment_reversed: RotateCcw,
  payment_applied: Banknote,
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No activity yet. Trigger a sync from the Integrations page to pull data.
      </p>
    );
  }

  // newest first
  const sorted = [...events].sort((a, b) =>
    a.occurred_at < b.occurred_at ? 1 : -1,
  );

  return (
    <ol className="relative space-y-6 border-l border-border pl-6">
      {sorted.map((ev) => {
        const Icon = ICON[ev.kind];
        return (
          <li key={ev.id} className="relative">
            <span className="absolute -left-[34px] flex h-6 w-6 items-center justify-center rounded-full border bg-card">
              <Icon className="h-3 w-3" />
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{ev.summary}</span>
              {ev.provider && (
                <Badge variant="outline" className="capitalize">
                  {ev.provider}
                </Badge>
              )}
              <span className="text-xs text-muted-foreground">
                {formatEventTimestamp(ev.occurred_at)}
              </span>
            </div>
            {Object.keys(ev.details).length > 0 && (
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {Object.entries(ev.details).map(([k, v]) => (
                  <div key={k}>
                    <dt className="inline font-mono">{k}: </dt>
                    <dd className="inline">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// Per-procedure CareStack rows arrive in bursts (one visit = many
// procedures, all sharing the service date) and their summaries are
// deliberately no-PII shells — ungrouped they flood the feed with
// visually identical lines. Same-kind, same-day runs collapse into one
// expandable row.
const GROUPED_KINDS = new Set<OperationalTimelineEventKind>([
  "treatment_proposed",
  "treatment_completed",
  // SF activity sweeps close several tasks within minutes; a same-day
  // run carries no individual signal either.
  "task_completed",
]);

const GROUP_LABEL: Record<string, string> = {
  treatment_proposed: "procedures proposed",
  treatment_completed: "procedures completed",
  task_completed: "tasks completed",
};

type TimelineRow =
  | { type: "single"; ev: OperationalTimelineEntry }
  | {
      type: "group";
      kind: OperationalTimelineEventKind;
      day: string;
      events: OperationalTimelineEntry[];
    };

function groupRows(sorted: OperationalTimelineEntry[]): TimelineRow[] {
  const rows: TimelineRow[] = [];
  for (const ev of sorted) {
    const day = ev.occurred_at.slice(0, 10);
    const last = rows[rows.length - 1];
    if (
      GROUPED_KINDS.has(ev.kind) &&
      last !== undefined &&
      last.type === "group" &&
      last.kind === ev.kind &&
      last.day === day
    ) {
      last.events.push(ev);
      continue;
    }
    if (GROUPED_KINDS.has(ev.kind)) {
      rows.push({ type: "group", kind: ev.kind, day, events: [ev] });
    } else {
      rows.push({ type: "single", ev });
    }
  }
  return rows;
}

export function OperationalTimeline({
  events,
  timezone = "America/Los_Angeles",
}: {
  events: OperationalTimelineEntry[];
  timezone?: string;
}) {
  // ENG-283 rule, mirrored from the PM Payments page: payment_applied is
  // the allocation leg of CareStack's double-entry ledger — one front-desk
  // payment fans out into one row per procedure/invoice it covers. They
  // are accounting plumbing, not person-meaningful actions (that is
  // payment_recorded), and on busy patients they flood the timeline with
  // visually identical lines.
  const visible = events.filter((ev) => ev.kind !== "payment_applied");

  if (visible.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No operational activity yet. Trigger a sync from the Integrations page
        to pull data.
      </p>
    );
  }

  const sorted = [...visible].sort((a, b) =>
    a.occurred_at < b.occurred_at ? 1 : -1,
  );

  const rows = groupRows(sorted);

  return (
    <ol className="relative space-y-6 border-l border-border pl-6">
      {rows.map((row) => {
        if (row.type === "group" && row.events.length > 1) {
          const Icon = OPERATIONAL_ICON[row.kind];
          const first = row.events[0];
          if (first === undefined) return null;
          // A day can hold several non-adjacent runs of the same kind
          // (interleaved with consultations), so the first event's source
          // id anchors the key.
          const groupKey = `group:${row.kind}:${row.day}:${first.source_external_id ?? first.occurred_at}`;
          return (
            <li
              key={groupKey}
              className="relative rounded-md bg-emerald-50/50 px-3 py-2"
            >
              <span className="absolute -left-[34px] flex h-6 w-6 items-center justify-center rounded-full border-emerald-400 bg-emerald-50">
                <Icon className="h-3 w-3 text-emerald-600" />
              </span>
              <details>
                <summary className="flex cursor-pointer flex-wrap items-center gap-2 [&::-webkit-details-marker]:hidden">
                  <span className="text-sm font-medium">
                    {row.events.length} {GROUP_LABEL[row.kind] ?? row.kind}
                  </span>
                  <Badge
                    variant="outline"
                    className="capitalize border-emerald-400/50 bg-emerald-50 text-emerald-700"
                  >
                    {first.source_provider}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatEventTimestamp(first.occurred_at, timezone)}
                  </span>
                  <span className="text-xs text-muted-foreground underline decoration-dotted">
                    expand
                  </span>
                </summary>
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {row.events.map((ev) => (
                    <li key={`${ev.kind}:${ev.source_external_id ?? ev.occurred_at}`}>
                      {ev.detail?.title ?? ev.summary} ·{" "}
                      {formatEventTimestamp(ev.occurred_at, timezone)}
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          );
        }
        const ev = row.type === "single" ? row.ev : row.events[0];
        if (ev === undefined) return null;
        return (
          <OperationalEntry
            key={operationalEntryKey(ev)}
            ev={ev}
            timezone={timezone}
          />
        );
      })}
    </ol>
  );
}

function operationalEntryKey(ev: OperationalTimelineEntry): string {
  return [
    ev.kind,
    ev.occurred_at,
    ev.source_provider,
    ev.source_kind ?? "unknown",
    ev.source_external_id ?? "none",
    ev.projection?.id ?? "no-projection",
  ].join(":");
}

function OperationalEntry({
  ev,
  timezone,
}: {
  ev: OperationalTimelineEntry;
  timezone: string;
}) {
  const Icon = OPERATIONAL_ICON[ev.kind];
  const detail = ev.detail ?? null;

  const isSf = ev.source_provider === "salesforce";
  const isCs = ev.source_provider === "carestack";
  const rowBg = isSf
    ? "rounded-md bg-blue-50/50 px-3 py-2"
    : isCs
      ? "rounded-md bg-emerald-50/50 px-3 py-2"
      : "";
  const dotBg = isSf
    ? "border-blue-400 bg-blue-50"
    : isCs
      ? "border-emerald-400 bg-emerald-50"
      : "border bg-card";

  return (
    <li className={`relative ${rowBg}`}>
      <span
        className={`absolute -left-[34px] flex h-6 w-6 items-center justify-center rounded-full ${dotBg}`}
      >
        <Icon
          className={`h-3 w-3 ${isSf ? "text-blue-600" : isCs ? "text-emerald-600" : ""}`}
        />
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{ev.summary}</span>
        <Badge
          variant="outline"
          className={`capitalize ${isSf ? "border-blue-400/50 bg-blue-50 text-blue-700" : isCs ? "border-emerald-400/50 bg-emerald-50 text-emerald-700" : ""}`}
        >
          {ev.source_provider}
        </Badge>
        <StatusBadge detail={detail} />
        {ev.review_status === "pending_review" ? (
          <Badge className="border-amber-300/60 bg-amber-50 capitalize text-amber-800">
            needs review
          </Badge>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground">
          {formatEventTimestamp(ev.occurred_at, timezone)}
        </span>
      </div>
      {/* ENG-418: responsibles ribbon — operational (agent/TC) + clinical
          (doctor) actor labels per node. */}
      <ResponsibleRibbon
        operational={ev.operational_responsibles ?? []}
        clinical={ev.clinical_responsibles ?? []}
      />
      {detail ? <NodeDetailCard detail={detail} /> : null}
    </li>
  );
}

/** Status / completion badge for a node. Green when the source record is
 * done (SF Task completed), amber while still open, neutral for kinds
 * with a status but no done/not-done semantics (leads, appointments). */
function StatusBadge({ detail }: { detail: TimelineNodeDetail | null }) {
  if (detail === null) return null;
  if (detail.is_complete === true) {
    return (
      <Badge className="gap-1 border-emerald-300/60 bg-emerald-50 text-emerald-800">
        <CheckCircle2 className="h-3 w-3" />
        {detail.status ?? "Completed"}
      </Badge>
    );
  }
  if (detail.is_complete === false) {
    return (
      <Badge className="gap-1 border-amber-300/60 bg-amber-50 text-amber-800">
        <Clock className="h-3 w-3" />
        {detail.status ?? "Open"}
      </Badge>
    );
  }
  if (detail.status) {
    return (
      <Badge variant="secondary" className="capitalize">
        {detail.status}
      </Badge>
    );
  }
  return null;
}

/** The curated "what happened" card behind a timeline node: a headline
 * (e.g. a Salesforce Task Subject) plus label/value rows projected from
 * the verbatim raw provider payload. */
function NodeDetailCard({ detail }: { detail: TimelineNodeDetail }) {
  // "Status" is already shown as a header badge — drop it from the grid
  // to avoid duplicating it.
  const fields = detail.fields.filter((f) => f.label !== "Status");
  if (detail.title === null && fields.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 rounded-md border bg-card/60 px-3 py-2">
      {detail.title ? (
        <p className="mb-1.5 text-sm font-medium text-foreground">
          {detail.title}
        </p>
      ) : null}
      {fields.length > 0 ? (
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
          {fields.map((f) => (
            <div key={f.label} className="break-words">
              <dt className="inline font-medium text-muted-foreground">
                {f.label}:{" "}
              </dt>
              <dd className="inline text-foreground/90">{f.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

/** ENG-418: one row of responsibility pills below a timeline node.
 * Operational owner (agent/TC) is a User glyph; clinical owner
 * (doctor) is a Stethoscope glyph. Sofia AI is detected by actor_type
 * = "ai" so its operational pill renders in a different colour and
 * makes the agent-vs-AI distinction visible at a glance.
 */
function ResponsibleRibbon({
  operational,
  clinical,
}: {
  operational: PersonTimelineResponsible[];
  clinical: PersonTimelineResponsible[];
}) {
  if (operational.length === 0 && clinical.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {operational.map((r) => (
        <ResponsiblePill key={`op:${r.actor_id}`} responsible={r} role="operational" />
      ))}
      {clinical.map((r) => (
        <ResponsiblePill key={`cl:${r.actor_id}`} responsible={r} role="clinical" />
      ))}
    </div>
  );
}

function ResponsiblePill({
  responsible: r,
  role,
}: {
  responsible: PersonTimelineResponsible;
  role: "operational" | "clinical";
}) {
  const isClinical = role === "clinical";
  const isAi = r.actor_type === "ai";
  const Icon = isClinical ? Stethoscope : User;
  // Distinct colour ramps so the chain UI can be parsed without
  // reading the labels — operational human (agent / TC) is slate;
  // operational AI (Sofia) is amber; clinical (doctor) is violet.
  const colour = isClinical
    ? "border-violet-300/60 bg-violet-50 text-violet-800"
    : isAi
      ? "border-amber-300/60 bg-amber-50 text-amber-800"
      : "border-slate-300/60 bg-slate-50 text-slate-800";
  const label = isClinical ? "Doctor" : isAi ? "Sofia AI" : "Owner";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${colour}`}
      title={`${label}: ${r.name}`}
    >
      <Icon className="h-3 w-3" />
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">·</span>
      <span>{r.name}</span>
    </span>
  );
}
