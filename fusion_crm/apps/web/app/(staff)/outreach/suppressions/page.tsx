"use client";

import { Loader2, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import {
  useRemoveSuppression,
  useSuppressions,
} from "@/lib/api/hooks/useOutreach";
import { formatDateTime } from "@/lib/utils";
import type { SuppressionReason } from "@/lib/api/schemas/outreach";

function reasonBadge(r: SuppressionReason) {
  if (r === "operator") return <Badge variant="secondary">Operator</Badge>;
  if (r === "one_click") return <Badge variant="outline">One-click</Badge>;
  if (r === "bounce_hard")
    return <Badge variant="destructive">Hard bounce</Badge>;
  return <Badge variant="destructive">Complaint</Badge>;
}

export default function SuppressionsPage() {
  const { data, isLoading, error } = useSuppressions();
  const remove = useRemoveSuppression();
  const { toast } = useToast();

  async function onRemove(email: string) {
    if (
      !window.confirm(
        `Remove ${email} from the suppression list? They will become eligible for outreach again.`,
      )
    ) {
      return;
    }
    try {
      await remove.mutateAsync(email);
      toast({
        title: "Suppression removed",
        description: `${email} can now receive outreach.`,
        variant: "success",
      });
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Unknown error";
      toast({
        title: "Remove failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Suppression list
        </h1>
        <p className="text-sm text-muted-foreground">
          Recipients excluded from outreach for this tenant — hard bounces,
          one-click unsubscribes, complaints, and operator-issued blocks.
          Removing a row makes the recipient eligible again.
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load suppressions: {(error as Error).message}
        </div>
      ) : null}

      {isLoading || !data ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : data.items.length === 0 ? (
        <div className="rounded-md border border-dashed p-10 text-center text-sm text-muted-foreground">
          No suppressions for this tenant.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Recipient</th>
                <th className="px-3 py-2 font-medium">Reason</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr
                  key={s.recipient_email_normalised}
                  className="border-b last:border-0"
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    {s.recipient_email_normalised}
                  </td>
                  <td className="px-3 py-2">{reasonBadge(s.reason)}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {formatDateTime(s.created_at)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        onRemove(s.recipient_email_normalised)
                      }
                      disabled={remove.isPending}
                      className="gap-1.5 text-destructive hover:text-destructive"
                    >
                      {remove.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Remove
                    </Button>
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
