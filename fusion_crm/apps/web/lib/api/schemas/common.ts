import { z } from "zod";

/** Backend error envelope. Mirrors PlatformError JSON output. */
export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).default({}),
  }),
});

export type ApiErrorBody = z.infer<typeof ApiErrorSchema>;

export const Uuid = z.string().uuid();

/**
 * ISO-8601 datetime string accepting either `Z` suffix or `±HH:MM`
 * offset. Python's `datetime.isoformat()` emits `+00:00` for UTC,
 * not `Z`; `z.string().datetime()` without `offset: true` rejects
 * the offset form and silently kills the page (see
 * `feedback_prod_deploy_traps.md`). Always use this alias instead
 * of `z.string().datetime()` for backend-supplied timestamps.
 */
export const Datetime = z.string().datetime({ offset: true });

/**
 * Provider keys surfaced on the staff UI. The first five mirror
 * `packages.ops.models.ACCOUNT_PROVIDERS` (lead/person source providers);
 * the marketing / SEO group (ENG-491) is surfaced on the integrations page
 * as bootstrap-credential cards and flows through the same
 * `IntegrationAccount` envelope.
 */
export const ProviderSchema = z.enum([
  "salesforce",
  "hubspot",
  "carestack",
  "manual",
  "import",
  // Marketing / SEO (ENG-491) — bootstrap-credential integration cards.
  "google_ads",
  "meta_ads",
  "google_analytics",
  "google_search_console",
]);
export type Provider = z.infer<typeof ProviderSchema>;
