import { z } from "zod";
import { Datetime } from "./common";

/**
 * Outreach domain schemas — mirrors `packages/outreach/schemas.py` DTOs
 * (TemplateOut / CampaignOut / SendOut / SuppressionOut / RenderedEmail /
 * PersonPreviewOut).
 *
 * Per ADR-0004:
 *   - `body_format=html` is enum-reserved but rejected at the service layer.
 *     We accept it on the wire to round-trip stored values; the form UI only
 *     surfaces `markdown` / `mjml`.
 *   - `tracking_enabled` may be true ONLY for `category=marketing`. The UI
 *     greys the toggle out for the three forbidden categories.
 */

export const TemplateBodyFormatSchema = z.enum(["markdown", "html", "mjml"]);
export type TemplateBodyFormat = z.infer<typeof TemplateBodyFormatSchema>;

export const TemplateCategorySchema = z.enum([
  "marketing",
  "clinical",
  "transactional",
  "operational",
]);
export type TemplateCategory = z.infer<typeof TemplateCategorySchema>;

export const TemplateStatusSchema = z.enum(["draft", "active", "archived"]);
export type TemplateStatus = z.infer<typeof TemplateStatusSchema>;

export const CampaignStatusSchema = z.enum([
  "draft",
  "queued",
  "sending",
  "sent",
  "failed",
  "cancelled",
]);
export type CampaignStatus = z.infer<typeof CampaignStatusSchema>;

export const CampaignMailboxStrategySchema = z.enum(["explicit", "auto_route"]);
export type CampaignMailboxStrategy = z.infer<
  typeof CampaignMailboxStrategySchema
>;

export const SendStatusSchema = z.enum([
  "queued",
  "sent",
  "bounced",
  "failed",
  "unsubscribed",
  "opened",
]);
export type SendStatus = z.infer<typeof SendStatusSchema>;

export const SuppressionReasonSchema = z.enum([
  "operator",
  "one_click",
  "bounce_hard",
  "complaint",
]);
export type SuppressionReason = z.infer<typeof SuppressionReasonSchema>;

/**
 * Categories that may NOT enable open/click tracking — ADR-0004 §"Tracking
 * gate is type-level". Mirrors `TRACKING_FORBIDDEN_CATEGORIES` server-side.
 */
export const TRACKING_FORBIDDEN_CATEGORIES: ReadonlySet<TemplateCategory> =
  new Set(["clinical", "transactional", "operational"]);

// --- Template -------------------------------------------------------------

export const TemplateInSchema = z.object({
  name: z.string().min(1).max(240),
  description: z.string().max(4000).nullable().optional(),
  subject_template: z.string().min(1),
  body_template: z.string().min(1),
  body_format: TemplateBodyFormatSchema.default("markdown"),
  category: TemplateCategorySchema.default("marketing"),
  tracking_enabled: z.boolean().default(false),
  intent_tags: z.array(z.string()).default([]),
});
export type TemplateIn = z.infer<typeof TemplateInSchema>;

export const TemplateUpdateSchema = TemplateInSchema.partial().extend({
  status: TemplateStatusSchema.optional(),
});
export type TemplateUpdate = z.infer<typeof TemplateUpdateSchema>;

export const TemplateOutSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  subject_template: z.string(),
  body_template: z.string(),
  body_format: TemplateBodyFormatSchema,
  category: TemplateCategorySchema,
  tracking_enabled: z.boolean(),
  intent_tags: z.array(z.string()),
  version: z.number().int(),
  status: TemplateStatusSchema,
  created_by_actor_id: z.string().uuid().nullable(),
  created_at: Datetime,
  updated_at: Datetime,
});
export type TemplateOut = z.infer<typeof TemplateOutSchema>;

export const TemplateListSchema = z.object({
  items: z.array(TemplateOutSchema),
});
export type TemplateList = z.infer<typeof TemplateListSchema>;

// --- Campaign -------------------------------------------------------------

export const CampaignInSchema = z.object({
  template_id: z.string().uuid(),
  name: z.string().min(1).max(240),
  recipient_query: z.record(z.unknown()).default({}),
  mailbox_credential_id: z.string().uuid().nullable().optional(),
  mailbox_strategy: CampaignMailboxStrategySchema.default("explicit"),
  scheduled_for: Datetime.nullable().optional(),
});
export type CampaignIn = z.infer<typeof CampaignInSchema>;

export const CampaignOutSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  template_id: z.string().uuid(),
  name: z.string(),
  recipient_query: z.record(z.unknown()),
  mailbox_credential_id: z.string().uuid().nullable(),
  mailbox_strategy: CampaignMailboxStrategySchema,
  scheduled_for: Datetime.nullable(),
  sent_count: z.number().int(),
  opened_count: z.number().int(),
  bounced_count: z.number().int(),
  unsubscribed_count: z.number().int(),
  status: CampaignStatusSchema,
  created_by_actor_id: z.string().uuid().nullable(),
  created_at: Datetime,
  updated_at: Datetime,
});
export type CampaignOut = z.infer<typeof CampaignOutSchema>;

export const CampaignListSchema = z.object({
  items: z.array(CampaignOutSchema),
});
export type CampaignList = z.infer<typeof CampaignListSchema>;

// --- Send -----------------------------------------------------------------

export const SendOutSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  campaign_id: z.string().uuid().nullable(),
  person_uid: z.string().uuid().nullable(),
  recipient_email: z.string(),
  message_id: z.string().nullable(),
  mailbox_credential_id: z.string().uuid(),
  status: SendStatusSchema,
  sent_at: Datetime.nullable(),
  error_text: z.string().nullable(),
  created_at: Datetime,
  updated_at: Datetime,
});
export type SendOut = z.infer<typeof SendOutSchema>;

export const SendListSchema = z.object({
  items: z.array(SendOutSchema),
  total: z.number().int(),
});
export type SendList = z.infer<typeof SendListSchema>;

// --- Suppression ----------------------------------------------------------

export const SuppressionOutSchema = z.object({
  tenant_id: z.string().uuid(),
  recipient_email_normalised: z.string(),
  reason: SuppressionReasonSchema,
  source_send_id: z.string().uuid().nullable(),
  created_at: Datetime,
});
export type SuppressionOut = z.infer<typeof SuppressionOutSchema>;

export const SuppressionListSchema = z.object({
  items: z.array(SuppressionOutSchema),
});
export type SuppressionList = z.infer<typeof SuppressionListSchema>;

// --- Render output --------------------------------------------------------

export const RenderedEmailSchema = z.object({
  subject: z.string(),
  body_html: z.string(),
  body_text: z.string(),
  list_unsubscribe_header: z.string().nullable().optional(),
});
export type RenderedEmail = z.infer<typeof RenderedEmailSchema>;

// --- Person preview (for campaign recipient preview) ---------------------

export const PersonPreviewOutSchema = z.object({
  person_uid: z.string().uuid(),
  display_name: z.string().nullable(),
  primary_email: z.string().nullable(),
});
export type PersonPreviewOut = z.infer<typeof PersonPreviewOutSchema>;

export const RecipientPreviewSchema = z.object({
  items: z.array(PersonPreviewOutSchema),
  total: z.number().int(),
});
export type RecipientPreview = z.infer<typeof RecipientPreviewSchema>;

// --- Merge fields allowlist (mirrors packages/outreach/merge_fields.py) ---

/**
 * The exact allowlist of merge-field keys the renderer accepts. UI inserts
 * `{{<key>}}` at the cursor when an operator clicks one in the sidebar.
 */
export const MERGE_FIELDS: ReadonlyArray<{
  key: string;
  group: string;
  description: string;
}> = [
  {
    key: "patient.first_name",
    group: "Patient",
    description: "Recipient first name.",
  },
  {
    key: "patient.last_name",
    group: "Patient",
    description: "Recipient last name.",
  },
  {
    key: "patient.full_name",
    group: "Patient",
    description: "Recipient full name.",
  },
  { key: "lead.status", group: "Lead", description: "Current lead status." },
  { key: "lead.source", group: "Lead", description: "Original lead source." },
  {
    key: "appointment.date",
    group: "Appointment",
    description: "Appointment date — MM/DD/YYYY.",
  },
  {
    key: "appointment.time",
    group: "Appointment",
    description: "Appointment time — h:mm AM/PM.",
  },
  {
    key: "appointment.location_name",
    group: "Appointment",
    description: "Location name on the booked appointment.",
  },
  { key: "location.name", group: "Location", description: "Office name." },
  {
    key: "location.address",
    group: "Location",
    description: "Office street address.",
  },
  {
    key: "location.phone",
    group: "Location",
    description: "Office phone number.",
  },
  {
    key: "tenant.name",
    group: "Tenant",
    description: "Clinic / organisation display name.",
  },
];
