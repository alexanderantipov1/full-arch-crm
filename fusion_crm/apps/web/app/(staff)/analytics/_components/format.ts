/**
 * Shared display formatters for the Revenue-Intelligence pages (ENG-514…523).
 *
 * The cardinal rule mirrors the backend: a `null` metric (no denominator, or a
 * B1-unresolved input) renders "—", never a fabricated 0. Real numeric zeros
 * (e.g. an honest zero count) render normally.
 */

const NO_DATA = "—";

/** Whole-dollar USD, e.g. "$12,500". */
export function formatMoney(amount: number): string {
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

/** Money or "—" for a nullable value (null = no data, not a fake $0). */
export function formatMoneyOrDash(amount: number | null | undefined): string {
  return amount === null || amount === undefined ? NO_DATA : formatMoney(amount);
}

/** A 0–1 ratio as a percentage with one decimal, e.g. "57.6%"; null → "—". */
export function formatRatio(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) {
    return NO_DATA;
  }
  return `${(ratio * 100).toFixed(1)}%`;
}

/** A multiple like "3.2×" (e.g. ROI / ROAS); null → "—". */
export function formatMultiple(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return NO_DATA;
  }
  return `${value.toFixed(1)}×`;
}

/** Integer with thousands separators, e.g. "1,204". */
export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

export const NO_DATA_DASH = NO_DATA;
