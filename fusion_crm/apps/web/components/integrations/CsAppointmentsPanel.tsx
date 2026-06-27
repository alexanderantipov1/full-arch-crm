"use client";

import { useState } from "react";
import { Loader2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  useCsAppointmentRaw,
  useFetchCsAppointments,
} from "@/lib/api/hooks/useCareStack";
import { CsRawDialog } from "./CsRawDialog";

function normaliseAppts(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data as Record<string, unknown>[];
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    for (const key of [
      "appointments",
      "items",
      "records",
      "results",
      "data",
    ]) {
      if (Array.isArray(obj[key]))
        return obj[key] as Record<string, unknown>[];
    }
  }
  return [];
}

export function CsAppointmentsPanel() {
  const fetcher = useFetchCsAppointments();
  const [openId, setOpenId] = useState<string | null>(null);
  const detail = useCsAppointmentRaw(openId);

  const appts = fetcher.data ? normaliseAppts(fetcher.data.data) : [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Appointments — modified in last 7 days</CardTitle>
            <CardDescription>
              Live read-only fetch via CareStack{" "}
              <code>/sync/appointments</code> feed. Sync feed uses textual{" "}
              <code>status</code> + <code>startDateTime</code>; the on-demand
              detail view returns <code>statusId</code> + <code>dateTime</code>.
            </CardDescription>
          </div>
          <Button
            onClick={() => fetcher.mutate(7)}
            disabled={fetcher.isPending}
            size="sm"
          >
            {fetcher.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Fetching…
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Fetch recent appointments
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {fetcher.isError && (
          <div className="mb-4 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            Fetch failed: {(fetcher.error as Error).message}
          </div>
        )}
        {fetcher.data && (
          <div className="mb-4 rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
            <span className="font-medium">modifiedSince:</span>{" "}
            <code>{fetcher.data.modifiedSince}</code>
            {" • "}
            <span className="font-medium">returned:</span> {appts.length} row
            {appts.length === 1 ? "" : "s"}
          </div>
        )}

        {!fetcher.data ? (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No data yet. Click <strong>Fetch recent appointments</strong>.
          </div>
        ) : appts.length === 0 ? (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            CareStack returned 0 appointments. Raw response shape:
            <pre className="mt-2 text-left text-xs">
              {JSON.stringify(fetcher.data.data, null, 2).slice(0, 600)}
            </pre>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Id</th>
                  <th className="px-3 py-2 font-medium">Patient</th>
                  <th className="px-3 py-2 font-medium">Start</th>
                  <th className="px-3 py-2 font-medium">Duration</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Location</th>
                  <th className="px-3 py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {appts.map((a, i) => {
                  const id = String(a.id ?? `row-${i}`);
                  return (
                    <tr
                      key={id}
                      onClick={() => setOpenId(id)}
                      className="cursor-pointer border-b last:border-0 hover:bg-muted/30"
                      title="Click to see full record"
                    >
                      <td className="px-3 py-2 font-mono text-xs">{id}</td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {String(a.patientId ?? "—")}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {String(
                          a.startDateTime ?? a.startTime ?? a.dateTime ?? "—",
                        ).slice(0, 16)}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {a.duration != null ? `${a.duration}m` : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {String(a.status ?? a.statusId ?? "—")}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {String(a.locationId ?? "—")}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {String(a.lastUpdatedOn ?? "—").slice(0, 19)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <CsRawDialog
        title="CareStack Appointment — full record"
        id={openId}
        onClose={() => setOpenId(null)}
        data={detail.data}
        isLoading={detail.isLoading}
        error={detail.error}
      />
    </Card>
  );
}
