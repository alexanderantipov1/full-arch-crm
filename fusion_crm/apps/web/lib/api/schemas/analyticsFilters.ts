import type { AnalyticsTimeRangePreset } from "./journeyMetrics";

/**
 * Shared global-filter state for the Revenue-Intelligence pages (ENG-514…523).
 *
 * Mirrors the backend `AnalyticsFilters` query params on
 * `GET /dashboard/analytics/*`. The B2 data-ready pages drive the filter bar
 * with the time-range preset + location (aggregate vs per-location); the
 * remaining dimensions exist on the contract but are not yet surfaced as filter
 * inputs (they appear as breakdowns on the Revenue page instead).
 *
 * `location_id === null` is the AGGREGATE (all locations); a value scopes the
 * window + counts to that one clinic (resolved in its timezone server-side).
 */
export type AnalyticsFilterValue = {
  time_range: AnalyticsTimeRangePreset;
  location_id: string | null;
  // Only meaningful when `time_range === "custom"` (ISO-8601 instants).
  custom_start?: string | null;
  custom_end?: string | null;
};

/** The preset ladder + labels for the filter bar (market.md time-range set). */
export const TIME_RANGE_PRESETS: {
  value: AnalyticsTimeRangePreset;
  label: string;
}[] = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "last_90_days", label: "Last 90 days" },
  { value: "this_month", label: "This month" },
  { value: "this_quarter", label: "This quarter" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom" },
];

/** Default filter selection shared by every page. */
export const DEFAULT_ANALYTICS_FILTERS: AnalyticsFilterValue = {
  time_range: "last_30_days",
  location_id: null,
};

/**
 * Serialize the shared filters to a query string for `/dashboard/analytics/*`.
 * Empty / null values are omitted so the backend applies its own defaults
 * (location omitted = aggregate). `custom_*` is sent only for the custom preset.
 */
export function toAnalyticsQuery(filters: AnalyticsFilterValue): string {
  const params = new URLSearchParams();
  params.set("time_range", filters.time_range);
  if (filters.location_id) params.set("location_id", filters.location_id);
  if (filters.time_range === "custom") {
    if (filters.custom_start) params.set("custom_start", filters.custom_start);
    if (filters.custom_end) params.set("custom_end", filters.custom_end);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}
