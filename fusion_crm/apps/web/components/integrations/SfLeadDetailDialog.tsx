"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSfLeadRaw } from "@/lib/api/hooks/useSfLeads";

interface Props {
  sfLeadId: string | null;
  onClose: () => void;
}

export function SfLeadDetailDialog({ sfLeadId, onClose }: Props) {
  const { data, isLoading, error } = useSfLeadRaw(sfLeadId);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!sfLeadId) return;
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onEsc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onEsc);
      document.body.style.overflow = "";
    };
  }, [sfLeadId, onClose]);

  const rows = useMemo(() => {
    if (!data) return [];
    const entries = Object.entries(data).filter(([k]) => k !== "attributes");
    const f = filter.trim().toLowerCase();
    if (!f) return entries;
    return entries.filter(
      ([k, v]) =>
        k.toLowerCase().includes(f) ||
        String(v ?? "").toLowerCase().includes(f),
    );
  }, [data, filter]);

  if (!sfLeadId) return null;

  const totalFields = data
    ? Object.keys(data).filter((k) => k !== "attributes").length
    : 0;
  const populatedFields = data
    ? Object.entries(data).filter(
        ([k, v]) => k !== "attributes" && v !== null && v !== "",
      ).length
    : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-lg border bg-card shadow-lg">
        <header className="flex items-start justify-between gap-4 border-b p-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">
              Salesforce Lead — full payload
            </h2>
            <p className="font-mono text-xs text-muted-foreground">
              {sfLeadId}
            </p>
            {data && (
              <p className="mt-1 text-xs text-muted-foreground">
                {populatedFields} populated of {totalFields} fields • live from
                SF, not persisted
              </p>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="border-b p-3">
          <Input
            placeholder="Filter fields by name or value…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="h-9"
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center p-12 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Fetching from Salesforce…
            </div>
          )}
          {error && (
            <div className="m-4 rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load: {(error as Error).message}
            </div>
          )}
          {data && rows.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No fields match &quot;{filter}&quot;.
            </div>
          )}
          {data && rows.length > 0 && (
            <table className="w-full text-sm">
              <thead className="sticky top-0 border-b bg-muted/80 text-left text-xs uppercase tracking-wide text-muted-foreground backdrop-blur">
                <tr>
                  <th className="w-1/3 px-4 py-2 font-medium">Field</th>
                  <th className="px-4 py-2 font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([key, value]) => (
                  <tr
                    key={key}
                    className={`border-b last:border-0 ${
                      value === null || value === "" ? "opacity-50" : ""
                    }`}
                  >
                    <td className="px-4 py-2 align-top font-mono text-xs">
                      {key}
                    </td>
                    <td className="px-4 py-2 align-top break-all text-xs">
                      {formatValue(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (value === "") return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
