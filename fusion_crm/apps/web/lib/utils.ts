import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(
  iso: string | null | undefined,
  timeZone?: string,
): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    // When a company timezone is supplied, pin to it and show the
    // abbreviation (e.g. "PDT") so "when" is unambiguous to the operator.
    ...(timeZone ? { timeZone, timeZoneName: "short" as const } : {}),
  });
}

// Provider date-only fields (CareStack dateOfService, invoice dates)
// arrive as exact UTC midnight. Converting those to the viewer's zone
// shifts the date back a day (Jul 22 visit → "Jul 21, 05:00 PM" in PDT),
// so midnight-UTC stamps render as a plain UTC date with no clock time.
const UTC_MIDNIGHT = /T00:00:00(?:\.0+)?(?:Z|\+00:00)$/;

export function formatEventTimestamp(
  iso: string | null | undefined,
  timeZone?: string,
): string {
  if (!iso) return "—";
  if (UTC_MIDNIGHT.test(iso)) {
    return new Date(iso).toLocaleDateString("en-US", {
      timeZone: "UTC",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }
  return formatDateTime(iso, timeZone);
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  if (diffMs < 0) return formatDateTime(iso);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return formatDateTime(iso);
}

/**
 * Format a USD amount with two decimals and a "$" prefix.
 *
 * Returns "—" when given null/undefined so the empty state stays
 * indistinguishable from "no data" — never "$0", which would falsely
 * imply we know the balance is zero. Use this for every monetary
 * display introduced after ENG-306 (the FinancialSummary card, the
 * Payments row balance pill, …).
 */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}
