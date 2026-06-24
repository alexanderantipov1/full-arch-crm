"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useDashboardSummary } from "@/lib/api/hooks/useDashboard";
import { formatRelative } from "@/lib/utils";
import type { LeadStatus } from "@/lib/api/schemas";

const LEAD_LABEL: Record<LeadStatus, string> = {
  new: "New",
  qualified: "Qualified",
  contacted: "Contacted",
  booked: "Booked",
  lost: "Lost",
};

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardSummary();

  return (
    <div className="space-y-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Marketing pipeline at a glance — Salesforce + CareStack.
        </p>
      </header>

      {error && (
        <Card className="border-destructive">
          <CardContent className="py-6 text-sm text-destructive">
            Failed to load dashboard.
          </CardContent>
        </Card>
      )}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Pipeline"
          value={isLoading ? null : data?.pipeline_total ?? 0}
          hint="Active leads"
        />
        <Stat
          label="Today's consults"
          value={isLoading ? null : data?.consultations_today ?? 0}
          hint="Booked for today"
        />
        <Stat
          label="This week"
          value={isLoading ? null : data?.consultations_this_week ?? 0}
          hint="Consultations scheduled"
        />
        <Stat
          label="Recent persons"
          value={isLoading ? null : data?.recent_persons.length ?? 0}
          hint="Updated in last 7 days"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Lead status breakdown</CardTitle>
            <CardDescription>
              Mirrors Salesforce <code>Lead.Status</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading
              ? [...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))
              : data &&
                (Object.keys(LEAD_LABEL) as LeadStatus[]).map((k) => (
                  <div
                    key={k}
                    className="flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm"
                  >
                    <span>{LEAD_LABEL[k]}</span>
                    <span className="font-mono text-muted-foreground">
                      {data.lead_counts[k] ?? 0}
                    </span>
                  </div>
                ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent persons</CardTitle>
            <CardDescription>Most recently active across providers.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading &&
              [...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            {data?.recent_persons.map((p) => (
              <Link
                key={p.id}
                href={`/persons/${p.id}`}
                className="flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm transition-colors hover:bg-accent"
              >
                <div>
                  <div className="font-medium">{p.display_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.email ?? "no email"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {p.source_providers.map((sp) => (
                    <Badge key={sp} variant="outline" className="capitalize">
                      {sp}
                    </Badge>
                  ))}
                  <span className="text-xs text-muted-foreground">
                    {formatRelative(p.last_activity_at)}
                  </span>
                </div>
              </Link>
            ))}
            {data && data.recent_persons.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No activity yet — connect Salesforce or CareStack to start.
              </p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
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
