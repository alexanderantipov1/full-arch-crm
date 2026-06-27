"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { TemplateForm } from "@/components/outreach/TemplateForm";
import { useTemplate } from "@/lib/api/hooks/useOutreach";

export default function EditTemplatePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { data, isLoading, error } = useTemplate(id);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header className="space-y-2">
        <Link
          href="/outreach/templates"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Back to templates
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          Edit template
        </h1>
        {data ? (
          <p className="text-sm text-muted-foreground">
            Editing <span className="font-medium">{data.name}</span> — v
            {data.version}, last updated{" "}
            {new Date(data.updated_at).toLocaleString()}.
          </p>
        ) : null}
      </header>

      {error ? (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load template: {(error as Error).message}
        </div>
      ) : null}

      {isLoading || !data ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <TemplateForm initial={data} />
      )}
    </div>
  );
}
