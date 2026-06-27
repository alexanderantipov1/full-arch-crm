"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, Eye, Loader2, Save, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import {
  useCreateCampaign,
  usePreviewRecipients,
  useScheduleCampaign,
  useTemplates,
} from "@/lib/api/hooks/useOutreach";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import {
  isMailboxProvider,
  PROVIDER_LABELS,
} from "@/lib/integrations/providers";
import type {
  CampaignMailboxStrategy,
  PersonPreviewOut,
} from "@/lib/api/schemas/outreach";
import type { ProviderKind } from "@/lib/api/schemas/tenant";

type LeadStatusFilter =
  | "any"
  | "new"
  | "contacted"
  | "qualified"
  | "closed";

type ScheduleMode = "now" | "later";

export default function NewCampaignPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { data: tenant } = useCurrentTenant();
  const { data: templates } = useTemplates();

  const createCampaign = useCreateCampaign();
  const scheduleCampaign = useScheduleCampaign();
  const previewRecipients = usePreviewRecipients();

  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState<string>("");
  const [leadStatus, setLeadStatus] = useState<LeadStatusFilter>("any");
  const [limit, setLimit] = useState<string>("");
  const [mailboxStrategy, setMailboxStrategy] =
    useState<CampaignMailboxStrategy>("explicit");
  const [mailboxCredentialId, setMailboxCredentialId] = useState<string>("");
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>("now");
  const [scheduledFor, setScheduledFor] = useState<string>("");
  const [recipients, setRecipients] = useState<PersonPreviewOut[]>([]);
  const [totalRecipients, setTotalRecipients] = useState<number | null>(null);

  // Filter the available mailbox credentials to operator-email providers
  // only, mirroring `PickMailboxService.pick` server-side.
  const mailboxCredentials = useMemo(() => {
    if (!tenant) return [];
    return tenant.integrations.filter(
      (c) =>
        isMailboxProvider(c.provider_kind as ProviderKind) &&
        c.status === "active",
    );
  }, [tenant]);

  function recipientQuery(): Record<string, unknown> {
    const q: Record<string, unknown> = {};
    if (leadStatus !== "any") q["lead_status"] = leadStatus;
    const parsed = Number.parseInt(limit, 10);
    if (Number.isFinite(parsed) && parsed > 0) q["limit"] = parsed;
    return q;
  }

  async function onPreview() {
    try {
      const r = await previewRecipients.mutateAsync(recipientQuery());
      setRecipients(r.items);
      setTotalRecipients(r.total);
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Unknown error";
      toast({
        title: "Preview failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  function validate(): string | null {
    if (!name.trim()) return "Name is required.";
    if (!templateId) return "Pick a template.";
    if (mailboxStrategy === "explicit" && !mailboxCredentialId) {
      return "Pick a mailbox or switch to auto-route.";
    }
    if (scheduleMode === "later" && !scheduledFor) {
      return "Pick a date/time or switch to Now.";
    }
    return null;
  }

  async function submit(mode: "draft" | "schedule") {
    const err = validate();
    if (err) {
      toast({ title: "Check the form", description: err, variant: "destructive" });
      return;
    }

    const payload = {
      template_id: templateId,
      name,
      recipient_query: recipientQuery(),
      mailbox_credential_id:
        mailboxStrategy === "explicit" ? mailboxCredentialId : null,
      mailbox_strategy: mailboxStrategy,
      scheduled_for:
        scheduleMode === "now"
          ? new Date().toISOString()
          : new Date(scheduledFor).toISOString(),
    };

    try {
      const created = await createCampaign.mutateAsync(payload);
      if (mode === "schedule") {
        await scheduleCampaign.mutateAsync(created.id);
        toast({
          title: "Campaign scheduled",
          description: `${name} is queued for send.`,
          variant: "success",
        });
      } else {
        toast({
          title: "Draft saved",
          description: `${name} saved as draft.`,
          variant: "success",
        });
      }
      router.push(`/outreach/campaigns/${created.id}`);
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Unknown error";
      toast({
        title: "Save failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  const saving = createCampaign.isPending || scheduleCampaign.isPending;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <header className="space-y-2">
        <Link
          href="/outreach/campaigns"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Back to campaigns
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New campaign</h1>
        <p className="text-sm text-muted-foreground">
          Pick a template, filter your audience, route through a mailbox, then
          either save as draft or schedule the send.
        </p>
      </header>

      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          submit("schedule");
        }}
      >
        <section className="space-y-4 rounded-md border bg-card p-5 shadow-sm">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="c-name">Campaign name</Label>
              <Input
                id="c-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="May welcome blast"
                maxLength={240}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-template">Template</Label>
              <NativeSelect
                id="c-template"
                ariaLabel="Template"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">— pick a template —</option>
                {templates?.items.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} (v{t.version})
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>
        </section>

        <section className="space-y-4 rounded-md border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Recipients</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="c-lead-status">Lead status</Label>
              <NativeSelect
                id="c-lead-status"
                ariaLabel="Lead status"
                value={leadStatus}
                onChange={(e) =>
                  setLeadStatus(e.target.value as LeadStatusFilter)
                }
              >
                <option value="any">Any</option>
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="qualified">Qualified</option>
                <option value="closed">Closed</option>
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-limit">Optional limit</Label>
              <Input
                id="c-limit"
                type="number"
                inputMode="numeric"
                min="1"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="e.g. 100"
              />
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                variant="outline"
                onClick={onPreview}
                disabled={previewRecipients.isPending}
                className="gap-1.5"
              >
                {previewRecipients.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
                Preview recipients
              </Button>
            </div>
          </div>

          {recipients.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground">
                Showing first {recipients.length} of{" "}
                <strong>{totalRecipients ?? recipients.length}</strong>{" "}
                matching recipients.
              </div>
              <ul className="rounded border bg-muted/20 text-xs">
                {recipients.map((r) => (
                  <li
                    key={r.person_uid}
                    className="flex items-center justify-between border-b px-3 py-1.5 last:border-0"
                  >
                    <span>{r.display_name ?? "(no name)"}</span>
                    <span className="font-mono text-muted-foreground">
                      {r.primary_email ?? "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="space-y-3 rounded-md border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Mailbox routing</h2>

          <label className="flex items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
            <input
              type="radio"
              name="mailbox-strategy"
              className="mt-1"
              checked={mailboxStrategy === "explicit"}
              onChange={() => setMailboxStrategy("explicit")}
            />
            <div className="flex-1 space-y-2">
              <div className="text-sm font-medium">Pick a mailbox</div>
              <NativeSelect
                ariaLabel="Mailbox"
                value={mailboxCredentialId}
                onChange={(e) => setMailboxCredentialId(e.target.value)}
                disabled={mailboxStrategy !== "explicit"}
              >
                <option value="">— pick a mailbox —</option>
                {mailboxCredentials.map((c) => (
                  <option key={c.id} value={c.id}>
                    {PROVIDER_LABELS[c.provider_kind as ProviderKind]} —{" "}
                    {c.mailbox_email ??
                      c.display_name ??
                      c.id.slice(0, 8)}
                    {c.is_default ? " (default)" : ""}
                  </option>
                ))}
              </NativeSelect>
              {mailboxCredentials.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">
                  No mailboxes connected.{" "}
                  <Link
                    href="/settings/tenant"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Connect one
                  </Link>{" "}
                  in Tenant settings → Integrations.
                </p>
              ) : null}
            </div>
          </label>

          <label className="flex items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
            <input
              type="radio"
              name="mailbox-strategy"
              className="mt-1"
              checked={mailboxStrategy === "auto_route"}
              onChange={() => setMailboxStrategy("auto_route")}
            />
            <div className="space-y-1">
              <div className="text-sm font-medium">Auto-route per intent</div>
              <p className="text-[11px] text-muted-foreground">
                The dispatcher picks a mailbox per recipient using
                location-tag and intent-tag rules (ADR-0004 §"Pick mailbox").
              </p>
            </div>
          </label>
        </section>

        <section className="space-y-3 rounded-md border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Schedule</h2>
          <label className="flex items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
            <input
              type="radio"
              name="schedule-mode"
              className="mt-1"
              checked={scheduleMode === "now"}
              onChange={() => setScheduleMode("now")}
            />
            <div className="text-sm font-medium">
              Now
              <div className="text-[11px] font-normal text-muted-foreground">
                Enqueue immediately when you click Schedule send.
              </div>
            </div>
          </label>
          <label className="flex items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
            <input
              type="radio"
              name="schedule-mode"
              className="mt-1"
              checked={scheduleMode === "later"}
              onChange={() => setScheduleMode("later")}
            />
            <div className="flex-1 space-y-2">
              <div className="text-sm font-medium">Pick datetime</div>
              <Input
                type="datetime-local"
                value={scheduledFor}
                onChange={(e) => setScheduledFor(e.target.value)}
                disabled={scheduleMode !== "later"}
              />
            </div>
          </label>
        </section>

        <div className="flex flex-wrap items-center gap-2 border-t pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => submit("draft")}
            disabled={saving}
            className="gap-1.5"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save as draft
          </Button>
          <Button type="submit" disabled={saving} className="gap-1.5">
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Schedule send
          </Button>
          {totalRecipients !== null ? (
            <Badge variant="outline" className="ml-auto">
              {totalRecipients} matching recipient
              {totalRecipients === 1 ? "" : "s"}
            </Badge>
          ) : null}
        </div>
      </form>
    </div>
  );
}
