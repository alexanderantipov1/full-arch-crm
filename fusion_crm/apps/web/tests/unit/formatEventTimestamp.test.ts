import { describe, expect, it } from "vitest";

import { formatEventTimestamp } from "@/lib/utils";

describe("formatEventTimestamp", () => {
  it("renders UTC-midnight stamps as a date-only label in UTC", () => {
    // CareStack dateOfService for a Jul-22 visit arrives as UTC midnight;
    // local-zone rendering would shift it to Jul 21 in any US timezone.
    expect(formatEventTimestamp("2026-07-22T00:00:00Z")).toBe("Jul 22, 2026");
    expect(formatEventTimestamp("2026-07-22T00:00:00+00:00")).toBe(
      "Jul 22, 2026",
    );
    expect(formatEventTimestamp("2026-07-22T00:00:00.000Z")).toBe(
      "Jul 22, 2026",
    );
  });

  it("keeps clock-time rendering for real timestamps", () => {
    const out = formatEventTimestamp("2026-06-10T22:44:00Z");
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  it("does not treat midnight in a non-UTC offset as date-only", () => {
    const out = formatEventTimestamp("2026-07-22T00:00:00+07:00");
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  it("returns the em dash for empty values", () => {
    expect(formatEventTimestamp(null)).toBe("—");
    expect(formatEventTimestamp(undefined)).toBe("—");
  });
});
