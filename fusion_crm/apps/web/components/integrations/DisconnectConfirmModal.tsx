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
import { useDisconnect } from "@/lib/api/hooks/useIntegrations";
import type { Provider } from "@/lib/api/schemas";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: Provider;
  providerLabel: string;
}

/**
 * Destructive confirmation modal for disconnecting a provider credential.
 *
 * Submit becomes enabled only after the operator types the provider's
 * human-readable name (case-insensitive, trimmed) into the confirmation
 * field. Calls ``DELETE /integrations/{provider}`` via ``useDisconnect``.
 */
export function DisconnectConfirmModal({
  open,
  onOpenChange,
  provider,
  providerLabel,
}: Props) {
  const { toast } = useToast();
  const [typed, setTyped] = useState("");
  const mutation = useDisconnect();

  // Reset typed-confirmation when the modal transitions to closed via the
  // parent (e.g. external state change) — not just via the internal close
  // wrapper. Keeps the confirmation gate from leaking state across opens.
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const matchesConfirmation =
    typed.trim().toLowerCase() === providerLabel.trim().toLowerCase();

  function reset() {
    setTyped("");
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!matchesConfirmation) return;
    try {
      await mutation.mutateAsync(provider);
      toast({
        title: "Disconnected",
        description: `${providerLabel} credential revoked.`,
      });
      reset();
      onOpenChange(false);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({
        title: "Disconnect failed",
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
          <DialogTitle>Disconnect {providerLabel}?</DialogTitle>
          <DialogDescription>
            This revokes the stored credential. Any ingest / outreach
            jobs that depend on {providerLabel} will fail until a new
            credential is connected. The action is recorded in the
            audit log.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="disconnect-confirm">
              Type <span className="font-mono">{providerLabel}</span> to confirm
            </Label>
            <Input
              id="disconnect-confirm"
              type="text"
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={providerLabel}
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
            <Button
              type="submit"
              variant="destructive"
              disabled={!matchesConfirmation || mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : null}
              Disconnect
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
