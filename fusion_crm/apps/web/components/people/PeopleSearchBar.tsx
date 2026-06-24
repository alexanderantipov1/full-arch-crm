"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { PeopleSearchInput } from "@/lib/api/schemas/peopleSearch";

interface Props {
  /** Controlled value — owner state lives in the parent page / dialog. */
  value: PeopleSearchInput;
  onChange: (next: PeopleSearchInput) => void;
  /** Optional autofocus on mount (used by Cmd+K dialog). */
  autoFocus?: boolean;
  className?: string;
  placeholder?: string;
}

/**
 * Heuristics for routing a single user-typed string into either the phone
 * field, the email field, or both. Phone-only chars: digits, plus, space,
 * dash, parens. Email signal: an `@` anywhere.
 */
function detectKind(raw: string): "phone" | "email" | "both" | "empty" {
  const v = raw.trim();
  if (!v) return "empty";
  if (v.includes("@")) return "email";
  if (/^[+\d\s()\-]+$/.test(v)) return "phone";
  return "both";
}

/**
 * Single-input people search bar with auto-detect (phone vs email vs both).
 * Toggle the chevron to switch into a 2-input mode for explicit phone +
 * email queries (e.g. when the lead's email contains digits and the
 * heuristic would mis-route).
 */
export function PeopleSearchBar({
  value,
  onChange,
  autoFocus,
  className,
  placeholder = "Search by phone or email…",
}: Props) {
  const [combined, setCombined] = useState("");
  const [splitMode, setSplitMode] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // When entering split mode, seed the two fields from the combined value
  // so the user does not lose typing context.
  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const kind = useMemo(() => detectKind(combined), [combined]);

  function handleCombinedChange(raw: string) {
    setCombined(raw);
    const v = raw.trim();
    if (!v) {
      onChange({});
      return;
    }
    const k = detectKind(raw);
    if (k === "email") onChange({ email: v });
    else if (k === "phone") onChange({ phone: v });
    else onChange({ phone: v, email: v });
  }

  function clearAll() {
    setCombined("");
    onChange({});
    inputRef.current?.focus();
  }

  function toggleSplit() {
    setSplitMode((prev) => {
      const next = !prev;
      if (next) {
        // entering split mode: pre-fill from auto-detect best guess
        const k = detectKind(combined);
        if (k === "email") onChange({ email: combined.trim() });
        else if (k === "phone") onChange({ phone: combined.trim() });
        else if (k === "both") {
          onChange({ phone: combined.trim(), email: combined.trim() });
        }
      } else {
        // leaving split mode: collapse back into the combined input.
        // Pick whichever side has a value; if both, prefer email since
        // it's the stronger signal.
        const collapsed = value.email ?? value.phone ?? "";
        setCombined(collapsed);
      }
      return next;
    });
  }

  const hasAny = Boolean(value.phone || value.email);

  return (
    <div className={cn("space-y-2", className)}>
      {!splitMode ? (
        <div className="relative flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={combined}
              onChange={(e) => handleCombinedChange(e.target.value)}
              placeholder={placeholder}
              className="pl-9 pr-9"
              autoComplete="off"
              spellCheck={false}
              inputMode="text"
              aria-label="Search people by phone or email"
            />
            {combined && (
              <button
                type="button"
                onClick={clearAll}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={toggleSplit}
            aria-label="Switch to phone + email mode"
            title="Phone + email mode"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="space-y-2 rounded-md border bg-muted/20 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Phone + email mode
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={toggleSplit}
            >
              Single input
            </Button>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="people-search-phone" className="text-xs">
                Phone
              </Label>
              <Input
                id="people-search-phone"
                value={value.phone ?? ""}
                onChange={(e) =>
                  onChange({ ...value, phone: e.target.value || undefined })
                }
                placeholder="+1 415 555 0142"
                autoComplete="off"
                inputMode="tel"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="people-search-email" className="text-xs">
                Email
              </Label>
              <Input
                id="people-search-email"
                value={value.email ?? ""}
                onChange={(e) =>
                  onChange({ ...value, email: e.target.value || undefined })
                }
                placeholder="lead@example.com"
                autoComplete="off"
                inputMode="email"
              />
            </div>
          </div>
          {hasAny && (
            <button
              type="button"
              onClick={clearAll}
              className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            >
              Clear both
            </button>
          )}
        </div>
      )}
      {!splitMode && combined && (
        <p className="text-xs text-muted-foreground">
          {kind === "email" && "Detected: email — will search by email"}
          {kind === "phone" && "Detected: phone — will search by phone"}
          {kind === "both" &&
            "Ambiguous — searching both phone and email fields"}
        </p>
      )}
    </div>
  );
}
