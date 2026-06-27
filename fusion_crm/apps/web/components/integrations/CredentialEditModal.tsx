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
import { useApiKeyConnect } from "@/lib/api/hooks/useIntegrations";
import type { Provider } from "@/lib/api/schemas";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: Provider;
  providerLabel: string;
  /** Pre-fill display name for the human-readable credential label. */
  defaultDisplayName?: string | null;
}

/**
 * Modal for rotating a non-OAuth API-key credential (currently CareStack).
 *
 * Submits via ``POST /integrations/{provider}/api-key``. The endpoint
 * upserts the credential and re-encrypts the payload. The stored key is
 * never echoed back to the DOM — the response is metadata only.
 */
export function CredentialEditModal({
  open,
  onOpenChange,
  provider,
  providerLabel,
  defaultDisplayName,
}: Props) {
  const { toast } = useToast();
  const [apiKey, setApiKey] = useState("");
  const [displayName, setDisplayName] = useState(defaultDisplayName ?? "");
  const mutation = useApiKeyConnect(provider);

  // Reset form state when the modal closes externally so the next open
  // does not inherit a stale (or worse, secret-bearing) input.
  useEffect(() => {
    if (!open) {
      setApiKey("");
      setDisplayName(defaultDisplayName ?? "");
    }
  }, [open, defaultDisplayName]);

  function reset() {
    setApiKey("");
    setDisplayName(defaultDisplayName ?? "");
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!apiKey.trim()) {
      toast({
        title: "API key required",
        description: "Paste the provider API key before saving.",
        variant: "destructive",
      });
      return;
    }
    try {
      await mutation.mutateAsync({
        api_key: apiKey.trim(),
        display_name: displayName.trim() || undefined,
      });
      toast({
        title: "Credential saved",
        description: `${providerLabel} key rotated.`,
      });
      reset();
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

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update {providerLabel} API key</DialogTitle>
          <DialogDescription>
            Paste the new key from the provider console. The previous key
            is replaced; this credential row stays — only the secret rotates.
            Stored values are never shown back here.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="credential-api-key">API key</Label>
            <Input
              id="credential-api-key"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="paste the new key"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="credential-display-name">
              Display name (optional)
            </Label>
            <Input
              id="credential-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={`${providerLabel} — primary`}
            />
          </div>
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
