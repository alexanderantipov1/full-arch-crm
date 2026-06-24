/**
 * IANA timezone helpers. `Intl.supportedValuesOf("timeZone")` returns ~600
 * zones at runtime in modern Node + browsers. The static fallback list keeps
 * SSR + older runtimes working with a useful subset (one per region) so the
 * select renders something even if `supportedValuesOf` is missing.
 */

const STATIC_FALLBACK: readonly string[] = [
  "UTC",
  "Africa/Cairo",
  "Africa/Johannesburg",
  "Africa/Lagos",
  "America/Anchorage",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/New_York",
  "America/Phoenix",
  "America/Sao_Paulo",
  "America/Toronto",
  "Asia/Dubai",
  "Asia/Hong_Kong",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Atlantic/Reykjavik",
  "Australia/Sydney",
  "Europe/Berlin",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Moscow",
  "Europe/Paris",
  "Pacific/Auckland",
  "Pacific/Honolulu",
];

interface IntlWithSupportedValues {
  supportedValuesOf?: (kind: string) => string[];
}

export function getSupportedTimezones(): readonly string[] {
  const intl = Intl as unknown as IntlWithSupportedValues;
  if (typeof intl.supportedValuesOf === "function") {
    try {
      return intl.supportedValuesOf("timeZone");
    } catch {
      return STATIC_FALLBACK;
    }
  }
  return STATIC_FALLBACK;
}

/**
 * Group IANA zones by their first segment (Africa, America, Asia, …) so we
 * can render `<optgroup>` / shadcn `<SelectGroup>` blocks. Each group's list
 * is sorted alphabetically.
 */
export function groupTimezones(
  zones: readonly string[],
): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const z of zones) {
    const region = z.split("/")[0] ?? "Other";
    (groups[region] ??= []).push(z);
  }
  for (const k of Object.keys(groups)) {
    groups[k]!.sort();
  }
  return groups;
}
