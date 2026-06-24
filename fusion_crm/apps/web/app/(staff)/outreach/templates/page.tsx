"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTemplates } from "@/lib/api/hooks/useOutreach";
import { formatRelative } from "@/lib/utils";
import type {
  TemplateCategory,
  TemplateStatus,
} from "@/lib/api/schemas/outreach";

function categoryBadge(c: TemplateCategory) {
  if (c === "marketing") return <Badge variant="default">Marketing</Badge>;
  if (c === "clinical") return <Badge variant="warning">Clinical</Badge>;
  if (c === "transactional")
    return <Badge variant="secondary">Transactional</Badge>;
  return <Badge variant="outline">Operational</Badge>;
}

function statusBadge(s: TemplateStatus) {
  if (s === "active") return <Badge variant="success">Active</Badge>;
  if (s === "draft") return <Badge variant="warning">Draft</Badge>;
  return <Badge variant="secondary">Archived</Badge>;
}

export default function TemplatesPage() {
  const { data, isLoading, error } = useTemplates();

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Outreach templates
          </h1>
          <p className="text-sm text-muted-foreground">
            Mustache + MJML email templates used by outreach campaigns and
            transactional sends.
          </p>
        </div>
        <Link href="/outreach/templates/new">
          <Button className="gap-1.5">
            <Plus className="h-4 w-4" />
            New template
          </Button>
        </Link>
      </header>

      {error ? (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load templates: {(error as Error).message}
        </div>
      ) : null}

      {isLoading || !data ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : data.items.length === 0 ? (
        <div className="rounded-md border border-dashed p-10 text-center text-sm text-muted-foreground">
          No templates yet. Create your first one with the button above.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Category</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Version</th>
                <th className="px-3 py-2 font-medium">Updated</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id} className="border-b last:border-0">
                  <td className="px-3 py-2">
                    <div className="font-medium">{t.name}</div>
                    {t.description ? (
                      <div className="text-xs text-muted-foreground">
                        {t.description}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">{categoryBadge(t.category)}</td>
                  <td className="px-3 py-2">{statusBadge(t.status)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    v{t.version}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {formatRelative(t.updated_at)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/outreach/templates/${t.id}/edit`}
                      className="text-xs text-primary underline-offset-4 hover:underline"
                    >
                      Edit
                    </Link>
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
