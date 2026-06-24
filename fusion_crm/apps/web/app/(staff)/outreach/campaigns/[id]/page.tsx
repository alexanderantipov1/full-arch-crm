"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ShieldOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCampaign,
  useCampaignSends,
  useTemplates,
} from "@/lib/api/hooks/useOutreach";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import { formatDateTime } from "@/lib/utils";
import type {
  CampaignStatus,
  SendStatus,
} from "@/lib/api/schemas/outreach";

function campaignStatusBadge(s: CampaignStatus) {
  if (s === "sent") return <Badge variant="success">Sent</Badge>;
  if (s === "sending") return <Badge variant="warning">Sending</Badge>;
  if (s === "queued") return <Badge variant="warning">Queued</Badge>;
  if (s === "draft") return <Badge variant="secondary">Draft</Badge>;
  if (s === "failed") return <Badge variant="destructive">Failed</Badge>;
  return <Badge variant="outline">Cancelled</Badge>;
}

function sendStatusBadge(s: SendStatus) {
  if (s === "sent" || s === "opened")
    return <Badge variant="success">{s}</Badge>;
  if (s === "queued") return <Badge variant="warning">Queued</Badge>;
  if (s === "bounced" || s === "failed")
    return <Badge variant="destructive">{s}</Badge>;
  if (s === "unsubscribed")
    return <Badge variant="secondary">Unsubscribed</Badge>;
  return <Badge variant="outline">{s}</Badge>;
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">{value}</div>
        {hint ? (
          <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { data: campaign, isLoading, error } = useCampaign(id);
  const { data: sends } = useCampaignSends(id);
  const { data: templates } = useTemplates();
  const { data: tenant } = useCurrentTenant();

  const templateName = (templateId: string): string =>
    templates?.items.find((t) => t.id === templateId)?.name ??
    templateId.slice(0, 8);

  const mailbox = tenant?.integrations.find(
    (c) => c.id === campaign?.mailbox_credential_id,
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header className="space-y-2">
        <Link
          href="/outreach/campaigns"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Back to campaigns
        </Link>

        {error ? (
          <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
            Failed to load campaign: {(error as Error).message}
          </div>
        ) : null}

        {isLoading || !campaign ? (
          <Skeleton className="h-8 w-72" />
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              {campaign.name}
            </h1>
            {campaignStatusBadge(campaign.status)}
          </div>
        )}
        {campaign ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              <span className="font-medium">Template:</span>{" "}
              {templateName(campaign.template_id)}
            </span>
            <span>
              <span className="font-medium">Mailbox:</span>{" "}
              {campaign.mailbox_strategy === "auto_route"
                ? "auto-route"
                : mailbox?.mailbox_email ??
                  mailbox?.display_name ??
                  campaign.mailbox_credential_id?.slice(0, 8) ??
                  "—"}
            </span>
            <span>
              <span className="font-medium">Scheduled for:</span>{" "}
              {campaign.scheduled_for
                ? formatDateTime(campaign.scheduled_for)
                : "—"}
            </span>
            <span>
              <span className="font-medium">Created:</span>{" "}
              {formatDateTime(campaign.created_at)}
            </span>
          </div>
        ) : null}
      </header>

      {campaign ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard
            label="Queued"
            value={
              sends?.items.filter((s) => s.status === "queued").length ?? 0
            }
            hint="Awaiting dispatcher"
          />
          <StatCard label="Sent" value={campaign.sent_count} hint="Accepted by provider" />
          <StatCard
            label="Opened"
            value={campaign.opened_count}
            hint={
              campaign.sent_count > 0
                ? `${Math.round(
                    (campaign.opened_count / campaign.sent_count) * 100,
                  )}% open rate`
                : undefined
            }
          />
          <StatCard
            label="Bounced"
            value={campaign.bounced_count}
            hint={
              campaign.unsubscribed_count > 0
                ? `${campaign.unsubscribed_count} unsubscribed`
                : undefined
            }
          />
        </div>
      ) : null}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Send list</h2>
          <Link
            href="/outreach/suppressions"
            className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
          >
            <ShieldOff className="h-3.5 w-3.5" />
            View suppression list
          </Link>
        </div>

        {!sends ? (
          <Skeleton className="h-32 w-full" />
        ) : sends.items.length === 0 ? (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No sends yet. Once the dispatcher picks the campaign up, rows
            appear here within seconds.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Recipient</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Message id</th>
                  <th className="px-3 py-2 font-medium">Sent at</th>
                  <th className="px-3 py-2 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {sends.items.map((s) => (
                  <tr key={s.id} className="border-b last:border-0 align-top">
                    <td className="px-3 py-2 font-mono text-xs">
                      {s.recipient_email}
                    </td>
                    <td className="px-3 py-2">{sendStatusBadge(s.status)}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
                      {s.message_id
                        ? `${s.message_id.slice(0, 24)}${
                            s.message_id.length > 24 ? "…" : ""
                          }`
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {s.sent_at ? formatDateTime(s.sent_at) : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-destructive">
                      {s.error_text ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
