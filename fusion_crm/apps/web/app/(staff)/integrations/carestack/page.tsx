"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { CsAppointmentsPanel } from "@/components/integrations/CsAppointmentsPanel";
import { CsPatientsPanel } from "@/components/integrations/CsPatientsPanel";

/**
 * CareStack inspector — read-only visual exploration of recent patients +
 * appointments. NOT persisted; live round-trip on every fetch. Pre-W2
 * reconnaissance: lets the operator see real CS shapes before we design
 * the persistence layer (ENG-7).
 */
export default function CareStackInspectorPage() {
  return (
    <div className="space-y-6 p-8">
      <header className="space-y-2">
        <Link
          href="/integrations"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to integrations
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          CareStack inspector
        </h1>
        <p className="text-sm text-muted-foreground">
          Live read-only view of CareStack data — patients and appointments
          modified in the last 7 days. Nothing here is saved to local Postgres
          (W2 / ENG-7 will add persistence). Click any row to see all fields
          for that record fresh from CareStack.
        </p>
      </header>

      <CsPatientsPanel />
      <CsAppointmentsPanel />
    </div>
  );
}
