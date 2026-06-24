"use client";

import { useState } from "react";
import { Loader2, Download } from "lucide-react";
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
  usePullRecentSfLeads,
  useRecentSfLeads,
} from "@/lib/api/hooks/useSfLeads";
import { useIntegrations } from "@/lib/api/hooks/useIntegrations";
import { SfLeadDetailDialog } from "./SfLeadDetailDialog";

export function SfLeadsPanel() {
  const { data: integrations, isLoading: integrationsLoading } =
    useIntegrations();
  const pull = usePullRecentSfLeads();
  const [openSfId, setOpenSfId] = useState<string | null>(null);
  const salesforce = integrations?.find(
    (account) => account.provider === "salesforce",
  );
  const canPull =
    salesforce?.status === "connected" || salesforce?.status === "syncing";
  const needsReconnect = salesforce?.status === "needs_reconnect";
  const { data: leads, isLoading } = useRecentSfLeads(5, canPull);
  const pullDisabled = pull.isPending || integrationsLoading || !canPull;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Salesforce Leads — slice 1</CardTitle>
            <CardDescription>
              Manual one-shot pull of the 5 most recently created Leads from
              Salesforce. Persisted to local Postgres via the canonical W1
              pipeline. Re-pull is idempotent.
            </CardDescription>
          </div>
          <Button
            onClick={() => pull.mutate(5)}
            disabled={pullDisabled}
            size="sm"
          >
            {pull.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Pulling…
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Pull 5 latest Leads
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {pull.isError && (
          <div className="mb-4 rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            Pull failed: {(pull.error as Error).message}
          </div>
        )}
        {pull.data && (
          <div className="mb-4 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">
            Pulled <strong>{pull.data.pulled_count}</strong> lead
            {pull.data.pulled_count === 1 ? "" : "s"}. Re-pulls are idempotent.
          </div>
        )}
        {!integrationsLoading && !canPull && (
          <div className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            {needsReconnect
              ? "Reconnect Salesforce before pulling Leads."
              : "Connect Salesforce before pulling Leads."}
          </div>
        )}

        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : !leads || leads.length === 0 ? (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            {canPull ? (
              <>
                No leads pulled yet. Click <strong>Pull 5 latest Leads</strong>.
              </>
            ) : (
              "No leads pulled yet."
            )}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">SF Id</th>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Email</th>
                  <th className="px-3 py-2 font-medium">Phone</th>
                  <th className="px-3 py-2 font-medium">Company</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">SF created</th>
                  <th className="px-3 py-2 font-medium">Touch</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => setOpenSfId(lead.sf_lead_id)}
                    className="cursor-pointer border-b last:border-0 hover:bg-muted/30"
                    title="Click to view all SF fields (live)"
                  >
                    <td className="px-3 py-2 font-mono text-xs">
                      {lead.sf_lead_id.slice(0, 10)}…
                    </td>
                    <td className="px-3 py-2">{lead.display_name ?? "—"}</td>
                    <td className="px-3 py-2 text-xs">{lead.email ?? "—"}</td>
                    <td className="px-3 py-2 text-xs">{lead.phone ?? "—"}</td>
                    <td className="px-3 py-2">{lead.company ?? "—"}</td>
                    <td className="px-3 py-2">{lead.lead_status ?? "—"}</td>
                    <td className="px-3 py-2 text-xs">
                      {lead.sf_created_at
                        ? new Date(lead.sf_created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-3 py-2">
                      {lead.is_reactivation ? (
                        <Badge variant="warning">Reactivated</Badge>
                      ) : (
                        <Badge variant="outline">New</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <SfLeadDetailDialog
        sfLeadId={openSfId}
        onClose={() => setOpenSfId(null)}
      />
    </Card>
  );
}
