"use client";

import { CalendarRange, MapPin } from "lucide-react";
import { NativeSelect } from "@/components/ui/native-select";
import { useCurrentTenant } from "@/lib/api/hooks/useTenant";
import {
  TIME_RANGE_PRESETS,
  type AnalyticsFilterValue,
} from "@/lib/api/schemas";

/**
 * Shared global filter bar for the Revenue-Intelligence pages (ENG-514…523):
 * time-range preset + location (aggregate vs per-location) + custom dates.
 *
 * Reuses the shared `AnalyticsFilterValue` / `toAnalyticsQuery` contract so every
 * page resolves its window identically (no drift). Location options come from
 * the current tenant's `locations`; "All locations" is the aggregate default.
 */
export function AnalyticsFilterBar({
  value,
  onChange,
}: {
  value: AnalyticsFilterValue;
  onChange: (next: AnalyticsFilterValue) => void;
}) {
  const tenant = useCurrentTenant();
  const locations = (tenant.data?.locations ?? []).filter((l) => l.is_active);

  // Custom dates: the bar collects calendar days; the window is half-open, so
  // the end date is sent as the following midnight (inclusive of the picked day).
  const startDate = value.custom_start?.slice(0, 10) ?? "";
  const endExclusive = value.custom_end ? new Date(value.custom_end) : null;
  const endDate = endExclusive
    ? new Date(endExclusive.getTime() - 86_400_000).toISOString().slice(0, 10)
    : "";

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-3">
      <div className="flex items-center gap-2">
        <CalendarRange className="h-4 w-4 text-muted-foreground" />
        <NativeSelect
          value={value.time_range}
          onChange={(e) =>
            onChange({
              ...value,
              time_range: e.target
                .value as AnalyticsFilterValue["time_range"],
            })
          }
          aria-label="Time range"
          className="w-40"
        >
          {TIME_RANGE_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </NativeSelect>
      </div>

      {value.time_range === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={startDate}
            aria-label="Custom start date"
            onChange={(e) =>
              onChange({
                ...value,
                custom_start: e.target.value
                  ? `${e.target.value}T00:00:00+00:00`
                  : null,
              })
            }
            className="h-9 rounded-md border bg-background px-2 text-sm"
          />
          <span className="text-muted-foreground">→</span>
          <input
            type="date"
            value={endDate}
            aria-label="Custom end date"
            onChange={(e) => {
              if (!e.target.value) {
                onChange({ ...value, custom_end: null });
                return;
              }
              // Inclusive end → send the next midnight (half-open window).
              const next = new Date(`${e.target.value}T00:00:00+00:00`);
              next.setUTCDate(next.getUTCDate() + 1);
              onChange({ ...value, custom_end: next.toISOString() });
            }}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          />
        </div>
      )}

      <div className="flex items-center gap-2">
        <MapPin className="h-4 w-4 text-muted-foreground" />
        <NativeSelect
          value={value.location_id ?? ""}
          onChange={(e) =>
            onChange({ ...value, location_id: e.target.value || null })
          }
          aria-label="Location"
          className="w-52"
        >
          <option value="">All locations</option>
          {locations.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.short_name || loc.name}
            </option>
          ))}
        </NativeSelect>
      </div>
    </div>
  );
}
