"use client";

import { useState } from "react";
import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { attributionDoc } from "@/lib/docs/attributionDoc";
import type { DocSection } from "@/lib/docs/paymentsDoc";

/**
 * "Docs" button + popup explaining the vendor-attribution workflow (ENG-569).
 * Content lives in `lib/docs/attributionDoc.ts`; the section renderer mirrors
 * the Payments docs page so the two stay visually consistent.
 */
export function AttributionDocsDialog() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={() => setOpen(true)}
      >
        <BookOpen className="h-4 w-4" />
        Docs
      </Button>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            {attributionDoc.title}
          </DialogTitle>
          <DialogDescription>{attributionDoc.subtitle}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {attributionDoc.sections.map((section) => (
            <DocSectionBlock key={section.heading} section={section} />
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DocSectionBlock({ section }: { section: DocSection }) {
  return (
    <section className="space-y-2 rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">{section.heading}</h2>

      {section.paragraphs?.map((paragraph, i) => (
        <p key={i} className="text-sm leading-relaxed text-muted-foreground">
          {paragraph}
        </p>
      ))}

      {section.bullets && (
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-muted-foreground">
          {section.bullets.map((bullet, i) => (
            <li key={i}>{bullet}</li>
          ))}
        </ul>
      )}

      {section.table && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b text-[10px] uppercase tracking-wide text-muted-foreground">
                {section.table.headers.map((header) => (
                  <th key={header} className="px-2 py-1.5 font-medium">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {section.table.rows.map((row, ri) => (
                <tr key={ri} className="border-b last:border-b-0 align-top">
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className={
                        ci === 0
                          ? "px-2 py-1.5 font-mono text-[11px]"
                          : "px-2 py-1.5 text-muted-foreground"
                      }
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {section.formula && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted px-3 py-2 text-xs leading-relaxed">
          {section.formula}
        </pre>
      )}
    </section>
  );
}
