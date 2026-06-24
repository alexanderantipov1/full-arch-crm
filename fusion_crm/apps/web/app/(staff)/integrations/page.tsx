"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useIntegrations } from "@/lib/api/hooks/useIntegrations";
import { ProviderCard } from "@/components/integrations/ProviderCard";
import { SfLeadsPanel } from "@/components/integrations/SfLeadsPanel";

export default function IntegrationsPage() {
  const { data, isLoading, error } = useIntegrations();

  return (
    <div className="space-y-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
        <p className="text-sm text-muted-foreground">
          Connect external CRM and practice-management providers. Phase 1 is{" "}
          <strong>read-only</strong> — we pull from the source, never push back.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load integrations.
        </div>
      )}

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {isLoading &&
          [...Array(2)].map((_, i) => (
            <Skeleton key={i} className="h-64 w-full" />
          ))}
        {data?.map((account) => (
          <ProviderCard key={account.provider} account={account} />
        ))}
      </section>

      <nav className="flex flex-wrap gap-2 text-sm">
        <Link
          href="/integrations/carestack"
          className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 hover:bg-muted/50"
        >
          <ExternalLink className="h-4 w-4" />
          Open CareStack inspector
          <span className="text-xs text-muted-foreground">
            (patients + appointments, last 7 days)
          </span>
        </Link>
      </nav>

      <SfLeadsPanel />
    </div>
  );
}
