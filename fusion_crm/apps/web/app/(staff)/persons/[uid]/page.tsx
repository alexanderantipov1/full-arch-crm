"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CalendarCheck,
  ClipboardList,
  DollarSign,
  ExternalLink,
  HelpCircle,
  MessageSquare,
  Network,
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { OperationalTimeline } from "@/components/person/Timeline";
import { IdentityGraphModal } from "@/components/person/IdentityGraphModal";
import {
  usePersonConsultations,
  usePersonDetail,
  usePersonLocationProfiles,
  usePersonOperationalTimeline,
} from "@/lib/api/hooks/usePersons";
import {
  useSfLeadOperationalSummary,
  useSfLeadOperationalTasks,
} from "@/lib/api/hooks/useSfLeads";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import {
  providerUrlBasesFromTenantSettings,
  providerUrlFor,
} from "@/lib/integrations/providerUrls";
import type {
  OperationalTimelineEntry,
  OpsConsultation,
  PersonCarestackOriginRow,
  PersonFinancialSummary,
  PersonHouseholdMember,
  PersonLocationProfile,
  PersonTimelineCurrentOwner,
  SfLeadTaskSummary,
  TenantLocation,
} from "@/lib/api/schemas";
import { formatCurrency, formatDateTime, formatRelative } from "@/lib/utils";

function formatLocationLabel(loc: TenantLocation | undefined): string | null {
  // Two locations can share the same `name` (e.g. "Fusion Dental Implants"
  // exists in both Roseville and El Dorado Hills); append the city so the
  // operator can tell them apart without a second glance.
  if (!loc) return null;
  return loc.city ? `${loc.name} · ${loc.city}` : loc.name;
}

export default function PersonDetailPage() {
  const params = useParams<{ uid: string }>();
  const uid = params?.uid ?? "";
  const { data, isLoading, error } = usePersonDetail(uid);
  const { data: operationalTimeline } = usePersonOperationalTimeline(uid);
  const { data: opsConsultations } = usePersonConsultations(uid);
  const { data: locationProfiles } = usePersonLocationProfiles(uid);
  const { data: tenant } = useCurrentTenant();
  const [graphOpen, setGraphOpen] = useState(false);
  const salesforceLeadId = useMemo(() => {
    if (!data) return null;
    return (
      data.source_links.find(
        (sourceLink) =>
          sourceLink.provider === "salesforce" && sourceLink.entity === "lead",
      )?.external_id ?? null
    );
  }, [data]);
  const carestackPatientLink = useMemo(() => {
    if (!data) return null;
    return data.source_links.find(
      (sl) => sl.provider === "carestack" && sl.entity === "patient",
    ) ?? null;
  }, [data]);
  const salesforceLeadLink = useMemo(() => {
    if (!data) return null;
    return data.source_links.find(
      (sl) => sl.provider === "salesforce" && sl.entity === "lead",
    ) ?? null;
  }, [data]);
  const { data: sfLeadSummary } = useSfLeadOperationalSummary(salesforceLeadId);
  const { data: sfLeadTasks } = useSfLeadOperationalTasks(salesforceLeadId);
  const consultationCount =
    opsConsultations?.length ?? data?.consultations.length ?? 0;
  const locationsById = useMemo(() => {
    return new Map((tenant?.locations ?? []).map((loc) => [loc.id, loc]));
  }, [tenant?.locations]);
  const providerUrlBases = useMemo(
    () => providerUrlBasesFromTenantSettings(tenant?.settings ?? []),
    [tenant?.settings],
  );
  const operationalSnapshot = useMemo(
    () =>
      buildOperationalSnapshot(
        operationalTimeline?.items ?? [],
        opsConsultations ?? [],
        locationProfiles ?? [],
      ),
    [locationProfiles, operationalTimeline?.items, opsConsultations],
  );
  const primaryLocationName = useMemo(() => {
    if (!locationProfiles || locationProfiles.length === 0) return null;
    const profile = locationProfiles[0];
    if (!profile) return null;
    return formatLocationLabel(locationsById.get(profile.location_id));
  }, [locationProfiles, locationsById]);
  const leadStatus =
    sfLeadSummary?.salesforce_status ??
    data?.lead?.salesforce_status ??
    data?.lead?.status ??
    null;
  const leadSource = sfLeadSummary?.source ?? data?.lead?.source ?? null;
  const leadCampaign = sfLeadSummary?.campaign ?? data?.lead?.campaign ?? null;
  const leadOwner = sfLeadSummary?.owner ?? data?.lead?.owner ?? null;
  const treatmentCoordinator =
    sfLeadSummary?.treatment_coordinator ??
    data?.lead?.treatment_coordinator ??
    null;
  const sfTasks = sfLeadTasks ?? [];
  const sfCallTasks = sfTasks.filter((task) => task.task_kind === "call");
  // Real-actions feed: every SF activity (call / SMS / task) as one concise
  // line, newest first — replaces the old field-heavy "Salesforce tasks" card.
  const sfActivity = [...sfTasks].sort((a, b) =>
    (a.occurred_at ?? "") < (b.occurred_at ?? "") ? 1 : -1,
  );
  const latestSfCall = sfCallTasks[0];
  const callsDescription = latestSfCall?.occurred_at
    ? formatRelative(latestSfCall.occurred_at)
    : operationalSnapshot.lastCall
      ? formatRelative(operationalSnapshot.lastCall.occurred_at)
      : "No call captured";
  const callUrl =
    latestSfCall?.call_recording_url ??
    sfLeadSummary?.call_recording_url ??
    operationalSnapshot.callUrl;

  return (
    <div className="space-y-6 p-8">
      <Button asChild variant="ghost" size="sm">
        <Link href="/persons">
          <ArrowLeft className="h-4 w-4" />
          Back to persons
        </Link>
      </Button>

      {isLoading && <Skeleton className="h-32 w-full" />}
      {error && (
        <p className="text-sm text-destructive">Failed to load person.</p>
      )}

      {data && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">
                    {data.summary.display_name}
                  </CardTitle>
                  <CardDescription>
                    {data.summary.email ?? "no email"} ·{" "}
                    {data.summary.phone ?? "no phone"}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {data.summary.source_providers.map((p) => (
                    <Badge key={p} variant="outline" className="capitalize">
                      {p}
                    </Badge>
                  ))}
                  {data.source_links.length > 0 ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setGraphOpen(true)}
                      className="gap-1.5"
                      title="Visualise identity links across providers"
                    >
                      <Network className="h-3.5 w-3.5" />
                      Identity graph
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted-foreground">Lead status</dt>
                  <dd className="font-medium capitalize">
                    {leadStatus ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Lead source</dt>
                  <dd className="font-medium">{leadSource ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Consultations</dt>
                  <dd className="font-medium">{consultationCount}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Locations</dt>
                  <dd className="font-medium">
                    {locationProfiles?.length ?? 0}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">External IDs</dt>
                  <dd className="font-medium">{data.source_links.length}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
            <Card className="border-blue-400/30 bg-blue-50/40">
              <CardHeader className="space-y-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ClipboardList className="h-4 w-4 text-blue-500" />
                  Salesforce / marketing
                </CardTitle>
                <CardDescription>
                  {leadStatus ?? "No Salesforce lead"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <FieldLine label="Source" value={leadSource} />
                <FieldLine label="Campaign" value={leadCampaign} />
                <FieldLine
                  label="Record source"
                  value={sfLeadSummary?.record_source_detail}
                />
                <FieldLine label="Owner" value={leadOwner} />
                <FieldLine label="TC" value={treatmentCoordinator} />
                <FieldLine
                  label="Assigned center"
                  value={sfLeadSummary?.assigned_center}
                />
                <FieldLine
                  label="Unqualified"
                  value={sfLeadSummary?.unqualified_reason}
                />
                <FieldLine
                  label="HubSpot"
                  value={sfLeadSummary?.hubspot_contact_id}
                />
                <FieldLine
                  label="HubSpot created"
                  value={
                    sfLeadSummary?.hubspot_created_at
                      ? formatDateTime(sfLeadSummary.hubspot_created_at)
                      : null
                  }
                />
                <FieldLine
                  label="Lead created"
                  value={
                    sfLeadSummary?.salesforce_created_at
                      ? formatDateTime(sfLeadSummary.salesforce_created_at)
                      : salesforceLeadLink?.first_seen_at
                        ? formatDateTime(salesforceLeadLink.first_seen_at)
                        : data.lead?.salesforce_created_at
                          ? formatDateTime(data.lead.salesforce_created_at)
                          : null
                  }
                />
                <FieldLine
                  label="Status updated"
                  value={
                    sfLeadSummary?.status_last_updated_at
                      ? formatDateTime(sfLeadSummary.status_last_updated_at)
                      : null
                  }
                />
              </CardContent>
            </Card>

            <Card className="border-blue-400/30 bg-blue-50/40">
              <CardHeader className="space-y-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Phone className="h-4 w-4 text-blue-500" />
                  Calls / SMS
                </CardTitle>
                <CardDescription>{callsDescription}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <FieldLine
                  label="SF calls"
                  value={
                    sfCallTasks.length > 0
                      ? `${sfCallTasks.length} captured`
                      : null
                  }
                />
                <FieldLine
                  label="Outcome"
                  value={latestSfCall?.outcome}
                />
                <FieldLine
                  label="Attempts"
                  value={sfLeadSummary?.attempt_count}
                />
                <FieldLine
                  label="Last call by"
                  value={latestSfCall?.agent ?? sfLeadSummary?.last_call_by}
                />
                <FieldLine
                  label="Duration"
                  value={latestSfCall?.duration_label}
                />
                <FieldLine
                  label="First touch"
                  value={
                    operationalSnapshot.firstTouch
                      ? formatDateTime(operationalSnapshot.firstTouch.occurred_at)
                      : null
                  }
                />
                <FieldLine
                  label="Last call"
                  value={
                    operationalSnapshot.lastCall
                      ? formatDateTime(operationalSnapshot.lastCall.occurred_at)
                      : latestSfCall?.occurred_at
                        ? formatDateTime(latestSfCall.occurred_at)
                      : null
                  }
                />
                <FieldLine
                  label="SMS sent / reply"
                  value={operationalSnapshot.smsLabel}
                />
                <FieldLine
                  label="Inbound call"
                  value={operationalSnapshot.inboundCallLabel}
                />
                {callUrl ? (
                  <a
                    href={callUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Open call
                  </a>
                ) : null}
                {sfCallTasks.length > 0 ? (
                  <div className="space-y-2 pt-1">
                    {sfCallTasks.slice(0, 2).map((task) => (
                      <div
                        key={task.task_id}
                        className="rounded-md border px-2 py-1.5 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{task.task_label}</span>
                          <span className="text-muted-foreground">
                            {task.outcome ?? task.status ?? "—"}
                          </span>
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {task.occurred_at ? formatDateTime(task.occurred_at) : "—"}
                          {task.duration_label ? ` · ${task.duration_label}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <CarestackIdentityCard
              data={data}
              primaryCarestackLink={carestackPatientLink}
              operationalSnapshot={operationalSnapshot}
              primaryLocationName={primaryLocationName}
            />

            <FinancialSummaryCard
              summary={data.financial_summary ?? null}
            />
          </div>

          {/* ENG-310 C: household / shared-contact card. Hidden when
              the resolver returned no siblings. Sits above the timeline
              row so the operator sees the navigational links before
              they dive into the activity stream. */}
          <HouseholdLinksCard members={data.household_members ?? []} />

          {sfActivity.length > 0 ? (
            <Card className="border-blue-400/30 bg-blue-50/40">
              <CardHeader>
                <CardTitle>Activity</CardTitle>
                <CardDescription>
                  What was actually done — calls, SMS and tasks from Salesforce,
                  newest first.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {sfActivity.slice(0, 12).map((task) => (
                  <ActivityRow
                    key={task.task_id}
                    task={task}
                    timezone={operationalTimeline?.timezone}
                  />
                ))}
              </CardContent>
            </Card>
          ) : null}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Funnel chain</CardTitle>
                <CardDescription>
                  Per-stage responsibility chain — agent → TC → doctor.
                </CardDescription>
                {/* ENG-418: current-owner header — Lead owner until
                    a non-closed-lost Opportunity exists, then TC. */}
                <CurrentOwnerHeader owner={operationalTimeline?.current_owner ?? null} />
              </CardHeader>
              <CardContent>
                <OperationalTimeline
                  events={operationalTimeline?.items ?? []}
                  timezone={operationalTimeline?.timezone}
                />
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="border-emerald-400/30 bg-emerald-50/40">
                <CardHeader>
                  <CardTitle>Clinic relationship</CardTitle>
                  <CardDescription>
                    {locationProfiles && locationProfiles.length > 0
                      ? `${locationProfiles.length} location profiles`
                      : "No CareStack location evidence yet."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {(locationProfiles ?? []).map((profile) => (
                    <div
                      key={profile.id}
                      className="rounded-md border bg-card px-3 py-2 text-sm"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="outline" className="capitalize">
                          {profile.relationship_kind}
                        </Badge>
                        <Badge variant="secondary" className="capitalize">
                          {profile.relationship_status.replace("_", " ")}
                        </Badge>
                      </div>
                      <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                        <div className="font-medium text-foreground">
                          {formatLocationLabel(
                            locationsById.get(profile.location_id),
                          ) ?? "Unknown location"}
                        </div>
                        <div className="font-mono">
                          {profile.location_id}
                        </div>
                        <div>
                          evidence: {profile.last_evidence_provider ?? "unknown"}
                          {profile.last_evidence_external_id
                            ? ` #${profile.last_evidence_external_id}`
                            : ""}
                        </div>
                        {profile.last_evidence_at ? (
                          <div title={formatDateTime(profile.last_evidence_at)}>
                            {formatRelative(profile.last_evidence_at)}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Source links</CardTitle>
                  <CardDescription>
                    External IDs resolved to this person.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.source_links.map((s) => {
                    // Prefer backend-supplied provider_url (when it lands);
                    // fall back to client-side synthesis so the "open in
                    // provider" affordance works today against the MSW
                    // mocks.
                    const url = s.provider_url ?? providerUrlFor(
                      s.provider,
                      s.entity,
                      s.external_id,
                      providerUrlBases,
                    );
                    return (
                      <div
                        key={`${s.provider}:${s.external_id}`}
                        className={`rounded-md border px-3 py-2 text-sm ${s.provider === "salesforce" ? "border-blue-400/30 bg-blue-50/40" : s.provider === "carestack" ? "border-emerald-400/30 bg-emerald-50/40" : "bg-card"}`}
                      >
                        <div className="flex items-center justify-between">
                          <Badge variant="outline" className="capitalize">
                            {s.provider}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            confidence {s.confidence.toFixed(2)}
                          </span>
                        </div>
                        <div className="mt-1 font-mono text-xs">
                          {s.entity}: {s.external_id}
                        </div>
                        {url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <ExternalLink className="h-3 w-3" />
                            Open in {s.provider}
                          </a>
                        ) : null}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Consultations</CardTitle>
                  <CardDescription>
                    {consultationCount === 0
                      ? "None scheduled."
                      : `${consultationCount} on file`}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {(opsConsultations
                    ? opsConsultations.map((c) => ({
                        id: c.id,
                        status: c.status,
                        scheduled_at: c.scheduled_at,
                        provider: c.source_provider,
                        location_id: c.location_id,
                        consultation_kind: c.consultation_kind,
                      }))
                    : data.consultations
                  )
                    .sort((a, b) => {
                      // Future-scheduled at top (closest first), then past
                      // (most recent first). This is what the operator
                      // actually wants to see at a glance.
                      const now = Date.now();
                      const ta = new Date(a.scheduled_at).getTime();
                      const tb = new Date(b.scheduled_at).getTime();
                      const aFuture = ta >= now;
                      const bFuture = tb >= now;
                      if (aFuture !== bFuture) return aFuture ? -1 : 1;
                      return aFuture ? ta - tb : tb - ta;
                    })
                    .map((c) => {
                      const isSf = c.provider === "salesforce";
                      const isCs = c.provider === "carestack";
                      const bgClass = isSf
                        ? "border-blue-400/30 bg-blue-50/40"
                        : isCs
                          ? "border-emerald-400/30 bg-emerald-50/40"
                          : "bg-card";
                      return (
                        <div
                          key={c.id}
                          className={`rounded-md border px-3 py-2 text-sm ${bgClass}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <Badge variant="outline" className="capitalize">
                              {c.status.replace("_", " ")}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`capitalize ${isSf ? "border-blue-400/50 bg-blue-50 text-blue-700" : isCs ? "border-emerald-400/50 bg-emerald-50 text-emerald-700" : ""}`}
                            >
                              {c.provider}
                            </Badge>
                          </div>
                          <div className="mt-1 text-xs font-medium">
                            {formatDateTime(c.scheduled_at)}
                          </div>
                          {"location_id" in c && c.location_id ? (
                            <div className="mt-1 text-xs text-muted-foreground">
                              {formatLocationLabel(
                                locationsById.get(String(c.location_id)),
                              ) ?? "Unknown location"}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  {/* Gap indicators */}
                  {(() => {
                    const consultList = opsConsultations
                      ? opsConsultations.map((c) => c.source_provider)
                      : data.consultations.map((c) => c.provider);
                    const hasSf = consultList.includes("salesforce");
                    const hasCs = consultList.includes("carestack");
                    const gaps: React.ReactNode[] = [];
                    if (hasCs && !hasSf) {
                      gaps.push(
                        <div key="no-sf" className="rounded-md border border-red-300/50 bg-red-50/30 px-3 py-2 text-sm text-red-500">
                          No Salesforce Event — consultation exists only in CareStack
                        </div>
                      );
                    }
                    if (hasSf && !hasCs) {
                      gaps.push(
                        <div key="no-cs" className="rounded-md border border-red-300/50 bg-red-50/30 px-3 py-2 text-sm text-red-500">
                          No CareStack Appointment — consultation exists only in Salesforce
                        </div>
                      );
                    }
                    return gaps;
                  })()}
                </CardContent>
              </Card>
            </div>
          </div>

          <IdentityGraphModal
            open={graphOpen}
            onOpenChange={setGraphOpen}
            detail={data}
            timelineEvents={operationalTimeline?.items}
          />
        </>
      )}
    </div>
  );
}

/** ENG-418: current-owner header for the funnel chain card.
 *
 * The chain UI's header tells the operator who is responsible RIGHT
 * NOW for moving this person to the next stage. The rule:
 *
 *   - ``stage="lead"``         → Lead.OwnerId (call-center agent)
 *   - ``stage="opportunity"``  → covering Opportunity.OwnerId (TC)
 *
 * Renders as a compact pill with the stage label, the actor's name,
 * and a small explainer so the hand-off rule is visible to a new
 * operator. Hidden when no owner is set (rare: only when the person
 * has neither a Lead nor an Opportunity row yet).
 */
function CurrentOwnerHeader({
  owner,
}: {
  owner: PersonTimelineCurrentOwner | null;
}) {
  if (!owner) return null;
  const stageLabel =
    owner.stage === "opportunity"
      ? "Opportunity owner (TC)"
      : "Lead owner (call-center agent)";
  const explainer =
    owner.stage === "opportunity"
      ? "Hand-off complete — TC drives this person through to surgery."
      : "Pre-consult stage — call-center agent still owns this person.";
  return (
    <div className="mt-2 flex items-center gap-2 rounded-md border border-slate-300/60 bg-slate-50 px-3 py-2 text-xs">
      <Badge
        variant="outline"
        className="border-slate-300 bg-white text-[10px] font-medium uppercase tracking-wide text-slate-700"
      >
        Current owner
      </Badge>
      <span className="font-medium text-slate-900">
        {owner.name ?? owner.external_id}
      </span>
      <span className="text-slate-500">·</span>
      <span className="text-slate-600">{stageLabel}</span>
      <span className="ml-auto hidden text-slate-500 md:inline">{explainer}</span>
    </div>
  );
}

/** One concise "real action" row — call / SMS / task with its outcome,
 * time (company tz) and agent. Replaces the old field-heavy task card. */
function ActivityRow({
  task,
  timezone,
}: {
  task: SfLeadTaskSummary;
  timezone?: string;
}) {
  const Icon = activityIcon(task);
  const right = [
    task.occurred_at ? formatDateTime(task.occurred_at, timezone) : null,
    task.agent,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-sm">
      <Icon className="h-4 w-4 shrink-0 text-blue-500" />
      <span className="font-medium">{task.action_label}</span>
      {task.outcome_label ? (
        <Badge className={`capitalize ${outcomeTone(task.outcome_label)}`}>
          {task.outcome_label}
        </Badge>
      ) : null}
      {task.task_kind === "call" && task.duration_label ? (
        <span className="text-xs text-muted-foreground">
          {task.duration_label}
        </span>
      ) : null}
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {right || "—"}
      </span>
      {task.call_recording_url ? (
        <a
          href={task.call_recording_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 underline"
        >
          rec
        </a>
      ) : null}
    </div>
  );
}

function activityIcon(task: SfLeadTaskSummary) {
  const action = task.action_label.toLowerCase();
  if (action.includes("sms")) return MessageSquare;
  if (task.direction === "inbound") return PhoneIncoming;
  if (task.direction === "outbound") return PhoneOutgoing;
  if (action.includes("call") && !action.includes("call-now")) return Phone;
  return ClipboardList;
}

function outcomeTone(outcome: string): string {
  const o = outcome.toLowerCase();
  if (["connected", "done", "completed", "sent"].includes(o)) {
    return "border-emerald-300/60 bg-emerald-50 text-emerald-800";
  }
  if (
    ["no answer", "missed", "voicemail", "busy", "wrong number", "bad number"].includes(
      o,
    )
  ) {
    return "border-amber-300/60 bg-amber-50 text-amber-800";
  }
  if (o === "pending") {
    return "border-slate-300/60 bg-slate-50 text-slate-700";
  }
  // SMS template tags (confirmation, reminder-24h, …) and anything else.
  return "border-blue-300/60 bg-blue-50 text-blue-700";
}

function FieldLine({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="max-w-[14rem] break-words text-right font-medium">
        {value === null || value === undefined || value === "" ? "—" : value}
      </span>
    </div>
  );
}

function FieldLineWithHelp({
  label,
  value,
  description,
}: {
  label: string;
  value: string | number | null | undefined;
  description: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {label}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={`What is ${label}?`}
            aria-expanded={open}
            className="rounded-full text-muted-foreground/60 transition-colors hover:text-muted-foreground focus:outline-none focus-visible:text-muted-foreground"
          >
            <HelpCircle className="h-3 w-3" />
          </button>
        </span>
        <span className="max-w-[14rem] break-words text-right font-medium">
          {value === null || value === undefined || value === "" ? "—" : value}
        </span>
      </div>
      {open && (
        <p className="mt-1 rounded bg-emerald-100/60 px-2 py-1 text-xs leading-snug text-muted-foreground">
          {description}
        </p>
      )}
    </div>
  );
}

function CarestackIdentityCard({
  data,
  primaryCarestackLink,
  operationalSnapshot,
  primaryLocationName,
}: {
  data: {
    carestack_origin: PersonCarestackOriginRow[];
  };
  primaryCarestackLink: {
    first_seen_at?: string | null;
    external_id: string;
  } | null;
  operationalSnapshot: {
    converted: boolean;
    consultationLabel: string;
    arrivedLabel: string;
    relationshipLabel: string;
    lastCarestackTouch?: { occurred_at: string };
  };
  primaryLocationName: string | null;
}) {
  // ENG-308: prefer the origin-context row for the "primary" pid (the
  // first link) so provider + earliest-activity + city/state come from
  // the new aggregator. The legacy ``carestackPatientLink`` (an
  // identity.source_link) carries first_seen_at = "First ingest".
  const origin = data.carestack_origin ?? [];
  const primaryOrigin =
    primaryCarestackLink !== null
      ? origin.find(
          (row) => row.patient_id === primaryCarestackLink.external_id,
        ) ?? origin[0]
      : origin[0];
  // Earliest activity across all linked pids — the operator-facing "real"
  // patient-since signal when one person has multiple CS records.
  const earliestActivityIso = pickEarliest(
    origin.map((row) => row.earliest_activity_at ?? null),
  );
  const providerName = primaryOrigin?.default_provider_name ?? null;
  const city = primaryOrigin?.city ?? null;
  const state = primaryOrigin?.state ?? null;
  const cityState = formatCityState(city, state);
  const showMultiLink = origin.length >= 2;
  return (
    <Card className="border-emerald-400/30 bg-emerald-50/40">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarCheck className="h-4 w-4 text-emerald-500" />
          CareStack
        </CardTitle>
        <CardDescription>
          {operationalSnapshot.converted ? "Converted patient" : "Prospect"}
        </CardDescription>
        {cityState ? (
          <p className="text-xs text-muted-foreground">{cityState}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <FieldLineWithHelp
          label="First ingest"
          value={
            primaryCarestackLink?.first_seen_at
              ? formatDateTime(primaryCarestackLink.first_seen_at)
              : null
          }
          description="Date we first pulled this patient from CareStack. Actual creation in CareStack may be earlier — see 'Earliest activity'."
        />
        <FieldLineWithHelp
          label="Earliest activity"
          value={earliestActivityIso ? formatRelative(earliestActivityIso) : null}
          description="Oldest appointment created or transaction recorded in CareStack across every linked patient record for this person."
        />
        <FieldLine label="Provider" value={providerName} />
        <FieldLine
          label="Patient ID"
          value={primaryCarestackLink?.external_id ?? null}
        />
        <FieldLine
          label="Consultation"
          value={operationalSnapshot.consultationLabel}
        />
        <FieldLine label="Arrived" value={operationalSnapshot.arrivedLabel} />
        <FieldLine
          label="Relationship"
          value={operationalSnapshot.relationshipLabel}
        />
        <FieldLine label="Location" value={primaryLocationName} />
        <FieldLine
          label="Last CareStack"
          value={
            operationalSnapshot.lastCarestackTouch
              ? formatDateTime(operationalSnapshot.lastCarestackTouch.occurred_at)
              : null
          }
        />
        {showMultiLink ? <CarestackMultiLinkPanel rows={origin} /> : null}
      </CardContent>
    </Card>
  );
}

function CarestackMultiLinkPanel({
  rows,
}: {
  rows: PersonCarestackOriginRow[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-2 border-t border-emerald-300/40 pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="carestack-multilink-panel"
        className="flex w-full items-center justify-between gap-2 rounded-md border border-emerald-300/40 bg-emerald-100/40 px-2 py-1 text-xs font-medium text-emerald-900 transition-colors hover:bg-emerald-100/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <span>Linked to {rows.length} CareStack patient records</span>
        <span className="text-emerald-700">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div
          id="carestack-multilink-panel"
          className="space-y-2 rounded-md border border-emerald-200/60 bg-white/70 p-2 text-xs"
        >
          {rows.map((row) => (
            <div
              key={row.patient_id}
              className="grid grid-cols-2 gap-x-2 gap-y-1 rounded border border-emerald-200/60 bg-emerald-50/40 px-2 py-1"
            >
              {/* ENG-310 A: per-pid row label is "First Last · pid" so
                  operators can tell the linked records apart at a glance
                  instead of seeing three bare integers. Falls back to
                  just the pid when names are absent. */}
              <div className="col-span-2 font-mono text-[11px] text-emerald-900">
                {formatPidRowLabel(row)}
              </div>
              <div className="text-muted-foreground">Location</div>
              <div className="font-medium">
                {row.default_location_name ?? "—"}
              </div>
              <div className="text-muted-foreground">Provider</div>
              <div className="font-medium">
                {row.default_provider_name ?? "—"}
              </div>
              <div className="text-muted-foreground">Earliest</div>
              <div className="font-medium">
                {row.earliest_activity_at
                  ? formatRelative(row.earliest_activity_at)
                  : "—"}
              </div>
              <div className="text-muted-foreground">Latest</div>
              <div className="font-medium">
                {row.latest_activity_at
                  ? formatRelative(row.latest_activity_at)
                  : "—"}
              </div>
              {/* ENG-310 B: per-pid Patient details panel — defaults
                  hidden, click-to-reveal. Intentional access for the
                  heavier PHI fields. */}
              <div className="col-span-2 pt-1">
                <PatientDetailsPanel row={row} />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function pickEarliest(values: Array<string | null>): string | null {
  let earliest: string | null = null;
  for (const value of values) {
    if (!value) continue;
    if (!earliest || new Date(value).getTime() < new Date(earliest).getTime()) {
      earliest = value;
    }
  }
  return earliest;
}

/** ENG-310 A: per-pid label for the multi-link expander row. Shows
 * "First Last · pid" when names are available, otherwise just the pid
 * (the pre-ENG-310 behaviour). */
function formatPidRowLabel(row: PersonCarestackOriginRow): string {
  const parts = [row.first_name, row.last_name].filter(
    (p): p is string => typeof p === "string" && p.length > 0,
  );
  if (parts.length > 0) {
    return `${parts.join(" ")} · ${row.patient_id}`;
  }
  return row.patient_id;
}

/** ENG-310 B: per-pid click-to-reveal Patient details panel. Renders
 * DOB / gender / phones / email / full address / patientIdentifier /
 * accountId. SSN intentionally omitted in v1.
 *
 * Hidden by default; click toggles. Every empty field renders "—" so
 * the operator can tell "absent on this pid" from "not implemented".
 */
function PatientDetailsPanel({ row }: { row: PersonCarestackOriginRow }) {
  const [open, setOpen] = useState(false);
  const panelId = `patient-details-${row.patient_id}`;
  const fullName = formatFullName(row.first_name, row.last_name);
  const fullAddress = formatFullAddress(row);
  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-emerald-300/40 bg-emerald-50/40 px-2 py-1 text-[11px] font-medium text-emerald-900 transition-colors hover:bg-emerald-100/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <span>Patient details</span>
        <span className="text-emerald-700">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div
          id={panelId}
          className="grid grid-cols-2 gap-x-2 gap-y-1 rounded-md border border-emerald-200/60 bg-white/70 px-2 py-1 text-[11px]"
        >
          <div className="text-muted-foreground">Name</div>
          <div className="font-medium">{fullName ?? "—"}</div>
          <div className="text-muted-foreground">DOB</div>
          <div className="font-medium">{row.dob ?? "—"}</div>
          <div className="text-muted-foreground">Gender</div>
          <div className="font-medium">{row.gender ?? "—"}</div>
          <div className="text-muted-foreground">Marital status</div>
          <div className="font-medium">{row.marital_status ?? "—"}</div>
          <div className="text-muted-foreground">Mobile</div>
          <div className="font-medium">{row.mobile ?? "—"}</div>
          <div className="text-muted-foreground">Phone w/ ext</div>
          <div className="font-medium">{row.phone_with_ext ?? "—"}</div>
          <div className="text-muted-foreground">Work phone</div>
          <div className="font-medium">{row.work_phone_with_ext ?? "—"}</div>
          <div className="text-muted-foreground">Email</div>
          <div className="font-medium break-all">{row.email ?? "—"}</div>
          <div className="text-muted-foreground">Address</div>
          <div className="font-medium">{fullAddress ?? "—"}</div>
          <div className="text-muted-foreground">Patient identifier</div>
          <div className="font-medium">{row.patient_identifier ?? "—"}</div>
          <div className="text-muted-foreground">Account ID</div>
          <div className="font-medium">{row.account_id ?? "—"}</div>
        </div>
      ) : null}
    </div>
  );
}

function formatFullName(
  first: string | null | undefined,
  last: string | null | undefined,
): string | null {
  const parts = [first, last].filter(
    (p): p is string => typeof p === "string" && p.length > 0,
  );
  return parts.length > 0 ? parts.join(" ") : null;
}

function formatFullAddress(row: PersonCarestackOriginRow): string | null {
  const lines = [row.address_line1, row.address_line2].filter(
    (p): p is string => typeof p === "string" && p.length > 0,
  );
  const cityState = formatCityState(row.city, row.state);
  const parts: string[] = [];
  if (lines.length > 0) parts.push(lines.join(", "));
  if (cityState) parts.push(cityState);
  if (typeof row.address_zip === "string" && row.address_zip.length > 0) {
    parts.push(row.address_zip);
  }
  return parts.length > 0 ? parts.join(", ") : null;
}

/** ENG-310 C: "Household / shared contact" card. Listed persons share a
 * normalised phone or email with this person. The identity resolver does
 * not auto-merge them (DOB / SSN policy), but the operator must see
 * everything that is happening on the shared contact — consultations,
 * balance — without leaving the page. Each row fetches the linked
 * person's PersonDetail and renders an inline summary; the row stays
 * navigational so a click jumps to the full profile. The card hides
 * entirely when there are no members. */
function HouseholdLinksCard({
  members,
}: {
  members: PersonHouseholdMember[];
}) {
  if (members.length === 0) return null;
  return (
    <Card className="border-purple-400/30 bg-purple-50/40">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Household / shared contact</CardTitle>
        <CardDescription>
          Linked by shared phone or email. Same person across multiple records
          appears here — review their CareStack activity below before treating
          them as separate.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {members.map((member) => (
          <HouseholdMemberRow key={member.person_uid} member={member} />
        ))}
      </CardContent>
    </Card>
  );
}

/** ENG-542: human label for the shared-contact channel. The "not merged"
 * suffix is appended at the call site so the operator always sees that these
 * are SEPARATE person records sharing a contact, never an identity merge. */
function sharedContactLabel(sharedVia: PersonHouseholdMember["shared_via"]): string {
  switch (sharedVia) {
    case "phone":
      return "Same phone";
    case "email":
      return "Same email";
    case "both":
      return "Same phone & email";
    default:
      return "Same contact";
  }
}

/** One household member row. Fetches the member's PersonDetail in
 * parallel so the operator sees their consultation breakdown + balance
 * inline. Falls back to the masked-hint-only view while the detail is
 * loading or when the fetch fails. */
function HouseholdMemberRow({ member }: { member: PersonHouseholdMember }) {
  const { data, isLoading } = usePersonDetail(member.person_uid);
  const consultations = data?.consultations ?? [];
  const counts = consultations.reduce<Record<string, number>>(
    (acc, c) => {
      acc.total = (acc.total ?? 0) + 1;
      acc[c.status] = (acc[c.status] ?? 0) + 1;
      return acc;
    },
    {},
  );
  const totalConsults = counts.total ?? 0;
  const financial = data?.financial_summary;
  const hasBalance = Boolean(financial && financial.snapshot_received_at);
  return (
    <div className="rounded-md border border-purple-200/60 bg-white/70 px-3 py-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <Link
          href={`/persons/${member.person_uid}`}
          className="font-medium text-primary hover:underline"
        >
          {member.display_name ?? member.person_uid}
        </Link>
        <span className="text-xs text-muted-foreground">
          {sharedContactLabel(member.shared_via)} — not merged:{" "}
          {member.shared_value_masked}
        </span>
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <div className="text-muted-foreground">
          Consultations:{" "}
          {isLoading ? (
            <span className="opacity-60">…</span>
          ) : totalConsults === 0 ? (
            <span>none</span>
          ) : (
            <span className="font-medium text-foreground">
              {totalConsults}
              {(["scheduled", "completed", "cancelled", "no_show"] as const)
                .filter((k) => counts[k])
                .map((k) => ` · ${counts[k]} ${k}`)
                .join("")}
            </span>
          )}
        </div>
        <div className="text-muted-foreground">
          Balance:{" "}
          {isLoading ? (
            <span className="opacity-60">…</span>
          ) : hasBalance ? (
            <span className="font-medium text-foreground">
              {formatCurrency(financial!.balance)}
            </span>
          ) : (
            <span>—</span>
          )}
        </div>
      </div>
    </div>
  );
}

function formatCityState(
  city: string | null | undefined,
  state: string | null | undefined,
): string | null {
  const parts = [city, state].filter(
    (part): part is string => typeof part === "string" && part.trim().length > 0,
  );
  return parts.length > 0 ? parts.join(", ") : null;
}

function FinancialSummaryCard({
  summary,
}: {
  summary: PersonFinancialSummary | null;
}) {
  // ENG-306: empty-state signal is "no snapshot yet". When the person has
  // no CareStack patient id at all (`summary === null`) OR when the
  // backfill has not landed for them yet (`snapshot_received_at === null`)
  // every number renders "—" — never "$0", which would falsely imply the
  // operator should treat this as a paid-up patient.
  const hasSnapshot = Boolean(summary && summary.snapshot_received_at);
  const billed = hasSnapshot ? formatCurrency(summary!.billed) : "—";
  const adjustments = hasSnapshot ? formatCurrency(summary!.adjustments) : "—";
  const paid = hasSnapshot ? formatCurrency(summary!.paid) : "—";
  const balance = hasSnapshot ? formatCurrency(summary!.balance) : "—";
  return (
    <Card className="border-amber-400/30 bg-amber-50/40">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2 text-base">
          <DollarSign className="h-4 w-4 text-amber-600" />
          Treatment / payments
          <FinancialSummaryHelpDialog />
        </CardTitle>
        <CardDescription>
          {hasSnapshot
            ? "Authoritative balance from CareStack"
            : "No balance snapshot yet"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <FinancialField
          label="Billed"
          value={billed}
          description="Sum of all PROCEDURECOMPLETED debit entries from the CareStack accounting journal, deduped by external_id. The gross amount invoiced for procedures performed."
        />
        <FinancialField
          label="Adjustments"
          value={adjustments}
          description="Net of PATIENTADJUSTMENT + FEEUPDATION entries (discounts, write-offs, fee corrections), deduped by external_id. Signed by transactionType: debit positive, credit negative."
        />
        <FinancialField
          label="Paid"
          value={paid}
          description="appliedPatientPayment + appliedInsPayments from the latest CareStack payment-summary snapshot. Authoritative cash actually collected and applied to this patient's invoices."
        />
        <FinancialField
          label="Balance"
          value={balance}
          description="balanceDuePatient + balanceDueInsurance from the latest CareStack payment-summary snapshot. Authoritative outstanding amount the patient (and their insurance) still owe."
        />
        <div className="pt-1 text-xs text-muted-foreground">
          {hasSnapshot
            ? `Last snapshot: ${formatRelative(summary!.snapshot_received_at)}`
            : "No balance snapshot yet"}
        </div>
      </CardContent>
    </Card>
  );
}

type HelpLang = "en" | "ru";

const FINANCIAL_HELP: Record<
  HelpLang,
  {
    title: string;
    intro: string;
    ruleHeader: { question: string; lookAt: string };
    rule: Array<{ q: string; look: string }>;
    note: string;
    doneHeader: string;
    done: string[];
    todoHeader: string;
    todo: string[];
  }
> = {
  en: {
    title: "How to read this card",
    intro:
      "Treatment / payments shows two different views of the same patient. The Paid and Balance numbers are authoritative — CareStack computes them across its full ledger. The Billed and Adjustments numbers are gross context from the accounting feed.",
    ruleHeader: { question: "What you want to know", lookAt: "Look at" },
    rule: [
      { q: "How much real money was collected", look: "Paid (authoritative)" },
      { q: "How much the patient still owes", look: "Balance (authoritative)" },
      {
        q: "Procedures registered in the accounting feed",
        look: "Billed (gross context)",
      },
      {
        q: "Patient-facing fee adjustments",
        look: "Adjustments (gross context)",
      },
      {
        q: "Decisions about collecting or refunding cash",
        look: "Paid + Balance only",
      },
    ],
    note: "Billed and Adjustments are reference numbers from the accounting feed. They do not need to add up to Paid or Balance. CareStack computes Paid and Balance using its complete ledger — treatment plans, insurance pools, transfers, deposits — so for financial decisions trust Paid and Balance only.",
    doneHeader: "What's already in place",
    done: [
      "Authoritative Paid and Balance from the latest CareStack payment-summary snapshot (aggregated across all linked CareStack patient IDs for one person).",
      "Billed and Adjustments from the accounting journal, deduped by external_id (latest received_at wins) and signed by transactionType.",
      'Empty-state "—" when no snapshot has landed yet — never "$0", so the operator does not assume the balance is settled.',
      "Per-field info tooltips (the ? next to each label) explaining the data source for that number.",
    ],
    todoHeader: "What could still be improved",
    todo: [
      'Visual grouping: separate "Authoritative" (Paid / Balance) from "Gross context" (Billed / Adjustments) with a divider or a subtle shade.',
      'Multi-link indicator: when a person has multiple CareStack patient IDs (e.g. three registrations merged into one identity), show "3 CareStack accounts" under the card so the larger numbers make sense.',
      "Insurance contribution breakdown: tooltip-level split of Paid into appliedPatientPayment vs appliedInsPayments so it's clear how much came from the patient vs insurance.",
      "Pre-paid / deposit indicator: a small hint when the patient has paid ahead of completed procedures (Paid significantly above Billed).",
    ],
  },
  ru: {
    title: "Как читать эту карточку",
    intro:
      "Treatment / payments показывает два разных взгляда на одного пациента. Paid и Balance — authoritative, CareStack считает их по своей полной бухгалтерии. Billed и Adjustments — справочный gross-контекст из accounting feed.",
    ruleHeader: { question: "Что хочешь узнать", lookAt: "Куда смотреть" },
    rule: [
      { q: "Сколько реально получено денег", look: "Paid (authoritative)" },
      { q: "Сколько ещё должен пациент", look: "Balance (authoritative)" },
      {
        q: "Какие процедуры зарегистрированы в feed",
        look: "Billed (gross context)",
      },
      {
        q: "Patient-facing корректировки fees",
        look: "Adjustments (gross context)",
      },
      {
        q: "Финансовые решения (collect / refund)",
        look: "только Paid + Balance",
      },
    ],
    note: "Billed и Adjustments — справочные, показывают что есть в feed. Они НЕ обязаны сводиться арифметически с Paid и Balance. Authoritative — только Paid и Balance, потому что их считает сам CareStack по своей полной бухгалтерии (treatment plans, insurance pools, transfers, deposits — всё учтено). Для финансовых решений доверяй только Paid и Balance.",
    doneHeader: "Что уже сделано",
    done: [
      "Authoritative Paid и Balance из последнего CareStack payment-summary snapshot (агрегируется по всем linked CareStack patient ID одного person).",
      "Billed и Adjustments из accounting journal, deduped по external_id (берётся последний received_at), signed by transactionType.",
      'Empty-state "—" когда snapshot ещё не пришёл — никогда не "$0", чтобы оператор не подумал что баланс закрыт.',
      "Per-field tooltips (значок ? рядом с каждым label) объясняющие источник данных для каждого числа.",
    ],
    todoHeader: "Что ещё можно улучшить",
    todo: [
      'Визуальная группировка: отделить "Authoritative" (Paid / Balance) от "Gross context" (Billed / Adjustments) разделителем или другим оттенком.',
      'Multi-link indicator: когда у person несколько CareStack patient ID (например, три регистрации, объединённые в одну identity), показать "3 CareStack accounts" под карточкой — это объясняет почему числа крупные.',
      "Раскрытие insurance contribution: на уровне tooltip разбить Paid на appliedPatientPayment vs appliedInsPayments — будет видно сколько от пациента vs страховой.",
      "Pre-paid / deposit indicator: тонкая подсказка когда пациент заплатил авансом сильно больше чем PROCEDURECOMPLETED (Paid значительно выше Billed).",
    ],
  },
};

function FinancialSummaryHelpDialog() {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<HelpLang>("en");
  const t = FINANCIAL_HELP[lang];
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label="How to read Treatment / payments"
          className="ml-auto flex items-center gap-1 rounded-md border border-amber-300/60 bg-amber-100/40 px-2 py-0.5 text-xs font-normal text-amber-900 transition-colors hover:bg-amber-100/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        >
          <HelpCircle className="h-3.5 w-3.5" />
          Help
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-1">
              <DialogTitle>{t.title}</DialogTitle>
              <DialogDescription className="sr-only">{t.intro}</DialogDescription>
            </div>
            <div
              role="group"
              aria-label="Language"
              className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5 text-xs"
            >
              <button
                type="button"
                onClick={() => setLang("en")}
                aria-pressed={lang === "en"}
                className={
                  lang === "en"
                    ? "rounded bg-background px-2 py-0.5 font-medium shadow-sm"
                    : "rounded px-2 py-0.5 text-muted-foreground hover:text-foreground"
                }
              >
                English
              </button>
              <button
                type="button"
                onClick={() => setLang("ru")}
                aria-pressed={lang === "ru"}
                className={
                  lang === "ru"
                    ? "rounded bg-background px-2 py-0.5 font-medium shadow-sm"
                    : "rounded px-2 py-0.5 text-muted-foreground hover:text-foreground"
                }
              >
                Русский
              </button>
            </div>
          </div>
        </DialogHeader>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1 text-sm" aria-live="polite">
          <p className="leading-snug text-muted-foreground">{t.intro}</p>
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">
                    {t.ruleHeader.question}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t.ruleHeader.lookAt}
                  </th>
                </tr>
              </thead>
              <tbody>
                {t.rule.map((row) => (
                  <tr key={row.q} className="border-t">
                    <td className="px-3 py-2 align-top">{row.q}</td>
                    <td className="px-3 py-2 align-top font-medium">
                      {row.look}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="leading-snug text-muted-foreground">{t.note}</p>
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t.doneHeader}
            </h3>
            <ul className="list-disc space-y-1 pl-5">
              {t.done.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t.todoHeader}
            </h3>
            <ul className="list-disc space-y-1 pl-5">
              {t.todo.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FinancialField({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {label}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={`What is ${label}?`}
            aria-expanded={open}
            className="rounded-full text-muted-foreground/60 transition-colors hover:text-muted-foreground focus:outline-none focus-visible:text-muted-foreground"
          >
            <HelpCircle className="h-3 w-3" />
          </button>
        </span>
        <span className="max-w-[14rem] break-words text-right font-medium">
          {value}
        </span>
      </div>
      {open && (
        <p className="mt-1 rounded bg-amber-100/60 px-2 py-1 text-xs leading-snug text-muted-foreground">
          {description}
        </p>
      )}
    </div>
  );
}

function buildOperationalSnapshot(
  events: OperationalTimelineEntry[],
  consultations: OpsConsultation[],
  locationProfiles: PersonLocationProfile[],
) {
  const orderedEvents = [...events].sort(
    (a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
  );
  const calls = orderedEvents.filter((event) =>
    ["call_logged", "call_reference_found"].includes(event.kind),
  );
  const smsEvents = orderedEvents.filter((event) =>
    /sms|text message|message/i.test(event.summary),
  );
  const inboundCalls = calls.filter((event) => /inbound|incoming/i.test(event.summary));
  const carestackEvents = orderedEvents.filter(
    (event) => event.source_provider === "carestack",
  );
  const completedConsultation = consultations.find(
    (consultation) => consultation.status === "completed",
  );
  const scheduledConsultation = consultations.find((consultation) =>
    ["scheduled", "rescheduled"].includes(consultation.status),
  );
  const noShowConsultation = consultations.find(
    (consultation) => consultation.status === "no_show",
  );
  const patientProfile = locationProfiles.find(
    (profile) => profile.relationship_kind === "patient",
  );
  const latestProfile = [...locationProfiles].sort(
    (a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )[0];
  const callWithLink = calls.find((event) =>
    /^https?:\/\//i.test(event.source_external_id ?? ""),
  );

  return {
    firstTouch: orderedEvents.at(-1),
    lastCall: calls[0],
    callUrl: callWithLink?.source_external_id ?? null,
    smsLabel:
      smsEvents.length > 0
        ? `${smsEvents.length} captured`
        : "Not captured",
    inboundCallLabel:
      inboundCalls.length > 0
        ? `${inboundCalls.length} captured`
        : "Not captured",
    consultationLabel: completedConsultation
      ? `Completed ${formatDateTime(completedConsultation.scheduled_at)}`
      : scheduledConsultation
        ? `Scheduled ${formatDateTime(scheduledConsultation.scheduled_at)}`
        : noShowConsultation
          ? `No-show ${formatDateTime(noShowConsultation.scheduled_at)}`
          : "Not scheduled",
    arrivedLabel: completedConsultation ? "Yes" : noShowConsultation ? "No-show" : "—",
    relationshipLabel: latestProfile
      ? `${latestProfile.relationship_kind} / ${latestProfile.relationship_status.replace(
          "_",
          " ",
        )}`
      : "—",
    converted: Boolean(patientProfile || completedConsultation),
    lastCarestackTouch: carestackEvents[0],
  };
}
