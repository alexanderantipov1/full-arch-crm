"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { useUpsertBootstrapCredential } from "@/lib/api/hooks/useCredentials";
import type {
  IntegrationCredentialBootstrapInput,
} from "@/lib/api/schemas/tenant";

type BootstrapProvider = "salesforce" | "carestack" | "openai";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: BootstrapProvider;
  providerLabel: string;
  /** Optional pre-fill for `display_name`. Secrets are never pre-filled. */
  defaultDisplayName?: string | null;
  /** Distinguish first-time setup vs editing existing config (changes copy). */
  mode?: "setup" | "edit";
}

interface SalesforceFields {
  client_id: string;
  client_secret: string;
  callback_url: string;
  domain: string;
}

interface CareStackFields {
  vendor_key: string;
  account_key: string;
  account_id: string;
  idp_base_url: string;
  api_base_url: string;
  api_version: string;
}

interface OpenAIFields {
  api_key: string;
}

const SF_EMPTY: SalesforceFields = {
  client_id: "",
  client_secret: "",
  callback_url: "",
  domain: "login.salesforce.com",
};

const CS_EMPTY: CareStackFields = {
  vendor_key: "",
  account_key: "",
  account_id: "",
  idp_base_url: "",
  api_base_url: "",
  api_version: "v1.0.45",
};

const OPENAI_EMPTY: OpenAIFields = {
  api_key: "",
};

/**
 * Bootstrap-or-rotate credential modal.
 *
 * Backend `POST /tenant/credentials` (via `useUpsertBootstrapCredential`)
 * is an upsert — same endpoint handles first-time setup and full re-key.
 * Secret-bearing fields are masked and never echoed back. The server
 * response is metadata-only and gets re-parsed against
 * `TenantIntegrationCredentialSchema` to ensure no plaintext leaks back
 * into React state.
 */
export function BootstrapCredentialModal({
  open,
  onOpenChange,
  provider,
  providerLabel,
  defaultDisplayName,
  mode = "setup",
}: Props) {
  const { toast } = useToast();
  const mutation = useUpsertBootstrapCredential();

  const [displayName, setDisplayName] = useState(defaultDisplayName ?? "");
  const [sf, setSf] = useState<SalesforceFields>(SF_EMPTY);
  const [cs, setCs] = useState<CareStackFields>(CS_EMPTY);
  const [openai, setOpenai] = useState<OpenAIFields>(OPENAI_EMPTY);

  // Reset all state when the modal closes from the parent. Critical for
  // secret-bearing fields — never leak a pasted secret across opens.
  useEffect(() => {
    if (!open) {
      setDisplayName(defaultDisplayName ?? "");
      setSf(SF_EMPTY);
      setCs(CS_EMPTY);
      setOpenai(OPENAI_EMPTY);
    }
  }, [open, defaultDisplayName]);

  function build(): IntegrationCredentialBootstrapInput {
    if (provider === "salesforce") {
      return {
        provider_kind: "salesforce",
        credential_kind: "api_key",
        display_name: displayName.trim() || undefined,
        client_id: sf.client_id.trim(),
        client_secret: sf.client_secret.trim(),
        callback_url: sf.callback_url.trim(),
        domain: sf.domain.trim(),
      };
    }
    if (provider === "openai") {
      return {
        provider_kind: "openai",
        credential_kind: "api_key",
        display_name: displayName.trim() || undefined,
        api_key: openai.api_key.trim(),
      };
    }
    return {
      provider_kind: "carestack",
      credential_kind: "password_grant",
      display_name: displayName.trim() || undefined,
      vendor_key: cs.vendor_key.trim(),
      account_key: cs.account_key.trim(),
      account_id: cs.account_id.trim(),
      idp_base_url: cs.idp_base_url.trim(),
      api_base_url: cs.api_base_url.trim(),
      api_version: cs.api_version.trim(),
    };
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await mutation.mutateAsync(build());
      toast({
        title: mode === "setup" ? "Credential connected" : "Credential rotated",
        description: `${providerLabel} configuration saved.`,
      });
      onOpenChange(false);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Save failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  const isSalesforce = provider === "salesforce";
  const isCareStack = provider === "carestack";
  const isOpenAI = provider === "openai";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === "setup" ? "Connect" : "Edit"} {providerLabel}
          </DialogTitle>
          <DialogDescription>
            Paste the provider configuration from your{" "}
            {isSalesforce
              ? "Salesforce Connected App"
              : isCareStack
                ? "CareStack partner"
                : "OpenAI project"}{" "}
            console. Secrets are stored encrypted and are never shown back here.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="bootstrap-display-name">
              Display name (optional)
            </Label>
            <Input
              id="bootstrap-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={`${providerLabel} — primary`}
            />
          </div>

          {isSalesforce ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="sf-client-id">Client ID</Label>
                <Input
                  id="sf-client-id"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={sf.client_id}
                  onChange={(e) =>
                    setSf({ ...sf, client_id: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sf-client-secret">Client secret</Label>
                <Input
                  id="sf-client-secret"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={sf.client_secret}
                  onChange={(e) =>
                    setSf({ ...sf, client_secret: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="sf-callback-url">Callback URL</Label>
                <Input
                  id="sf-callback-url"
                  type="url"
                  autoComplete="off"
                  spellCheck={false}
                  value={sf.callback_url}
                  onChange={(e) =>
                    setSf({ ...sf, callback_url: e.target.value })
                  }
                  placeholder="https://fusioncrm.app/api/integrations/salesforce/callback"
                  required
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="sf-domain">Login domain</Label>
                <Input
                  id="sf-domain"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={sf.domain}
                  onChange={(e) => setSf({ ...sf, domain: e.target.value })}
                  placeholder="login.salesforce.com"
                  required
                />
              </div>
            </div>
          ) : null}

          {isCareStack ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="cs-vendor-key">Vendor key</Label>
                <Input
                  id="cs-vendor-key"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.vendor_key}
                  onChange={(e) =>
                    setCs({ ...cs, vendor_key: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cs-account-key">Account key</Label>
                <Input
                  id="cs-account-key"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.account_key}
                  onChange={(e) =>
                    setCs({ ...cs, account_key: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cs-account-id">Account ID</Label>
                <Input
                  id="cs-account-id"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.account_id}
                  onChange={(e) =>
                    setCs({ ...cs, account_id: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cs-api-version">API version</Label>
                <Input
                  id="cs-api-version"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.api_version}
                  onChange={(e) =>
                    setCs({ ...cs, api_version: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="cs-idp-base-url">IDP base URL</Label>
                <Input
                  id="cs-idp-base-url"
                  type="url"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.idp_base_url}
                  onChange={(e) =>
                    setCs({ ...cs, idp_base_url: e.target.value })
                  }
                  placeholder="https://idp.carestack.com"
                  required
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="cs-api-base-url">API base URL</Label>
                <Input
                  id="cs-api-base-url"
                  type="url"
                  autoComplete="off"
                  spellCheck={false}
                  value={cs.api_base_url}
                  onChange={(e) =>
                    setCs({ ...cs, api_base_url: e.target.value })
                  }
                  placeholder="https://api.carestack.com"
                  required
                />
              </div>
            </div>
          ) : null}

          {isOpenAI ? (
            <div className="space-y-2">
              <Label htmlFor="openai-api-key">API key</Label>
              <Input
                id="openai-api-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={openai.api_key}
                onChange={(e) =>
                  setOpenai({ ...openai, api_key: e.target.value })
                }
                placeholder="sk-..."
                required
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : null}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
