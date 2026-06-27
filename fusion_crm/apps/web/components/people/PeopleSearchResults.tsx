"use client";

import {
  AlertCircle,
  Building2,
  CalendarClock,
  ExternalLink,
  Link2,
  Mail,
  Phone,
  UserCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatDateTime, formatRelative } from "@/lib/utils";
import type {
  CsPatientMatch,
  PeopleSearchOut,
  SfPersonMatch,
} from "@/lib/api/schemas/peopleSearch";

interface Props {
  data: PeopleSearchOut | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  /** True iff the user has typed something — drives the empty-state copy. */
  hasQuery: boolean;
}

const LINK_DISABLED_TOOLTIP =
  "Coming next — backend ENG-120 will ship the link-to-person action.";

export function PeopleSearchResults({
  data,
  isLoading,
  isError,
  error,
  hasQuery,
}: Props) {
  const linkedCount = data?.linked_person_uids.length ?? 0;
  const warnings = data?.warnings ?? [];

  return (
    <div className="space-y-4">
      {linkedCount > 0 && data && (
        <LinkedPersonStrip uids={data.linked_person_uids} />
      )}

      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((warning) => (
            <div
              key={`${warning.provider}-${warning.code}`}
              className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-medium">
                  {warning.provider === "salesforce"
                    ? "Salesforce unavailable"
                    : "CareStack unavailable"}
                </div>
                <div className="text-xs opacity-90">{warning.message}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {isError && (
        <div className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">Search failed</div>
            <div className="text-xs opacity-90">
              {(error as Error)?.message ?? "Unknown error"}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Column
          provider="salesforce"
          title="Salesforce"
          subtitle="Lead / Contact matches"
          isLoading={isLoading}
          hasQuery={hasQuery}
          isEmpty={!data || data.salesforce.matches.length === 0}
        >
          {data?.salesforce.matches.map((m) => (
            <SfMatchCard key={`sf-${m.object_type}-${m.id}`} match={m} />
          ))}
        </Column>

        <Column
          provider="carestack"
          title="CareStack"
          subtitle="Patient matches"
          isLoading={isLoading}
          hasQuery={hasQuery}
          isEmpty={!data || data.carestack.matches.length === 0}
        >
          {data?.carestack.matches.map((m) => (
            <CsMatchCard key={`cs-${m.id}`} match={m} />
          ))}
        </Column>
      </div>
    </div>
  );
}

function LinkedPersonStrip({ uids }: { uids: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm">
      <UserCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
      <span className="font-medium">
        Already in CRM
        {uids.length === 1 ? "" : ` — ${uids.length} persons`}
      </span>
      <span className="flex flex-wrap gap-1">
        {uids.map((uid) => (
          <a
            key={uid}
            href={`/persons/${uid}`}
            className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-xs text-emerald-800 hover:bg-emerald-500/30 dark:text-emerald-200"
          >
            {uid.slice(0, 8)}…
          </a>
        ))}
      </span>
    </div>
  );
}

interface ColumnProps {
  provider: "salesforce" | "carestack";
  title: string;
  subtitle: string;
  isLoading: boolean;
  hasQuery: boolean;
  isEmpty: boolean;
  children?: React.ReactNode;
}

function Column({
  provider,
  title,
  subtitle,
  isLoading,
  hasQuery,
  isEmpty,
  children,
}: ColumnProps) {
  return (
    <Card>
      <div className="flex items-center justify-between border-b px-5 py-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                "capitalize",
                provider === "salesforce"
                  ? "border-sky-500/40 text-sky-700 dark:text-sky-300"
                  : "border-violet-500/40 text-violet-700 dark:text-violet-300",
              )}
            >
              {title}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <CardContent className="space-y-3 p-4">
        {isLoading && <SkeletonStack count={3} />}
        {!isLoading && isEmpty && hasQuery && <EmptyState provider={provider} />}
        {!isLoading && isEmpty && !hasQuery && <PromptState />}
        {!isLoading && !isEmpty && children}
      </CardContent>
    </Card>
  );
}

function SkeletonStack({ count }: { count: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="space-y-2 rounded-md border bg-muted/20 p-3"
        >
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </div>
  );
}

function PromptState() {
  return (
    <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      Type a phone or email above to search.
    </div>
  );
}

function EmptyState({ provider }: { provider: "salesforce" | "carestack" }) {
  return (
    <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      No matches in {provider === "salesforce" ? "Salesforce" : "CareStack"}.
    </div>
  );
}

function SfMatchCard({ match }: { match: SfPersonMatch }) {
  // Phase 1 placeholder — real deeplink lands when we wire the SF instance URL
  // through the integrations service. Until then, the button is informational.
  const sfUrl = `https://salesforce.com/lightning/r/${match.object_type}/${match.id}/view`;
  return (
    <MatchCard
      title={match.name ?? "(no name)"}
      providerKind={match.object_type}
      providerKindClass="border-sky-500/40 text-sky-700 dark:text-sky-300"
      identifierLines={[
        match.phone ? { icon: Phone, text: match.phone } : null,
        match.email ? { icon: Mail, text: match.email } : null,
      ]}
      meta={
        <>
          {match.status && (
            <Badge variant="secondary" className="font-normal">
              {match.status}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            modified {formatRelative(match.last_modified)}
          </span>
        </>
      }
      linkedPersonUid={match.linked_person_uid}
      openHref={sfUrl}
      openLabel="Open in Salesforce"
    />
  );
}

function CsMatchCard({ match }: { match: CsPatientMatch }) {
  // Phase 1 placeholder — CareStack tenant URL is per-clinic; will be wired
  // through integrations.account config later.
  const csUrl = `https://app.carestack.com/patients/${match.id}`;
  return (
    <MatchCard
      title={match.name ?? "(no name)"}
      providerKind="Patient"
      providerKindClass="border-violet-500/40 text-violet-700 dark:text-violet-300"
      identifierLines={[
        match.phone ? { icon: Phone, text: match.phone } : null,
        match.email ? { icon: Mail, text: match.email } : null,
        match.location_name
          ? { icon: Building2, text: match.location_name }
          : null,
      ]}
      meta={
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <CalendarClock className="h-3 w-3" />
          {match.last_appointment
            ? `${
                new Date(match.last_appointment).getTime() > Date.now()
                  ? "upcoming"
                  : "last"
              } appt ${formatDateTime(match.last_appointment)}`
            : "no appointments"}
        </span>
      }
      linkedPersonUid={match.linked_person_uid}
      openHref={csUrl}
      openLabel="Open in CareStack"
    />
  );
}

interface MatchCardProps {
  title: string;
  providerKind: string;
  providerKindClass: string;
  identifierLines: Array<{
    icon: React.ComponentType<{ className?: string }>;
    text: string;
  } | null>;
  meta: React.ReactNode;
  linkedPersonUid: string | null;
  openHref: string;
  openLabel: string;
}

function MatchCard({
  title,
  providerKind,
  providerKindClass,
  identifierLines,
  meta,
  linkedPersonUid,
  openHref,
  openLabel,
}: MatchCardProps) {
  return (
    <div className="rounded-md border bg-card p-3 transition-colors hover:bg-accent/30">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium">{title}</span>
            <Badge
              variant="outline"
              className={cn("text-[10px]", providerKindClass)}
            >
              {providerKind}
            </Badge>
            {linkedPersonUid && (
              <Badge variant="success" className="text-[10px]">
                Linked
              </Badge>
            )}
          </div>
          <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            {identifierLines
              .filter((l): l is NonNullable<typeof l> => l !== null)
              .map((line, i) => {
                const Icon = line.icon;
                return (
                  <div key={i} className="flex items-center gap-1.5">
                    <Icon className="h-3 w-3" />
                    <span className="truncate">{line.text}</span>
                  </div>
                );
              })}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">{meta}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 border-t pt-3">
        <Button asChild size="sm" variant="outline">
          <a href={openHref} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5" />
            {openLabel}
          </a>
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled
          title={LINK_DISABLED_TOOLTIP}
          aria-label={LINK_DISABLED_TOOLTIP}
        >
          <Link2 className="h-3.5 w-3.5" />
          Link
        </Button>
      </div>
    </div>
  );
}
