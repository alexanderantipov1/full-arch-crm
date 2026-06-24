import { z } from "zod";
import { Datetime, ProviderSchema, Uuid } from "./common";

export const IntegrationStatusSchema = z.enum([
  "disconnected",
  "connecting",
  "connected",
  "syncing",
  "error",
  "needs_reconnect",
]);
export type IntegrationStatus = z.infer<typeof IntegrationStatusSchema>;

export const IntegrationAccountSchema = z.object({
  id: Uuid,
  provider: ProviderSchema,
  status: IntegrationStatusSchema,
  display_name: z.string().nullable(),
  /** ISO timestamp of last successful sync run (null if never). */
  last_sync_at: Datetime.nullable(),
  /** Most recent SyncRun summary, null if never run. */
  last_sync_summary: z
    .object({
      id: Uuid,
      status: z.enum(["running", "success", "failed"]),
      records_pulled: z.number().int().nonnegative(),
      finished_at: Datetime.nullable(),
    })
    .nullable(),
  error_message: z.string().nullable(),
});
export type IntegrationAccount = z.infer<typeof IntegrationAccountSchema>;

export const IntegrationListSchema = z.object({
  items: z.array(IntegrationAccountSchema),
});
export type IntegrationList = z.infer<typeof IntegrationListSchema>;

/** Response from POST /integrations/{provider}/connect/start
 * Salesforce → returns OAuth redirect URL.
 * CareStack → returns "api_key_form" hint so the UI shows the API-key form. */
export const ConnectStartResponseSchema = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("oauth_redirect"),
    /** Either an absolute external URL (real OAuth) or a same-origin path
     *  (mock flow). Backend MUST return a usable href value. */
    redirect_url: z.string().min(1),
  }),
  z.object({
    kind: z.literal("api_key_form"),
    label: z.string(),
    placeholder: z.string(),
  }),
  z.object({
    /** Server connected synchronously (e.g. credentials already in env).
     * Frontend should refetch the integrations list to pick up the
     * connected state — no redirect, no form. */
    kind: z.literal("instant_connected"),
    display_name: z.string(),
  }),
]);
export type ConnectStartResponse = z.infer<typeof ConnectStartResponseSchema>;

export const ApiKeyConnectRequestSchema = z.object({
  api_key: z.string().min(1),
  display_name: z.string().min(1).optional(),
});
export type ApiKeyConnectRequest = z.infer<typeof ApiKeyConnectRequestSchema>;

export const SyncTriggerResponseSchema = z.object({
  sync_run_id: Uuid,
});
export type SyncTriggerResponse = z.infer<typeof SyncTriggerResponseSchema>;
