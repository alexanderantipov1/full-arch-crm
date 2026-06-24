"use client";

import { useState } from "react";
import { Check, Loader2, Pencil, Star, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useToast } from "@/components/ui/toast";
import { cn, formatDateTime, formatRelative } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import {
  useDeleteCredential,
  useSetDefaultCredential,
  useUpdateCredential,
} from "@/lib/api/hooks/useCredentials";
import { PROVIDER_ICONS, PROVIDER_LABELS } from "@/lib/integrations/providers";
import type {
  CredentialStatus,
  ProviderKind,
  TenantIntegrationCredential,
  TenantLocation,
} from "@/lib/api/schemas/tenant";

/**
 * Editable mailbox row used inside the Integrations tab. Only rendered for
 * `google_workspace` / `microsoft_365` credentials, where ENG-125 added the
 * `display_name` / `location_id` / `is_default` / `tags` columns.
 *
 * Mutations call into `useCredentials`. If the backend endpoints aren't
 * live yet (current state at ENG-135 ship), the request 404s — we degrade
 * gracefully with a destructive toast and the row stays read-only. The
 * frontend ships ahead of the last 10 percent of backend per the ticket
 * brief.
 */
interface Props {
  integration: TenantIntegrationCredential;
  locations: TenantLocation[];
}

function credentialStatusBadge(status: CredentialStatus) {
  if (status === "active") return <Badge variant="success">Active</Badge>;
  if (status === "expired") return <Badge variant="warning">Expired</Badge>;
  return <Badge variant="destructive">Revoked</Badge>;
}

export function MailboxCredentialRow({ integration, locations }: Props) {
  const Icon = PROVIDER_ICONS[integration.provider_kind as ProviderKind];
  const { toast } = useToast();

  const update = useUpdateCredential();
  const setDefault = useSetDefaultCredential();
  const remove = useDeleteCredential();

  // Local edit-mode state for the inline form. We only commit on Save so
  // a half-typed display_name doesn't fire dozens of PATCHes.
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(integration.display_name ?? "");
  const [locationId, setLocationId] = useState<string>(
    integration.location_id ?? "",
  );
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>(integration.tags ?? []);

  function resetLocal() {
    setDisplayName(integration.display_name ?? "");
    setLocationId(integration.location_id ?? "");
    setTags(integration.tags ?? []);
    setTagInput("");
  }

  function asPatch(): {
    display_name?: string | null;
    location_id?: string | null;
    tags?: string[];
  } {
    const patch: {
      display_name?: string | null;
      location_id?: string | null;
      tags?: string[];
    } = {};
    if (displayName !== (integration.display_name ?? "")) {
      patch.display_name = displayName || null;
    }
    if (locationId !== (integration.location_id ?? "")) {
      patch.location_id = locationId || null;
    }
    const tagsChanged =
      tags.length !== (integration.tags ?? []).length ||
      tags.some((t, i) => (integration.tags ?? [])[i] !== t);
    if (tagsChanged) patch.tags = tags;
    return patch;
  }

  async function onSave() {
    const patch = asPatch();
    if (Object.keys(patch).length === 0) {
      setEditing(false);
      return;
    }
    try {
      await update.mutateAsync({ id: integration.id, ...patch });
      toast({ title: "Mailbox updated", variant: "success" });
      setEditing(false);
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Update failed",
        description:
          e instanceof ApiError && e.status === 404
            ? "edit endpoint coming next — backend route not live yet"
            : msg,
        variant: "destructive",
      });
    }
  }

  async function onSetDefault() {
    if (integration.is_default) return;
    try {
      await setDefault.mutateAsync(integration.id);
      toast({ title: "Default mailbox updated", variant: "success" });
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Could not change default",
        description:
          e instanceof ApiError && e.status === 404
            ? "endpoint coming next"
            : msg,
        variant: "destructive",
      });
    }
  }

  async function onDisconnect() {
    if (
      !window.confirm(
        `Revoke the ${PROVIDER_LABELS[integration.provider_kind as ProviderKind]} credential for ${
          integration.mailbox_email ?? integration.display_name ?? "this mailbox"
        }? Outreach sends through it will stop.`,
      )
    ) {
      return;
    }
    try {
      await remove.mutateAsync(integration.id);
      toast({ title: "Mailbox disconnected", variant: "success" });
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Could not disconnect",
        description:
          e instanceof ApiError && e.status === 404
            ? "endpoint coming next"
            : msg,
        variant: "destructive",
      });
    }
  }

  function addTag() {
    const t = tagInput.trim();
    if (!t) return;
    if (tags.includes(t)) {
      setTagInput("");
      return;
    }
    setTags([...tags, t]);
    setTagInput("");
  }

  function removeTag(t: string) {
    setTags(tags.filter((x) => x !== t));
  }

  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-medium">
              {PROVIDER_LABELS[integration.provider_kind as ProviderKind]}
            </span>
            {credentialStatusBadge(integration.status)}
            {integration.is_default ? (
              <Badge variant="outline" className="gap-1">
                <Star className="h-3 w-3 fill-current" /> Default
              </Badge>
            ) : null}
          </div>

          {integration.mailbox_email ? (
            <div className="font-mono text-xs text-muted-foreground">
              {integration.mailbox_email}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span>
              <span className="font-medium">Refreshed:</span>{" "}
              {formatRelative(integration.last_refreshed_at)}
            </span>
            <span>
              <span className="font-medium">Expires:</span>{" "}
              {integration.expires_at
                ? formatDateTime(integration.expires_at)
                : "—"}
            </span>
          </div>

          {editing ? (
            <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2">
              <label className="space-y-1">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Display name
                </div>
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="marketing@fusion-dental.com"
                />
              </label>

              <label className="space-y-1">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Location
                </div>
                <NativeSelect
                  ariaLabel="Location"
                  value={locationId}
                  onChange={(e) => setLocationId(e.target.value)}
                >
                  <option value="">— Tenant-wide —</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.short_name ?? l.name}
                    </option>
                  ))}
                </NativeSelect>
              </label>

              <div className="sm:col-span-2">
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Tags
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {tags.map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-0.5 text-xs"
                    >
                      {t}
                      <button
                        type="button"
                        onClick={() => removeTag(t)}
                        aria-label={`Remove tag ${t}`}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  <div className="flex items-center gap-1">
                    <Input
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addTag();
                        }
                      }}
                      placeholder="add tag…"
                      className="h-8 w-32 text-xs"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addTag}
                    >
                      Add
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-muted-foreground">
              {integration.location_id ? (
                <span>
                  <span className="font-medium">Location:</span>{" "}
                  {locations.find((l) => l.id === integration.location_id)
                    ?.short_name ??
                    locations.find((l) => l.id === integration.location_id)
                      ?.name ??
                    "—"}
                </span>
              ) : (
                <span>
                  <span className="font-medium">Location:</span> tenant-wide
                </span>
              )}
              {(integration.tags ?? []).length > 0 ? (
                <span className="flex flex-wrap gap-1">
                  {(integration.tags ?? []).map((t) => (
                    <span
                      key={t}
                      className="rounded-full border bg-muted/40 px-2 py-0.5 text-[10px]"
                    >
                      {t}
                    </span>
                  ))}
                </span>
              ) : null}
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-2">
          {editing ? (
            <>
              <Button
                type="button"
                size="sm"
                onClick={onSave}
                disabled={update.isPending}
                className="gap-1"
              >
                {update.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Check className="h-3.5 w-3.5" />
                )}
                Save
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  resetLocal();
                  setEditing(false);
                }}
                className="gap-1"
              >
                <X className="h-3.5 w-3.5" /> Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEditing(true)}
                className="gap-1.5"
              >
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onSetDefault}
                disabled={integration.is_default || setDefault.isPending}
                className={cn(
                  "gap-1.5",
                  integration.is_default && "text-amber-500",
                )}
                aria-label={
                  integration.is_default
                    ? "Already default mailbox"
                    : "Mark mailbox as default"
                }
              >
                <Star
                  className={cn(
                    "h-3.5 w-3.5",
                    integration.is_default && "fill-current",
                  )}
                />
                {integration.is_default ? "Default" : "Set default"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onDisconnect}
                disabled={remove.isPending}
                className="gap-1.5 text-destructive hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Disconnect
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
