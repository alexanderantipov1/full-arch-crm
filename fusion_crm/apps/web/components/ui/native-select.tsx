"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Lightweight native `<select>` styled to look like shadcn's Select trigger.
 * We use the platform control here (instead of `@radix-ui/react-select`) so
 * we can ship an IANA-tz dropdown without pulling a new dependency. When the
 * settings page becomes editable, swap this for the full Radix Select.
 */
export interface NativeSelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  ariaLabel?: string;
}

const NativeSelect = React.forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, children, ariaLabel, ...props }, ref) => (
    <div
      className={cn(
        "relative inline-flex w-full items-center",
        props.disabled && "opacity-70",
      )}
    >
      <select
        ref={ref}
        aria-label={ariaLabel}
        className={cn(
          "flex h-10 w-full appearance-none items-center justify-between rounded-md border border-input bg-background px-3 py-2 pr-9 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-100",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-muted-foreground" />
    </div>
  ),
);
NativeSelect.displayName = "NativeSelect";

export { NativeSelect };
