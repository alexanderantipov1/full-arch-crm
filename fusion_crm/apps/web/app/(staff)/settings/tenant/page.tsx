"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  Copy,
  ExternalLink,
  Globe,
  KeyRound,
  MessageSquare,
  RefreshCw,
  Save,
  Trash2,
  User,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NativeSelect } from "@/components/ui/native-select";
import { useToast } from "@/components/ui/toast";
import { useAccessList } from "@/lib/api/hooks/useAuth";
import {
  useCurrentTenant,
  useSyncLocationsFromCareStack,
  useUpsertTenantSetting,
} from "@/lib/api/hooks/useTenant";
import { useConnectStart } from "@/lib/api/hooks/useIntegrations";
import {
  useProviderMessengerMappings,
  useSetProviderMessengerUsername,
} from "@/lib/api/hooks/useMessengerMappings";
import type { ProviderMessengerMapping } from "@/lib/api/schemas/messengerMappings";
import { MessengerDirectoryCard } from "@/components/settings/MessengerDirectoryCard";
import { BootstrapCredentialModal } from "@/components/integrations/BootstrapCredentialModal";
import { CredentialEditModal } from "@/components/integrations/CredentialEditModal";
import { DisconnectConfirmModal } from "@/components/integrations/DisconnectConfirmModal";
import { formatDateTime, formatRelative, cn } from "@/lib/utils";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  isMailboxProvider,
  PROVIDER_CATEGORIES,
  PROVIDER_ICONS,
  PROVIDER_LABELS,
  type ProviderCategory,
} from "@/lib/integrations/providers";
import { MailboxConnectButton } from "@/components/integrations/MailboxConnectButton";
import { MailboxCredentialRow } from "@/components/integrations/MailboxCredentialRow";
import { VendorsManager } from "@/components/vendors/VendorsManager";
import { getSupportedTimezones, groupTimezones } from "@/lib/timezones";
import type {
  CredentialStatus,
  ProviderKind,
  Tenant,
  TenantIntegrationCredential,
  TenantLocation,
  TenantSetting,
  TenantStatus,
} from "@/lib/api/schemas/tenant";

const PROVIDER_LINK_BASES_SETTING_KEY = "provider_link_bases";

const SETTINGS_TABS = new Set([
  "overview",
  "locations",
  "integrations",
  "vendors",
  "access",
  "settings",
  "messenger",
]);

function statusBadge(status: TenantStatus) {
  if (status === "active") return <Badge variant="success">Active</Badge>;
  if (status === "paused") return <Badge variant="warning">Paused</Badge>;
  return <Badge variant="secondary">Archived</Badge>;
}

function subscriptionBadge(s: string | null) {
  if (!s) return <span className="text-muted-foreground">—</span>;
  if (s === "trial") return <Badge variant="warning">Trial</Badge>;
  if (s === "active" || s === "paid")
    return <Badge variant="success">{s}</Badge>;
  return <Badge variant="outline">{s}</Badge>;
}

function credentialStatusBadge(status: CredentialStatus) {
  if (status === "active") return <Badge variant="success">Active</Badge>;
  if (status === "expired") return <Badge variant="warning">Expired</Badge>;
  return <Badge variant="destructive">Revoked</Badge>;
}

function activeChip(isActive: boolean) {
  return isActive ? (
    <Badge variant="success">Active</Badge>
  ) : (
    <Badge variant="secondary">Disabled</Badge>
  );
}

interface FieldRowProps {
  label: string;
  children: React.ReactNode;
}

function FieldRow({ label, children }: FieldRowProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function TenantOverview({ tenant }: { tenant: Tenant }) {
  const groupedZones = useMemo(
    () => groupTimezones(getSupportedTimezones()),
    [],
  );
  const regions = useMemo(() => Object.keys(groupedZones).sort(), [
    groupedZones,
  ]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organisation</CardTitle>
        <CardDescription>
          Read-only summary of the tenant record. Editing is wired up after
          ENG-127.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,auto]">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FieldRow label="Name">{tenant.name}</FieldRow>
            <FieldRow label="Slug">
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                {tenant.slug}
              </code>
            </FieldRow>
            <FieldRow label="Status">{statusBadge(tenant.status)}</FieldRow>
            <FieldRow label="Subscription">
              {subscriptionBadge(tenant.subscription_status)}
            </FieldRow>
            <FieldRow label="Industry">{tenant.industry ?? "—"}</FieldRow>
            <FieldRow label="Tax id">{tenant.tax_id ?? "—"}</FieldRow>
            <FieldRow label="Primary email">
              {tenant.primary_email ? (
                <a
                  href={`mailto:${tenant.primary_email}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {tenant.primary_email}
                </a>
              ) : (
                "—"
              )}
            </FieldRow>
            <FieldRow label="Primary phone">
              {tenant.primary_phone ?? "—"}
            </FieldRow>
            <FieldRow label="Billing email">
              {tenant.billing_email ?? "—"}
            </FieldRow>
            <FieldRow label="Website">
              {tenant.website ? (
                <a
                  href={tenant.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
                >
                  {tenant.website.replace(/^https?:\/\//, "")}
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : (
                "—"
              )}
            </FieldRow>
            <FieldRow label="Timezone">
              <div title="Save settings — coming next">
                <NativeSelect
                  ariaLabel="Timezone"
                  value={tenant.timezone}
                  disabled
                  onChange={() => {
                    /* no-op until ENG-127 enables editing */
                  }}
                >
                  {regions.map((region) => (
                    <optgroup key={region} label={region}>
                      {(groupedZones[region] ?? []).map((zone) => (
                        <option key={zone} value={zone}>
                          {zone}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </NativeSelect>
              </div>
            </FieldRow>
            <FieldRow label="Locale">
              <div title="Save settings — coming next">
                <NativeSelect
                  ariaLabel="Locale"
                  value={tenant.locale}
                  disabled
                  onChange={() => {
                    /* no-op until ENG-127 enables editing */
                  }}
                >
                  <option value="en-US">en-US — English (United States)</option>
                  <option value="es-US">es-US — Español (EE. UU.)</option>
                </NativeSelect>
              </div>
            </FieldRow>
            <FieldRow label="Created">
              {formatDateTime(tenant.created_at)}
            </FieldRow>
          </div>
          <div className="flex items-start justify-center">
            {tenant.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logo_url}
                alt={`${tenant.name} logo`}
                className="h-32 w-32 rounded-lg border object-contain"
              />
            ) : (
              <div className="flex h-32 w-32 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/30 text-xs text-muted-foreground">
                No logo
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function LocationsTab({ locations }: { locations: TenantLocation[] }) {
  const { toast } = useToast();
  const sync = useSyncLocationsFromCareStack();

  const triggerSync = () => {
    sync.mutate(undefined, {
      onSuccess: (result) => {
        const total =
          result.created + result.updated + (result.deactivated ?? 0);
        toast({
          title: "Locations synced",
          description: `Created ${result.created}, updated ${result.updated}${result.deactivated ? `, deactivated ${result.deactivated}` : ""} (${total} of ${result.total_seen} processed).`,
          variant: "success",
        });
      },
      onError: (err) => {
        toast({
          title: "Sync failed",
          description: (err as Error).message,
          variant: "destructive",
        });
      },
    });
  };

  const syncButton = (
    <Button
      variant="outline"
      size="sm"
      className="gap-2"
      onClick={triggerSync}
      disabled={sync.isPending}
    >
      <RefreshCw
        className={cn("h-4 w-4", sync.isPending && "animate-spin")}
      />
      {sync.isPending ? "Syncing…" : "Re-sync from CareStack"}
    </Button>
  );

  if (locations.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Practice locations are sourced from CareStack — click below to
            pull them in.
          </p>
          {syncButton}
        </div>
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          No locations linked yet.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Practice locations sourced from CareStack. Use the row link to open
          the source record.
        </p>
        {syncButton}
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Short name</th>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">City</th>
              <th className="px-3 py-2 font-medium">Phone</th>
              <th className="px-3 py-2 font-medium">Active</th>
              <th className="px-3 py-2 font-medium">CS id</th>
              <th className="px-3 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {locations.map((loc) => {
              const csId = loc.external_ref?.["carestack_location_id"];
              const csIdStr = csId !== undefined ? String(csId) : null;
              const csUrl = csIdStr
                ? `https://app.carestack.com/locations/${csIdStr}`
                : null;
              return (
                <tr key={loc.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">
                    {loc.short_name ?? "—"}
                  </td>
                  <td className="px-3 py-2">{loc.name}</td>
                  <td className="px-3 py-2">
                    {loc.city ?? "—"}
                    {loc.state ? `, ${loc.state}` : ""}
                  </td>
                  <td className="px-3 py-2 text-xs">{loc.phone ?? "—"}</td>
                  <td className="px-3 py-2">{activeChip(loc.is_active)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {csIdStr ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {csUrl ? (
                      <a
                        href={csUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
                      >
                        View on CareStack
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface ConnectedCardProps {
  provider: ProviderKind;
  integration: TenantIntegrationCredential;
}

function SalesforceCallbackHint() {
  const { toast } = useToast();
  // The backend route is GET /api/integrations/salesforce/callback (mounted
  // at /api/integrations, see apps/api/routers/integrations.py). The base
  // URL must match the production OAUTH_REDIRECT_BASE_URL. We expose
  // NEXT_PUBLIC_OAUTH_REDIRECT_BASE_URL on the web side; if unset we fall
  // back to window.location.origin so local dev still produces a usable
  // URL to copy into the Salesforce Connected App config.
  const baseEnv = process.env.NEXT_PUBLIC_OAUTH_REDIRECT_BASE_URL;
  const base =
    baseEnv && baseEnv.length > 0
      ? baseEnv
      : typeof window !== "undefined"
        ? window.location.origin
        : "";
  const url = `${base.replace(/\/$/, "")}/api/integrations/salesforce/callback`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: "Copied", description: "Callback URL copied." });
    } catch {
      toast({
        title: "Copy failed",
        description: "Browser blocked clipboard access.",
        variant: "destructive",
      });
    }
  }

  return (
    <div className="mt-3 rounded-md border border-dashed bg-muted/40 p-2 text-[11px] text-muted-foreground">
      <div className="font-medium text-foreground">
        Salesforce Connected App callback URL
      </div>
      <div className="mt-0.5">
        Paste into your Salesforce Connected App → OAuth Settings →
        Callback URL.
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <code className="flex-1 truncate rounded bg-background px-2 py-1 font-mono text-[11px]">
          {url}
        </code>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={copy}
          className="h-7 gap-1.5 px-2"
        >
          <Copy className="h-3 w-3" />
          Copy
        </Button>
      </div>
    </div>
  );
}

function ConnectedCard({ provider, integration }: ConnectedCardProps) {
  const Icon = PROVIDER_ICONS[provider];
  const { toast } = useToast();
  const connectStart = useConnectStart();
  const [editOpen, setEditOpen] = useState(false);
  const [editConfigOpen, setEditConfigOpen] = useState(false);
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const isSalesforce = provider === "salesforce";
  const isCareStack = provider === "carestack";
  const isOpenAI = provider === "openai";
  const expiresLabel = integration.expires_at
    ? formatRelative(integration.expires_at)
    : "—";

  async function onReconnect() {
    try {
      // Legacy ConnectStart hook is typed against a narrow Provider enum
      // (`salesforce` | `hubspot` | `carestack` | `manual` | `import`).
      // `provider` here is the broader ProviderKind; the runtime guards
      // above ensure we only reach this path for salesforce.
      const res = await connectStart.mutateAsync(provider as "salesforce");
      if (res.kind !== "oauth_redirect" || !res.redirect_url) {
        toast({
          title: "Unexpected response",
          description:
            "Server did not return an OAuth redirect URL for this provider.",
          variant: "destructive",
        });
        return;
      }
      window.open(res.redirect_url, "_blank", "noopener,noreferrer");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Reconnect failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  return (
    <div className="flex flex-col rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">
              {PROVIDER_LABELS[provider]}
            </span>
            {credentialStatusBadge(integration.status)}
          </div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">
            {integration.display_name ?? integration.credential_kind}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span
              title={
                integration.last_refreshed_at
                  ? formatDateTime(integration.last_refreshed_at)
                  : undefined
              }
            >
              <span className="font-medium">Refreshed:</span>{" "}
              {formatRelative(integration.last_refreshed_at)}
            </span>
            <span
              title={
                integration.expires_at
                  ? formatDateTime(integration.expires_at)
                  : undefined
              }
            >
              <span className="font-medium">Expires:</span> {expiresLabel}
            </span>
          </div>
        </div>
      </div>
      {/* Actions row — full-width under the metadata so a 3-button line
          can't overflow the card on narrow viewports. */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
        {isSalesforce ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onReconnect}
            disabled={connectStart.isPending}
            className="gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reconnect
          </Button>
        ) : null}
        {isCareStack ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditOpen(true)}
            className="gap-1.5"
          >
            <KeyRound className="h-3.5 w-3.5" />
            Edit key
          </Button>
        ) : null}
        {isOpenAI ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditConfigOpen(true)}
            className="gap-1.5"
          >
            <KeyRound className="h-3.5 w-3.5" />
            Edit key
          </Button>
        ) : null}
        {(isSalesforce || isCareStack) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setEditConfigOpen(true)}
            className="gap-1.5"
            title="Edit full provider config (rotate all secrets)"
          >
            Edit config
          </Button>
        ) : null}
        {(isSalesforce || isCareStack) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDisconnectOpen(true)}
            className="ml-auto gap-1.5 text-destructive hover:text-destructive"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Disconnect
          </Button>
        ) : null}
      </div>
      {isSalesforce ? <SalesforceCallbackHint /> : null}

      {isCareStack ? (
        <CredentialEditModal
          open={editOpen}
          onOpenChange={setEditOpen}
          provider="carestack"
          providerLabel={PROVIDER_LABELS.carestack}
          defaultDisplayName={integration.display_name}
        />
      ) : null}
      {(isSalesforce || isCareStack) ? (
        <DisconnectConfirmModal
          open={disconnectOpen}
          onOpenChange={setDisconnectOpen}
          provider={provider as "salesforce" | "carestack"}
          providerLabel={PROVIDER_LABELS[provider]}
        />
      ) : null}
      {(isSalesforce || isCareStack || isOpenAI) ? (
        <BootstrapCredentialModal
          open={editConfigOpen}
          onOpenChange={setEditConfigOpen}
          provider={provider as "salesforce" | "carestack" | "openai"}
          providerLabel={PROVIDER_LABELS[provider]}
          defaultDisplayName={integration.display_name}
          mode="edit"
        />
      ) : null}
    </div>
  );
}

function NotConnectedCard({ provider }: { provider: ProviderKind }) {
  const Icon = PROVIDER_ICONS[provider];
  const canConnect = isMailboxProvider(provider);
  const isBootstrappable =
    provider === "salesforce" ||
    provider === "carestack" ||
    provider === "openai";
  const [bootstrapOpen, setBootstrapOpen] = useState(false);
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-dashed bg-muted/20 p-4">
      <div className="flex flex-1 items-start gap-3">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-muted-foreground">
            {PROVIDER_LABELS[provider]}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            Not connected
          </div>
        </div>
      </div>
      {canConnect ? (
        <MailboxConnectButton provider={provider} label="Connect" />
      ) : isBootstrappable ? (
        <>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setBootstrapOpen(true)}
          >
            Set up
          </Button>
          <BootstrapCredentialModal
            open={bootstrapOpen}
            onOpenChange={setBootstrapOpen}
            provider={provider as "salesforce" | "carestack" | "openai"}
            providerLabel={PROVIDER_LABELS[provider]}
            mode="setup"
          />
        </>
      ) : (
        <span title="Generic API-key form ships with ENG-198">
          <Button variant="outline" size="sm" disabled>
            Connect
          </Button>
        </span>
      )}
    </div>
  );
}

function MailboxesSection({
  integrations,
  locations,
}: {
  integrations: TenantIntegrationCredential[];
  locations: TenantLocation[];
}) {
  const mailboxes = integrations.filter((c) =>
    isMailboxProvider(c.provider_kind as ProviderKind),
  );

  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold tracking-tight">
            Email mailboxes
          </h3>
          <p className="text-xs text-muted-foreground">
            Operator-owned Google Workspace / Microsoft 365 inboxes used by
            outreach campaigns. Add as many as you like — pin to a location,
            tag for routing, set one as default per provider.
          </p>
        </div>
        <div className="flex gap-2">
          <MailboxConnectButton
            provider="google_workspace"
            label="Connect Google Workspace"
          />
          <MailboxConnectButton
            provider="microsoft_365"
            label="Connect Microsoft 365"
          />
        </div>
      </div>

      {mailboxes.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          No mailboxes connected yet. Click a Connect button above to start
          the OAuth flow.
        </div>
      ) : (
        <div className="space-y-3">
          {mailboxes.map((m) => (
            <MailboxCredentialRow
              key={m.id}
              integration={m}
              locations={locations}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function IntegrationsTab({
  integrations,
  locations,
}: {
  integrations: TenantIntegrationCredential[];
  locations: TenantLocation[];
}) {
  // Pre-index registered credentials by provider_kind so the per-category
  // grids can render Connected vs NotConnected with O(1) lookups. For the
  // mailbox category (which is multi-credential) we handle it separately
  // via MailboxesSection.
  const byProvider = useMemo(() => {
    const map = new Map<ProviderKind, TenantIntegrationCredential>();
    for (const cred of integrations) {
      if (!isMailboxProvider(cred.provider_kind as ProviderKind)) {
        map.set(cred.provider_kind, cred);
      }
    }
    return map;
  }, [integrations]);

  return (
    <div className="space-y-8">
      <MailboxesSection
        integrations={integrations}
        locations={locations}
      />

      {CATEGORY_ORDER.filter((c) => c !== "email").map(
        (cat: ProviderCategory) => {
          const providers = PROVIDER_CATEGORIES[cat];
          return (
            <section key={cat} className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold tracking-tight">
                  {CATEGORY_LABELS[cat]}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {providers.length} provider
                  {providers.length === 1 ? "" : "s"} in this category
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {providers.map((provider) => {
                  const existing = byProvider.get(provider);
                  return existing ? (
                    <ConnectedCard
                      key={provider}
                      provider={provider}
                      integration={existing}
                    />
                  ) : (
                    <NotConnectedCard key={provider} provider={provider} />
                  );
                })}
              </div>
            </section>
          );
        },
      )}
    </div>
  );
}

function providerLinkBaseValue(
  settings: TenantSetting[],
  field: "salesforce_lightning_base_url" | "carestack_app_base_url",
): string {
  const setting = settings.find(
    (s) => s.key === PROVIDER_LINK_BASES_SETTING_KEY,
  );
  if (!setting || !isRecord(setting.value)) return "";
  const value = setting.value[field];
  return typeof value === "string" ? value : "";
}

function normalizeEditableUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isValidHttpsUrl(value: string): boolean {
  if (!value.trim()) return true;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function ProviderLinkBasesCard({ settings }: { settings: TenantSetting[] }) {
  const { toast } = useToast();
  const upsertSetting = useUpsertTenantSetting();
  const initialSalesforceUrl = providerLinkBaseValue(
    settings,
    "salesforce_lightning_base_url",
  );
  const initialCarestackUrl = providerLinkBaseValue(
    settings,
    "carestack_app_base_url",
  );
  const [salesforceUrl, setSalesforceUrl] = useState(initialSalesforceUrl);
  const [carestackUrl, setCarestackUrl] = useState(initialCarestackUrl);

  useEffect(() => {
    setSalesforceUrl(initialSalesforceUrl);
    setCarestackUrl(initialCarestackUrl);
  }, [initialCarestackUrl, initialSalesforceUrl]);

  const normalizedSalesforceUrl = normalizeEditableUrl(salesforceUrl);
  const normalizedCarestackUrl = normalizeEditableUrl(carestackUrl);
  const salesforceValid = isValidHttpsUrl(normalizedSalesforceUrl);
  const carestackValid = isValidHttpsUrl(normalizedCarestackUrl);
  const hasChanges =
    normalizedSalesforceUrl !== normalizeEditableUrl(initialSalesforceUrl) ||
    normalizedCarestackUrl !== normalizeEditableUrl(initialCarestackUrl);
  const canSave =
    hasChanges &&
    salesforceValid &&
    carestackValid &&
    !upsertSetting.isPending;

  function save() {
    upsertSetting.mutate(
      {
        key: PROVIDER_LINK_BASES_SETTING_KEY,
        value: {
          salesforce_lightning_base_url: normalizedSalesforceUrl,
          carestack_app_base_url: normalizedCarestackUrl,
        },
      },
      {
        onSuccess: () => {
          toast({
            title: "Provider links saved",
            description: "Source links will use the configured company domains.",
            variant: "success",
          });
        },
        onError: (err) => {
          toast({
            title: "Save failed",
            description: err.message,
            variant: "destructive",
          });
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider link domains</CardTitle>
        <CardDescription>
          Company domains used by Source links on person records.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="salesforce-lightning-base-url">
              Salesforce Lightning base URL
            </Label>
            <Input
              id="salesforce-lightning-base-url"
              value={salesforceUrl}
              onChange={(event) => setSalesforceUrl(event.target.value)}
              placeholder="https://fusiondentalimplants.lightning.force.com"
              aria-invalid={!salesforceValid}
            />
            {!salesforceValid ? (
              <p className="text-xs text-destructive">Enter an https:// URL.</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="carestack-app-base-url">
              CareStack app base URL
            </Label>
            <Input
              id="carestack-app-base-url"
              value={carestackUrl}
              onChange={(event) => setCarestackUrl(event.target.value)}
              placeholder="https://antipov.carestack.com"
              aria-invalid={!carestackValid}
            />
            {!carestackValid ? (
              <p className="text-xs text-destructive">Enter an https:// URL.</p>
            ) : null}
          </div>
        </div>

        <div className="rounded-md border bg-muted/30 p-3 text-xs">
          <div className="font-medium text-foreground">Preview</div>
          <div className="mt-2 space-y-1 font-mono text-muted-foreground">
            <div>
              {normalizedSalesforceUrl || "https://login.salesforce.com"}
              /lightning/r/Lead/00Q.../view
            </div>
            <div>
              {normalizedCarestackUrl || "https://app.carestack.com"}
              /patient/2246613
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            onClick={save}
            disabled={!canSave}
            className="gap-2"
          >
            <Save className="h-4 w-4" />
            {upsertSetting.isPending ? "Saving…" : "Save domains"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function normalizeUsername(value: string): string {
  return value.trim().replace(/^@+/, "").trim();
}

function MessengerMappingRow({
  mapping,
}: {
  mapping: ProviderMessengerMapping;
}) {
  const { toast } = useToast();
  const setMapping = useSetProviderMessengerUsername();
  const initial = mapping.mattermost_username ?? "";
  const [username, setUsername] = useState(initial);

  useEffect(() => {
    setUsername(initial);
  }, [initial]);

  const normalized = normalizeUsername(username);
  const hasChanges = normalized !== normalizeUsername(initial);
  const canSave = hasChanges && normalized.length > 0 && !setMapping.isPending;

  function save() {
    setMapping.mutate(
      {
        carestackProviderId: mapping.carestack_provider_id,
        mattermostUsername: normalized,
      },
      {
        onSuccess: (result) => {
          toast({
            title: "Doctor mapped",
            description: `${mapping.actor_name} → @${result.mattermost_username ?? "(unknown)"}`,
            variant: "success",
          });
        },
        onError: (err) => {
          toast({
            title: "Save failed",
            description: err.message,
            variant: "destructive",
          });
        },
      },
    );
  }

  return (
    <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Doctor</Label>
        <div className="text-sm font-medium">{mapping.actor_name}</div>
        <div className="font-mono text-xs text-muted-foreground">
          cs={mapping.carestack_provider_id}
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor={`mm-${mapping.carestack_provider_id}`} className="text-xs">
          Mattermost username
        </Label>
        <Input
          id={`mm-${mapping.carestack_provider_id}`}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="drantipov"
        />
      </div>
      <Button
        type="button"
        onClick={save}
        disabled={!canSave}
        className="gap-2"
      >
        <Save className="h-4 w-4" />
        {setMapping.isPending ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}

function MessengerMappingsCard() {
  const { data, isLoading, isError } = useProviderMessengerMappings();
  const items = data?.items ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Doctor Mattermost handles
        </CardTitle>
        <CardDescription>
          Map each CareStack provider to a Mattermost username so consult
          reminders @mention the assigned doctor. The doctor must also be a
          member of the team&apos;s #consult-reminders channel to be pinged.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive">
            Could not load providers. Try reloading.
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            No CareStack providers found yet. Providers appear here after a
            CareStack sync.
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((mapping) => (
              <MessengerMappingRow
                key={mapping.carestack_provider_id}
                mapping={mapping}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SettingsTab({ settings }: { settings: TenantSetting[] }) {
  return (
    <div className="space-y-4">
      <ProviderLinkBasesCard settings={settings} />
      <MessengerMappingsCard />

      {settings.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          No custom settings yet.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-1/3 px-3 py-2 font-medium">Key</th>
                <th className="px-3 py-2 font-medium">Value</th>
                <th className="px-3 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {settings.map((s) => (
                <tr key={s.key} className="border-b last:border-0 align-top">
                  <td className="px-3 py-2 font-mono text-xs">{s.key}</td>
                  <td className="px-3 py-2">
                    <pre className="overflow-x-auto rounded bg-muted/40 p-2 text-xs">
                      {JSON.stringify(s.value, null, 2)}
                    </pre>
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {formatDateTime(s.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function accessRoleLabel(role: string): string {
  if (role === "roles/iap.httpsResourceAccessor") return "Staff access";
  return role.replace(/^roles\//, "");
}

function AccessKindIcon({ kind }: { kind: string }) {
  if (kind === "user") return <User className="h-4 w-4 text-blue-600" />;
  if (kind === "domain") return <Globe className="h-4 w-4 text-emerald-600" />;
  if (kind === "serviceAccount")
    return <Bot className="h-4 w-4 text-amber-600" />;
  if (kind === "group") return <Users className="h-4 w-4 text-violet-600" />;
  return <KeyRound className="h-4 w-4 text-muted-foreground" />;
}

function AccessTab() {
  const { data, isLoading, error } = useAccessList();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>People with access</CardTitle>
            <CardDescription>
              Anyone Google IAP currently allows to reach this app. Add or
              remove access via <code>gcloud iap web</code> at the project
              level — this view is read-only.
            </CardDescription>
          </div>
          {data?.live === false && (
            <Badge variant="warning">Offline view</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {error && (
          <p className="text-sm text-destructive">
            Failed to load access list: {(error as Error).message}
          </p>
        )}
        {data?.live === false && data.reason && (
          <p className="mb-3 text-xs text-muted-foreground">
            {data.reason}. Run on Cloud Run with{" "}
            <code>roles/iam.securityReviewer</code> to see the live list.
          </p>
        )}
        {data && data.members.length === 0 && data.live && (
          <p className="text-sm text-muted-foreground">
            No bindings found on the IAP backend services.
          </p>
        )}
        {data && data.members.length > 0 && (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-left font-medium">Identity</th>
                  <th className="px-3 py-2 text-left font-medium">Role</th>
                  <th className="px-3 py-2 text-left font-medium">Surfaces</th>
                </tr>
              </thead>
              <tbody>
                {data.members.map((m, i) => (
                  <tr
                    key={`${m.kind}:${m.value}:${m.role}:${i}`}
                    className="border-t"
                  >
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <AccessKindIcon kind={m.kind} />
                        <span className="text-xs text-muted-foreground">
                          {m.kind}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{m.value}</td>
                    <td className="px-3 py-2">{accessRoleLabel(m.role)}</td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        {m.surfaces.map((s) => (
                          <Badge key={s} variant="outline">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function TenantSettingsPage() {
  const { data, isLoading, error } = useCurrentTenant();
  const search = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const requestedTab = search.get("tab");
  const activeTab = SETTINGS_TABS.has(requestedTab ?? "")
    ? requestedTab!
    : "overview";

  // Surface ?connected=...&mailbox=... + ?oauth_error=... toasts emitted by
  // the OAuth callback redirect. Clear the params after firing so a hard
  // refresh doesn't re-toast.
  useEffect(() => {
    const connected = search.get("connected");
    const mailbox = search.get("mailbox");
    const oauthError = search.get("oauth_error");
    const provider = search.get("provider");

    if (connected) {
      toast({
        title: "Mailbox connected",
        description: mailbox
          ? `${mailbox} is now available for outreach.`
          : `${connected} is now connected.`,
        variant: "success",
      });
    } else if (oauthError) {
      toast({
        title: "OAuth failed",
        description: `${provider ?? "Provider"} returned: ${oauthError}`,
        variant: "destructive",
      });
    }

    if (connected || oauthError) {
      // Drop the query params; keep the same path so the tab selection
      // and scroll position are preserved.
      router.replace("/settings/tenant?tab=integrations");
    }
  }, [search, router, toast]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Tenant settings
        </h1>
        <p className="text-sm text-muted-foreground">
          Read-only view of this workspace&apos;s organisation profile, linked
          locations, integration credentials, and operational toggles. Mutation
          flows ship later.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load tenant settings: {(error as Error).message}
        </div>
      )}

      {isLoading || !data ? (
        <div className="space-y-4">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <Tabs
          value={activeTab}
          onValueChange={(value) =>
            router.replace(
              value === "overview"
                ? "/settings/tenant"
                : `/settings/tenant?tab=${value}`,
            )
          }
        >
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="locations">
              Locations
              <span className="ml-1.5 rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">
                {data.locations.length}
              </span>
            </TabsTrigger>
            <TabsTrigger value="integrations">
              Integrations
              <span className="ml-1.5 rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">
                {data.integrations.length}
              </span>
            </TabsTrigger>
            <TabsTrigger value="vendors">Vendors</TabsTrigger>
            <TabsTrigger value="access">Access</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
            <TabsTrigger value="messenger">Messenger</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <TenantOverview tenant={data.tenant} />
          </TabsContent>
          <TabsContent value="locations">
            <LocationsTab locations={data.locations} />
          </TabsContent>
          <TabsContent value="integrations">
            <IntegrationsTab
              integrations={data.integrations}
              locations={data.locations}
            />
          </TabsContent>
          <TabsContent value="vendors">
            <VendorsManager />
          </TabsContent>
          <TabsContent value="access">
            <AccessTab />
          </TabsContent>
          <TabsContent value="settings">
            <SettingsTab settings={data.settings} />
          </TabsContent>
          <TabsContent value="messenger">
            <MessengerDirectoryCard />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
