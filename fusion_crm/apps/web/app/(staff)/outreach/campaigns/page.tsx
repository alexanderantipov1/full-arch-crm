"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCampaigns,
  useTemplates,
} from "@/lib/api/hooks/useOutreach";
import { formatDateTime } from "@/lib/utils";
import type { CampaignStatus } from "@/lib/api/schemas/outreach";

function campaignStatusBadge(s: CampaignStatus) {
  if (s === "sent") return <Badge variant="success">Sent</Badge>;
  if (s === "sending") return <Badge variant="warning">Sending</Badge>;
  if (s === "queued") return <Badge variant="warning">Queued</Badge>;
  if (s === "draft") return <Badge variant="secondary">Draft</Badge>;
  if (s === "failed") return <Badge variant="destructive">Failed</Badge>;
  return <Badge variant="outline">Cancelled</Badge>;
}

export default function CampaignsPage() {
  const { data, isLoading, error } = useCampaigns();
  const { data: templates } = useTemplates();

  const templateName = (id: string): string => {
    const t = templates?.items.find((x) => x.id === id);
    return t?.name ?? id.slice(0, 8);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Outreach campaigns
          </h1>
          <p className="text-sm text-muted-foreground">
            Scheduled or immediate batch emails. Status auto-refreshes while
            the dispatcher works through the queue.
          </p>
        </div>
        <Link href="/outreach/campaigns/new">
          <Button className="gap-1.5">
            <Plus className="h-4 w-4" />
            New campaign
          </Button>
        </Link>
      </header>

      {error ? (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load campaigns: {(error as Error).message}
        </div>
      ) : null}

      {isLoading || !data ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : data.items.length === 0 ? (
        <div className="rounded-md border border-dashed p-10 text-center text-sm text-muted-foreground">
          No campaigns yet — start one with the button above.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Template</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Sent</th>
                <th className="px-3 py-2 font-medium">Open rate</th>
                <th className="px-3 py-2 font-medium">Scheduled for</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => {
                const openRate =
                  c.sent_count > 0
                    ? `${Math.round((c.opened_count / c.sent_count) * 100)}%`
                    : "—";
                return (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="px-3 py-2 font-medium">{c.name}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {templateName(c.template_id)}
                    </td>
                    <td className="px-3 py-2">
                      {campaignStatusBadge(c.status)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {c.sent_count}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {openRate}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {c.scheduled_for ? formatDateTime(c.scheduled_for) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        href={`/outreach/campaigns/${c.id}`}
                        className="text-xs text-primary underline-offset-4 hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
