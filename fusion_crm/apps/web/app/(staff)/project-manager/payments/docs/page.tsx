"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, Info, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DocLanguage,
  DocSection,
  paymentsDoc,
} from "@/lib/docs/paymentsDoc";

export default function PaymentsDocsPage() {
  const [language, setLanguage] = useState<DocLanguage>("en");
  const content = paymentsDoc[language];

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-6">
      <header className="space-y-3">
        <Button asChild variant="ghost" size="sm" className="w-fit px-0">
          <Link href="/project-manager/payments">
            <ArrowLeft className="h-4 w-4" />
            {language === "en" ? "Back to Payments" : "Назад к Payments"}
          </Link>
        </Button>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="flex items-center gap-2 text-xl font-semibold">
              <BookOpen className="h-5 w-5 text-muted-foreground" />
              {content.title}
            </h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              {content.subtitle}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0 gap-1.5"
            onClick={() => setLanguage((l) => (l === "en" ? "ru" : "en"))}
            aria-label={
              language === "en" ? "Switch to Russian" : "Switch to English"
            }
          >
            <Languages className="h-4 w-4" />
            {language === "en" ? "Русский" : "English"}
          </Button>
        </div>
      </header>

      <div className="space-y-4">
        {content.sections.map((section) => (
          <DocSectionBlock key={section.heading} section={section} />
        ))}
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-amber-300/50 bg-amber-50 p-3 text-xs text-amber-900">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{content.maintenanceNote}</p>
      </div>
    </div>
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
        <pre className="overflow-x-auto rounded-md bg-muted px-3 py-2 text-xs leading-relaxed">
          {section.formula}
        </pre>
      )}
    </section>
  );
}
