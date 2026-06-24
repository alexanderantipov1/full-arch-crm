"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PeopleSearchBar } from "./PeopleSearchBar";
import { PeopleSearchResults } from "./PeopleSearchResults";
import { usePeopleSearch } from "@/lib/api/hooks/usePeopleSearch";
import type { PeopleSearchInput } from "@/lib/api/schemas/peopleSearch";

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Cmd+K-triggered people search dialog. Mirrors the full /people/search
 * page but renders in an overlay so receptionists can look up a caller
 * without leaving their current page.
 *
 * Pattern follows CsRawDialog — vanilla div backdrop with Esc-to-close,
 * no extra Radix dependency surface.
 */
export function PeopleSearchDialog({ open, onClose }: Props) {
  const [input, setInput] = useState<PeopleSearchInput>({});
  const query = usePeopleSearch(input);
  const hasQuery = Boolean(input.phone || input.email);

  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onEsc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onEsc);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  // Reset on close so the next Cmd+K starts fresh.
  useEffect(() => {
    if (!open) setInput({});
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-background/80 p-4 pt-[10vh] backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-lg border bg-card shadow-lg">
        <header className="flex items-center justify-between gap-4 border-b p-4">
          <div>
            <h2 className="text-lg font-semibold">Find a person</h2>
            <p className="text-xs text-muted-foreground">
              Press Esc to close · search runs across SF, CareStack, and CRM
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="border-b p-4">
          <PeopleSearchBar value={input} onChange={setInput} autoFocus />
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <PeopleSearchResults
            data={query.data}
            isLoading={query.isFetching && hasQuery}
            isError={query.isError}
            error={query.error}
            hasQuery={hasQuery}
          />
        </div>
      </div>
    </div>
  );
}
