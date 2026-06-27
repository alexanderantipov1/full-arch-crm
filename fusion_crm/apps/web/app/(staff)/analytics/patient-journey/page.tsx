"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink, Route as RouteIcon } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePatientJourney } from "@/lib/api/hooks/usePatientJourney";
import { formatMoney, formatMoneyOrDash } from "../_components/format";

function formatStamp(iso: string | null): string {
  if (!iso) return "No data";
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PatientJourneyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const personParam = searchParams.get("person");

  const [input, setInput] = useState(personParam ?? "");
  useEffect(() => {
    setInput(personParam ?? "");
  }, [personParam]);

  const query = usePatientJourney(personParam);
  const data = query.data;

  function submit(uid: string) {
    const trimmed = uid.trim();
    router.replace(
      trimmed ? `/analytics/patient-journey?person=${trimmed}` : "/analytics/patient-journey",
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <RouteIcon className="h-6 w-6" />
          Patient journey
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          One person’s full revenue journey from the patient-journey fact: each
          stage’s timestamp, the campaign / source that brought them in, and the
          revenue they generated. Responsible employee (caller / coordinator /
          doctor) shows “No data” until B1 enablement resolves it. This page is
          the drill-down target from the other analytics pages.
        </p>
      </div>

      {/* Person selector — drill-down target via ?person=<uid>. */}
      <form
        className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <label htmlFor="person-uid" className="text-sm text-muted-foreground">
          Person UID
        </label>
        <input
          id="person-uid"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="00000000-0000-0000-0000-000000000000"
          className="h-9 w-[26rem] max-w-full rounded-md border bg-background px-2 font-mono text-sm"
        />
        <Button type="submit" size="sm">
          View journey
        </Button>
      </form>

      {!personParam ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Enter a person UID above, or open this page from a drill-down link on
            another analytics page.
          </CardContent>
        </Card>
      ) : query.isError ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-destructive">
            Failed to load the journey. Is the API running and the UID valid?
          </CardContent>
        </Card>
      ) : query.isLoading || !data ? (
        <Skeleton className="h-72 w-full" />
      ) : !data.found ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No journey fact for this person. They may not be in the analytics
            projection yet.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Attribution + money header */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Card>
              <CardContent className="space-y-1 py-4">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Source
                </div>
                <div className="text-lg font-semibold">
                  {data.source ?? "—"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-1 py-4">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Campaign
                </div>
                <div className="text-lg font-semibold">
                  {data.campaign_name ?? "—"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-1 py-4">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Gross revenue
                </div>
                <div className="text-lg font-semibold tabular-nums">
                  {formatMoneyOrDash(data.revenue_amount)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-1 py-4">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Collected
                </div>
                <div className="text-lg font-semibold tabular-nums">
                  {formatMoneyOrDash(data.collected_amount)}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Stage timeline */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Journey timeline</CardTitle>
              <CardDescription>
                Stages reached carry a timestamp; stages not yet reached show
                “No data”. Responsible employee is unresolved until B1.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="space-y-0">
                {data.steps.map((step, i) => {
                  const reached = step.occurred_at !== null;
                  return (
                    <li
                      key={step.key}
                      className="flex gap-3 border-b border-border/40 py-3 last:border-0"
                    >
                      <div className="flex flex-col items-center">
                        <span
                          className={`mt-1 h-2.5 w-2.5 rounded-full ${
                            reached ? "bg-primary" : "bg-muted-foreground/30"
                          }`}
                        />
                        {i < data.steps.length - 1 ? (
                          <span className="mt-1 w-px flex-1 bg-border" />
                        ) : null}
                      </div>
                      <div className="flex flex-1 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                        <span
                          className={`text-sm font-medium ${
                            reached ? "" : "text-muted-foreground"
                          }`}
                        >
                          {step.label}
                        </span>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {formatStamp(step.occurred_at)}
                        </span>
                        <span className="w-full text-xs text-muted-foreground">
                          Responsible: {step.responsible_employee ?? "No data"}
                          {step.revenue !== null
                            ? ` · ${formatMoney(step.revenue)} collected`
                            : ""}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </CardContent>
          </Card>

          {/* Granular operational timeline (ENG-235) lives on the person card. */}
          <Card>
            <CardContent className="flex items-center justify-between gap-3 py-4">
              <p className="text-sm text-muted-foreground">
                For the granular event-level operational timeline (calls, SMS,
                appointments, payments), open the person record.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link href={`/persons/${data.person_uid}`}>
                  Open person
                  <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
