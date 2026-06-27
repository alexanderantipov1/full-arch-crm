"use client";

import { useState } from "react";
import { KeyRound, Loader2, Plug2, RefreshCw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useQueryClient } from "@tanstack/react-query";
import { useUpsertBootstrapCredential } from "@/lib/api/hooks/useCredentials";
import {
  useConnectStart,
  useDisconnect,
  useOAuthCallback,
  useTriggerSync,
} from "@/lib/api/hooks/useIntegrations";
import type { IntegrationAccount, IntegrationStatus } from "@/lib/api/schemas";
import type {
  BootstrapProviderKind,
  IntegrationCredentialBootstrapInput,
} from "@/lib/api/schemas/tenant";
import { formatRelative } from "@/lib/utils";

// Providers that present an operator credential form on the card. Mirrors the
// backend `BootstrapProviderKind` minus `openai` (which connects via the
// agent-runtime test path, not this card).
type CardBootstrapProvider = Exclude<BootstrapProviderKind, "openai">;

// Providers whose connect button immediately opens the credential form rather
// than calling `connect/start` (no OAuth redirect / mock dance). The marketing
// / SEO providers store operator-supplied tokens directly.
const DIRECT_CREDENTIAL_PROVIDERS: ReadonlySet<string> = new Set([
  "google_ads",
  "meta_ads",
  "google_analytics",
  "google_search_console",
]);

const STATUS_VARIANT: Record<
  IntegrationStatus,
  "outline" | "success" | "warning" | "destructive" | "default"
> = {
  disconnected: "outline",
  connecting: "warning",
  connected: "success",
  syncing: "warning",
  error: "destructive",
  needs_reconnect: "warning",
};

const STATUS_LABEL: Record<IntegrationStatus, string> = {
  disconnected: "Not connected",
  connecting: "Connecting…",
  connected: "Connected",
  syncing: "Syncing…",
  error: "Error",
  needs_reconnect: "Reconnect needed",
};

const PROVIDER_BLURB: Record<string, string> = {
  salesforce: "Pulls Leads + Accounts from your production Salesforce org.",
  carestack: "Pulls patient appointments + statuses from CareStack.",
  google_ads: "Pulls daily ad-spend + campaign metrics from Google Ads.",
  meta_ads: "Pulls daily ad-spend + campaign metrics from Meta Ads.",
  google_analytics: "Pulls GA4 traffic + conversion metrics.",
  google_search_console: "Pulls organic search clicks, impressions, and rank.",
};

/** A single operator-entered credential field rendered in the form. */
interface CredentialField {
  /** Maps to a key on `IntegrationCredentialBootstrapInput`. */
  name: string;
  label: string;
  /** `password` masks the input; `url` sets the input type to url. */
  type?: "text" | "password" | "url";
  required?: boolean;
  optional?: boolean;
  placeholder?: string;
  /** When set, the field is a comma-separated list mapped to `string[]`. */
  list?: boolean;
}

interface CredentialCopy {
  displayPlaceholder: string;
  savedMessage: string;
  fields: readonly CredentialField[];
}

const OAUTH_CLIENT_FIELDS: readonly CredentialField[] = [
  { name: "client_id", label: "OAuth client ID", required: true },
  {
    name: "client_secret",
    label: "OAuth client secret",
    type: "password",
    required: true,
  },
];

const CREDENTIAL_COPY: Record<CardBootstrapProvider, CredentialCopy> = {
  salesforce: {
    displayPlaceholder: "Salesforce production",
    savedMessage: "Salesforce app credentials saved.",
    fields: [
      { name: "client_id", label: "Connected App client ID", required: true },
      {
        name: "client_secret",
        label: "Connected App client secret",
        type: "password",
        required: true,
      },
      {
        name: "callback_url",
        label: "OAuth callback URL",
        type: "url",
        required: true,
        placeholder:
          "https://fusioncrm.app/api/integrations/salesforce/callback",
      },
      { name: "domain", label: "Salesforce login domain", required: true },
    ],
  },
  carestack: {
    displayPlaceholder: "CareStack production",
    savedMessage: "CareStack app credentials saved.",
    fields: [
      { name: "client_id", label: "CareStack client ID", required: true },
      {
        name: "client_secret",
        label: "CareStack client secret",
        type: "password",
        required: true,
      },
      {
        name: "vendor_key",
        label: "Vendor key",
        type: "password",
        required: true,
      },
      {
        name: "account_key",
        label: "Account key",
        type: "password",
        required: true,
      },
      { name: "account_id", label: "Account ID", required: true },
      {
        name: "idp_base_url",
        label: "Identity base URL",
        type: "url",
        required: true,
      },
      {
        name: "api_base_url",
        label: "API base URL",
        type: "url",
        required: true,
      },
      { name: "api_version", label: "API version", optional: true },
    ],
  },
  google_ads: {
    displayPlaceholder: "Google Ads — main account",
    savedMessage: "Google Ads credentials saved.",
    fields: [
      ...OAUTH_CLIENT_FIELDS,
      {
        name: "developer_token",
        label: "Developer token",
        type: "password",
        required: true,
      },
      {
        name: "refresh_token",
        label: "OAuth refresh token",
        type: "password",
        required: true,
      },
      {
        name: "login_customer_id",
        label: "Login customer ID (MCC)",
        optional: true,
        placeholder: "1234567890",
      },
      {
        name: "customer_ids",
        label: "Customer IDs",
        optional: true,
        list: true,
        placeholder: "1234567890, 0987654321",
      },
    ],
  },
  meta_ads: {
    displayPlaceholder: "Meta Ads — main account",
    savedMessage: "Meta Ads credentials saved.",
    fields: [
      {
        name: "access_token",
        label: "Long-lived access token",
        type: "password",
        required: true,
      },
      {
        name: "ad_account_ids",
        label: "Ad account IDs",
        optional: true,
        list: true,
        placeholder: "act_123456, act_654321",
      },
      { name: "app_id", label: "App ID", optional: true },
      {
        name: "app_secret",
        label: "App secret",
        type: "password",
        optional: true,
      },
    ],
  },
  google_analytics: {
    displayPlaceholder: "GA4 — main property",
    savedMessage: "Google Analytics credentials saved.",
    fields: [
      ...OAUTH_CLIENT_FIELDS,
      {
        name: "refresh_token",
        label: "OAuth refresh token",
        type: "password",
        required: true,
      },
      {
        name: "property_id",
        label: "GA4 property ID",
        required: true,
        placeholder: "123456789",
      },
    ],
  },
  google_search_console: {
    displayPlaceholder: "Search Console — main property",
    savedMessage: "Google Search Console credentials saved.",
    fields: [
      ...OAUTH_CLIENT_FIELDS,
      {
        name: "refresh_token",
        label: "OAuth refresh token",
        type: "password",
        required: true,
      },
      {
        name: "site_url",
        label: "Site URL",
        type: "url",
        optional: true,
        placeholder: "https://example.com/",
      },
    ],
  },
};

function isBootstrapProvider(
  provider: string,
): provider is CardBootstrapProvider {
  return provider in CREDENTIAL_COPY;
}

/** Split a comma / newline separated string into a trimmed, non-empty list. */
function parseList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function ProviderCard({ account }: { account: IntegrationAccount }) {
  const qc = useQueryClient();
  const connectStart = useConnectStart();
  const upsertCredential = useUpsertBootstrapCredential();
  const oauthCallback = useOAuthCallback();
  const triggerSync = useTriggerSync();
  const disconnect = useDisconnect();
  const [showCredentials, setShowCredentials] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({
    domain: "login.salesforce.com",
    idp_base_url: "https://identity.carestack.com",
    api_base_url: "https://api.carestack.com",
    api_version: "v1.0",
  });
  const credentialProvider = isBootstrapProvider(account.provider)
    ? account.provider
    : null;
  const credentialCopy = credentialProvider
    ? CREDENTIAL_COPY[credentialProvider]
    : null;

  async function onConnect() {
    // Marketing / SEO providers have no OAuth redirect — open the form inline.
    if (credentialProvider && DIRECT_CREDENTIAL_PROVIDERS.has(account.provider)) {
      openCredentialsForm();
      return;
    }
    const res = await connectStart.mutateAsync(account.provider);
    if (res.kind === "oauth_redirect") {
      // Mock OAuth: bypass the redirect dance and finalize inline.
      // Real OAuth: redirect to the external provider URL.
      if (res.redirect_url.includes("mock=1")) {
        await oauthCallback.mutateAsync(account.provider);
      } else {
        window.location.href = res.redirect_url;
      }
    } else if (res.kind === "instant_connected") {
      // Server already finished the auth — just refetch state.
      await qc.invalidateQueries({ queryKey: ["integrations"] });
    } else if (credentialProvider) {
      setSavedMessage(null);
      upsertCredential.reset();
      setShowCredentials(true);
    }
  }

  function setField(name: string, value: string) {
    setSavedMessage(null);
    upsertCredential.reset();
    setForm((current) => ({ ...current, [name]: value }));
  }

  function openCredentialsForm() {
    setSavedMessage(null);
    upsertCredential.reset();
    setShowCredentials(true);
  }

  function resetSecretFields() {
    setForm((current) => ({
      domain: current.domain || "login.salesforce.com",
      idp_base_url: current.idp_base_url || "https://identity.carestack.com",
      api_base_url: current.api_base_url || "https://api.carestack.com",
      api_version: current.api_version || "v1.0",
    }));
  }

  async function onCredentialSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!credentialProvider || !credentialCopy) {
      return;
    }
    // Build the typed payload strictly from this provider's field descriptors
    // so a value belonging to another provider can never leak into the body.
    const payload: Record<string, unknown> = {
      provider_kind: credentialProvider,
      credential_kind:
        credentialProvider === "carestack" ? "password_grant" : "api_key",
      display_name: form.display_name || undefined,
    };
    for (const field of credentialCopy.fields) {
      const raw = form[field.name] ?? "";
      if (field.list) {
        const list = parseList(raw);
        if (list.length > 0) {
          payload[field.name] = list;
        }
        continue;
      }
      const trimmed = raw.trim();
      if (trimmed.length > 0) {
        payload[field.name] = trimmed;
      }
    }
    await upsertCredential.mutateAsync(
      payload as IntegrationCredentialBootstrapInput,
    );
    resetSecretFields();
    setShowCredentials(false);
    setSavedMessage(credentialCopy.savedMessage);
  }

  // Marketing / SEO providers store credentials here but their pull + revoke
  // surfaces land in sibling tickets (ENG-490/492+). Until then we do not show
  // a "Sync now" / "Disconnect" button that would hit a route they lack.
  const supportsSyncActions = !DIRECT_CREDENTIAL_PROVIDERS.has(account.provider);

  const isBusy =
    connectStart.isPending ||
    upsertCredential.isPending ||
    triggerSync.isPending ||
    disconnect.isPending ||
    account.status === "connecting" ||
    account.status === "syncing";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="capitalize">
              {account.provider.replace(/_/g, " ")}
            </CardTitle>
            <CardDescription>
              {PROVIDER_BLURB[account.provider] ?? "External integration."}
            </CardDescription>
          </div>
          <Badge variant={STATUS_VARIANT[account.status]}>
            {STATUS_LABEL[account.status]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Display name</dt>
            <dd>{account.display_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Last sync</dt>
            <dd>{formatRelative(account.last_sync_at)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Last run</dt>
            <dd>
              {account.last_sync_summary
                ? `${account.last_sync_summary.records_pulled} records · ${account.last_sync_summary.status}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Error</dt>
            <dd className="text-destructive">{account.error_message ?? "—"}</dd>
          </div>
        </dl>

        {savedMessage && (
          <p
            role="status"
            className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
          >
            {savedMessage}
          </p>
        )}

        {showCredentials && credentialCopy && (
          <form
            onSubmit={onCredentialSubmit}
            className="space-y-3 rounded-md border bg-muted/40 p-4"
          >
            <div className="space-y-2">
              <Label htmlFor={`${account.provider}-display-name`}>
                Display name
              </Label>
              <Input
                id={`${account.provider}-display-name`}
                value={form.display_name ?? ""}
                onChange={(e) => setField("display_name", e.target.value)}
                placeholder={credentialCopy.displayPlaceholder}
              />
            </div>
            {credentialCopy.fields.map((field) => (
              <div key={field.name} className="space-y-2">
                <Label htmlFor={`${account.provider}-${field.name}`}>
                  {field.label}
                  {field.optional && (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      (optional)
                    </span>
                  )}
                </Label>
                <Input
                  id={`${account.provider}-${field.name}`}
                  type={field.type === "password" ? "password" : field.type === "url" ? "url" : "text"}
                  autoComplete={
                    field.type === "password" ? "new-password" : undefined
                  }
                  value={form[field.name] ?? ""}
                  onChange={(e) => setField(field.name, e.target.value)}
                  required={field.required}
                  placeholder={field.placeholder}
                />
                {field.list && (
                  <p className="text-xs text-muted-foreground">
                    Comma-separated.
                  </p>
                )}
              </div>
            ))}
            <div className="flex gap-2">
              <Button
                type="submit"
                size="sm"
                disabled={upsertCredential.isPending}
              >
                {upsertCredential.isPending ? "Saving…" : "Save credentials"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  upsertCredential.reset();
                  setShowCredentials(false);
                }}
              >
                Cancel
              </Button>
            </div>
            {upsertCredential.error && (
              <p className="text-sm text-destructive">
                Failed to save credentials.
              </p>
            )}
          </form>
        )}

        <div className="flex flex-wrap gap-2">
          {(account.status === "disconnected" ||
            account.status === "needs_reconnect") &&
            !showCredentials && (
            <Button onClick={onConnect} disabled={connectStart.isPending}>
              {connectStart.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : account.status === "needs_reconnect" ? (
                <RefreshCw className="h-4 w-4" />
              ) : (
                <Plug2 className="h-4 w-4" />
              )}
              {account.status === "needs_reconnect" ? "Reconnect" : "Connect"}
            </Button>
          )}
          {!showCredentials && credentialProvider && (
            <Button
              variant="outline"
              onClick={openCredentialsForm}
              disabled={isBusy}
            >
              <KeyRound className="h-4 w-4" />
              {account.status === "disconnected"
                ? "App credentials"
                : "Update credentials"}
            </Button>
          )}
          {supportsSyncActions &&
            (account.status === "connected" || account.status === "syncing") && (
            <Button
              variant="outline"
              onClick={() => triggerSync.mutate(account.provider)}
              disabled={isBusy}
            >
              {account.status === "syncing" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              {account.status === "syncing" ? "Syncing…" : "Sync now"}
            </Button>
          )}
          {supportsSyncActions &&
            (account.status === "connected" ||
              account.status === "error" ||
              account.status === "needs_reconnect") && (
            <Button
              variant="ghost"
              onClick={() => disconnect.mutate(account.provider)}
              disabled={isBusy}
            >
              <Trash2 className="h-4 w-4" />
              Disconnect
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
