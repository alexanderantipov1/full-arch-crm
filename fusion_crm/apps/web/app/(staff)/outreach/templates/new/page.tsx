"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { TemplateForm } from "@/components/outreach/TemplateForm";

export default function NewTemplatePage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <header className="space-y-2">
        <Link
          href="/outreach/templates"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Back to templates
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New template</h1>
        <p className="text-sm text-muted-foreground">
          Compose the subject + body. Mustache placeholders limited to the
          allowlist on the right.
        </p>
      </header>

      <TemplateForm initial={null} />
    </div>
  );
}
