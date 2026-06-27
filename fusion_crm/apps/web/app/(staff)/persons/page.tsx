"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePersons } from "@/lib/api/hooks/usePersons";
import { formatRelative } from "@/lib/utils";

export default function PersonsListPage() {
  const { data, isLoading, error } = usePersons();

  return (
    <div className="space-y-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Persons</h1>
        <p className="text-sm text-muted-foreground">
          Unified view across Salesforce + CareStack.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{data ? `${data.total} persons` : "Persons"}</CardTitle>
          <CardDescription>
            One row per person, regardless of how many systems they appear in.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {error && (
            <p className="text-sm text-destructive">Failed to load persons.</p>
          )}
          {isLoading &&
            [...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          {data?.items.map((p) => (
            <Link
              key={p.id}
              href={`/persons/${p.id}`}
              className="flex items-center justify-between rounded-md border bg-card px-4 py-3 transition-colors hover:bg-accent"
            >
              <div>
                <div className="font-medium">{p.display_name}</div>
                <div className="text-xs text-muted-foreground">
                  {p.email ?? "no email"} · {p.phone ?? "no phone"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {p.has_lead && <Badge>Lead</Badge>}
                {p.has_consultation && (
                  <Badge variant="secondary">Consult</Badge>
                )}
                {p.source_providers.map((sp) => (
                  <Badge key={sp} variant="outline" className="capitalize">
                    {sp}
                  </Badge>
                ))}
                <span className="text-xs text-muted-foreground">
                  {formatRelative(p.last_activity_at)}
                </span>
              </div>
            </Link>
          ))}
          {data && data.items.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No persons yet — connect a provider on the Integrations page.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
