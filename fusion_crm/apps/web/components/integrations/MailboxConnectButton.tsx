"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { PROVIDER_LABELS } from "@/lib/integrations/providers";
import type { ProviderKind } from "@/lib/api/schemas";

/**
 * Click-handler for the per-provider "Connect" button that lights up the
 * Google Workspace / Microsoft 365 OAuth flow.
 *
 * Flow (per ENG-131):
 *  1. Operator clicks → we GET /api/integrations/{provider}/connect/start.
 *  2. Backend mints a signed state + returns the provider's authorize URL.
 *  3. We open that URL in a new tab. The operator consents inside Google
 *     / Microsoft, who redirect back to our callback host with code+state.
 *  4. The backend's callback exchanges, runs the HIPAA gate, persists the
 *     credential, and 302s the operator back to /settings/tenant.
 *
 * We mirror the salesforce pattern (existing `lib/sf/oauth.ts`) which opens
 * the provider URL in the same tab. For Workspace/365 we use a new tab so
 * the operator's settings page stays open — the popup returns to the same
 * route via the backend's redirect.
 */
interface Props {
  provider: ProviderKind;
  locationId?: string | null;
  displayName?: string | null;
  /** Optional override label — defaults to "Connect <provider>". */
  label?: string;
  size?: "sm" | "default";
}

export function MailboxConnectButton({
  provider,
  locationId,
  displayName,
  label,
  size = "sm",
}: Props) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);

  async function onClick() {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (locationId) params.set("location_id", locationId);
      if (displayName) params.set("display_name", displayName);
      const qs = params.toString();
      const url = `/api/integrations/${provider}/connect/start${
        qs ? `?${qs}` : ""
      }`;
      const res = await fetch(url, {
        method: "GET",
        credentials: "include",
      });
      const text = await res.text();
      const body = text ? (JSON.parse(text) as Record<string, unknown>) : null;

      if (!res.ok) {
        const err = (body?.error ?? {}) as {
          code?: string;
          message?: string;
        };
        // Personal account guard returns 403 PersonalAccountBlocked per
        // ADR-0004 §"HIPAA compliance gate". Surface the operator-readable
        // message verbatim so they know to switch to a Workspace mailbox.
        toast({
          title:
            err.code === "PersonalAccountBlocked"
              ? "Personal account not allowed"
              : "Connect failed",
          description: err.message ?? `HTTP ${res.status}`,
          variant: "destructive",
        });
        return;
      }

      const authorize =
        typeof body?.["authorize_url"] === "string"
          ? (body["authorize_url"] as string)
          : null;
      if (!authorize) {
        toast({
          title: "Unexpected response",
          description: "Server did not return an authorize URL.",
          variant: "destructive",
        });
        return;
      }
      // Open in a new tab — keeps the settings page available for the
      // operator to see the success toast on return. The backend redirects
      // the popup tab back to /settings/tenant?connected=...
      window.open(authorize, "_blank", "noopener,noreferrer");
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Connect failed",
        description: msg,
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size={size}
      onClick={onClick}
      disabled={busy}
      className="gap-1.5"
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
      {label ?? `Connect ${PROVIDER_LABELS[provider]}`}
    </Button>
  );
}
