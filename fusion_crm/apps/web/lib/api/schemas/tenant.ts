import { z } from "zod";
import { Datetime } from "./common";

/**
 * Tenant domain schemas. Mirrors `packages/tenant` Pydantic shapes that
 * ADR-0003 + ENG-125 (multi-mailbox addendum) specify.
 *
 * The provider list now matches the backend `ProviderKind` Literal — extending
 * with `google_workspace` / `microsoft_365` mailbox providers (ENG-131) and the
 * Phase-1 marketing / payment / analytics expansions.
 */

export const TenantStatusSchema = z.enum(["active", "paused", "archived"]);
export type TenantStatus = z.infer<typeof TenantStatusSchema>;

export const ProviderKindSchema = z.enum([
  // CRM
  "salesforce",
  "hubspot",
  // PMS / clinical
  "carestack",
  "open_dental",
  // Voice & AI
  "vapi",
  "openai",
  "anthropic",
  "elevenlabs",
  "deepgram",
  // SMS / voice transport
  "twilio",
  // Email / OAuth mailbox (ENG-131)
  "google_workspace",
  "microsoft_365",
  // Reviews
  "birdeye",
  "podium",
  "google_business",
  // Payment / financing
  "stripe",
  "square",
  "carecredit",
  "sunbit",
  "cherry",
  // Marketing analytics
  "google_analytics",
  "meta_pixel",
  "tiktok_pixel",
  // Corporate chat / messenger (ENG-435)
  "mattermost",
  // Marketing / SEO ad platforms (ENG-489 / ENG-491)
  "google_ads",
  "meta_ads",
  "google_search_console",
  // Catch-all
  "other",
]);
export type ProviderKind = z.infer<typeof ProviderKindSchema>;

export const CredentialKindSchema = z.enum([
  "oauth_token",
  "api_key",
  "password_grant",
  "webhook_secret",
]);
export type CredentialKind = z.infer<typeof CredentialKindSchema>;

export const CredentialStatusSchema = z.enum([
  "active",
  "expired",
  "revoked",
]);
export type CredentialStatus = z.infer<typeof CredentialStatusSchema>;

export const TenantSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  primary_email: z.string().email().nullable(),
  primary_phone: z.string().nullable(),
  website: z.string().url().nullable(),
  logo_url: z.string().url().nullable(),
  billing_email: z.string().email().nullable(),
  industry: z.string().nullable(),
  tax_id: z.string().nullable(),
  timezone: z.string(),
  locale: z.string(),
  status: TenantStatusSchema,
  subscription_status: z.string().nullable(),
  created_at: Datetime,
});
export type Tenant = z.infer<typeof TenantSchema>;

export const TenantLocationSchema = z.object({
  id: z.string().uuid(),
  external_ref: z
    .record(z.union([z.string(), z.number()]))
    .nullable(),
  name: z.string(),
  short_name: z.string().nullable(),
  address_line1: z.string().nullable(),
  address_line2: z.string().nullable(),
  city: z.string().nullable(),
  state: z.string().nullable(),
  zip: z.string().nullable(),
  country: z.string().nullable(),
  phone: z.string().nullable(),
  timezone_override: z.string().nullable(),
  latitude: z.number().nullable(),
  longitude: z.number().nullable(),
  is_active: z.boolean(),
});
export type TenantLocation = z.infer<typeof TenantLocationSchema>;

/**
 * Multi-mailbox fields land here per ENG-125: `mailbox_email`, `location_id`,
 * `is_default`, `tags`. The fields default to safe values so older fixtures
 * keep parsing — when the backend ships fully these become required.
 */
export const TenantIntegrationCredentialSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid().optional(),
  provider_kind: ProviderKindSchema,
  credential_kind: CredentialKindSchema,
  display_name: z.string().nullable(),
  status: CredentialStatusSchema,
  expires_at: Datetime.nullable(),
  last_refreshed_at: Datetime.nullable(),
  mailbox_email: z.string().nullable().optional(),
  location_id: z.string().uuid().nullable().optional(),
  is_default: z.boolean().optional(),
  tags: z.array(z.string()).optional(),
});
export type TenantIntegrationCredential = z.infer<
  typeof TenantIntegrationCredentialSchema
>;

export const BootstrapProviderKindSchema = z.enum([
  "salesforce",
  "carestack",
  "openai",
  // Marketing / SEO providers (ENG-491) — persisted as api_key payloads.
  "google_ads",
  "meta_ads",
  "google_analytics",
  "google_search_console",
]);
export type BootstrapProviderKind = z.infer<typeof BootstrapProviderKindSchema>;

const NonEmpty = z.string().trim().min(1);

/**
 * Required + optional field sets per bootstrap provider. Mirrors
 * `IntegrationCredentialBootstrapIn.validate_provider_shape` in
 * `packages/tenant/schemas.py` EXACTLY — any field not in a provider's
 * (required ∪ optional) set is rejected as unsupported.
 */
const BOOTSTRAP_REQUIRED: Record<BootstrapProviderKind, readonly string[]> = {
  salesforce: ["client_id", "client_secret", "callback_url"],
  // CareStack uses partner / password-grant config, not OAuth client creds.
  // client_id / client_secret are accepted (optional) but not required here —
  // the BootstrapCredentialModal omits those fields for CareStack (ENG-215).
  carestack: [
    "vendor_key",
    "account_key",
    "account_id",
    "idp_base_url",
    "api_base_url",
  ],
  openai: ["api_key"],
  google_ads: ["client_id", "client_secret", "developer_token", "refresh_token"],
  meta_ads: ["access_token"],
  google_analytics: [
    "client_id",
    "client_secret",
    "refresh_token",
    "property_id",
  ],
  google_search_console: ["client_id", "client_secret", "refresh_token"],
};

const BOOTSTRAP_OPTIONAL: Record<BootstrapProviderKind, readonly string[]> = {
  salesforce: ["domain"],
  // client_id / client_secret accepted but optional for CareStack (see
  // BOOTSTRAP_REQUIRED note); the original Zod treated them as supported.
  carestack: ["client_id", "client_secret", "api_version"],
  openai: [],
  google_ads: ["login_customer_id", "customer_ids"],
  meta_ads: ["ad_account_ids", "app_id", "app_secret"],
  google_analytics: [],
  google_search_console: ["site_url"],
};

const BOOTSTRAP_TYPED_FIELDS = [
  "client_id",
  "client_secret",
  "callback_url",
  "domain",
  "vendor_key",
  "account_key",
  "account_id",
  "idp_base_url",
  "api_base_url",
  "api_version",
  "api_key",
  "developer_token",
  "refresh_token",
  "login_customer_id",
  "customer_ids",
  "access_token",
  "ad_account_ids",
  "app_id",
  "app_secret",
  "property_id",
  "site_url",
] as const;

function isPresent(v: unknown): boolean {
  if (v === undefined || v === null) return false;
  if (Array.isArray(v)) return v.length > 0;
  return true;
}

export const IntegrationCredentialBootstrapInputSchema = z
  .object({
    provider_kind: BootstrapProviderKindSchema,
    credential_kind: CredentialKindSchema.optional(),
    display_name: z.string().trim().min(1).optional(),
    is_default: z.boolean().optional(),
    // Salesforce / OAuth client config (client_id/secret reused by marketing).
    client_id: NonEmpty.optional(),
    client_secret: NonEmpty.optional(),
    callback_url: NonEmpty.url().optional(),
    domain: NonEmpty.optional(),
    // CareStack password-grant config.
    vendor_key: NonEmpty.optional(),
    account_key: NonEmpty.optional(),
    account_id: NonEmpty.optional(),
    idp_base_url: NonEmpty.url().optional(),
    api_base_url: NonEmpty.url().optional(),
    api_version: NonEmpty.optional(),
    // AI provider API key.
    api_key: NonEmpty.optional(),
    // Marketing / SEO config (ENG-491).
    developer_token: NonEmpty.optional(),
    refresh_token: NonEmpty.optional(),
    login_customer_id: NonEmpty.optional(),
    customer_ids: z.array(NonEmpty).optional(),
    access_token: NonEmpty.optional(),
    ad_account_ids: z.array(NonEmpty).optional(),
    app_id: NonEmpty.optional(),
    app_secret: NonEmpty.optional(),
    property_id: NonEmpty.optional(),
    site_url: NonEmpty.url().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    const expectedKind =
      value.provider_kind === "carestack" ? "password_grant" : "api_key";
    if (value.credential_kind && value.credential_kind !== expectedKind) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["credential_kind"],
        message: `${value.provider_kind} credentials must use ${expectedKind}`,
      });
    }

    const supported = new Set<string>([
      ...BOOTSTRAP_REQUIRED[value.provider_kind],
      ...BOOTSTRAP_OPTIONAL[value.provider_kind],
    ]);
    for (const field of BOOTSTRAP_TYPED_FIELDS) {
      if (!supported.has(field) && isPresent(value[field as keyof typeof value])) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [field],
          message: `${field} is not supported for ${value.provider_kind}`,
        });
      }
    }

    for (const field of BOOTSTRAP_REQUIRED[value.provider_kind]) {
      if (!isPresent(value[field as keyof typeof value])) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [field],
          message: "Required",
        });
      }
    }
  });
export type IntegrationCredentialBootstrapInput = z.infer<
  typeof IntegrationCredentialBootstrapInputSchema
>;

export const TenantSettingSchema = z.object({
  key: z.string(),
  value: z.unknown(),
  updated_at: Datetime,
});
export type TenantSetting = z.infer<typeof TenantSettingSchema>;

export const TenantWithRelationsSchema = z.object({
  tenant: TenantSchema,
  locations: z.array(TenantLocationSchema),
  integrations: z.array(TenantIntegrationCredentialSchema),
  settings: z.array(TenantSettingSchema),
});
export type TenantWithRelations = z.infer<typeof TenantWithRelationsSchema>;
