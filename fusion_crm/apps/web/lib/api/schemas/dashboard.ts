import { z } from "zod";
import { Datetime, Uuid } from "./common";
import {
  LeadStatusSchema,
  OperationalTimelineEntrySchema,
  PersonSummarySchema,
} from "./person";

export const DashboardSummarySchema = z.object({
  lead_counts: z.record(LeadStatusSchema, z.number().int().nonnegative()),
  consultations_today: z.number().int().nonnegative(),
  consultations_this_week: z.number().int().nonnegative(),
  recent_persons: z.array(PersonSummarySchema),
  pipeline_total: z.number().int().nonnegative(),
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

export const DashboardPmFilterProviderSchema = z.enum([
  "salesforce",
  "carestack",
]);
export type DashboardPmFilterProvider = z.infer<
  typeof DashboardPmFilterProviderSchema
>;

export const DashboardAppliedFiltersSchema = z.object({
  from: Datetime.nullable(),
  to: Datetime.nullable(),
  source_provider: DashboardPmFilterProviderSchema.nullable(),
  lead_source: z.string().nullable(),
  location_id: Uuid.nullable(),
  q: z.string().nullable(),
  // ENG-408 PM Payments resource filter: the selected lead-source explorer
  // node (lead_source doubles as the node's source level on payments).
  lead_channel: z.string().nullable().optional(),
  lead_medium: z.string().nullable().optional(),
  lead_campaign: z.string().nullable().optional(),
});

export const DashboardKpiSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number().int().nonnegative(),
  hint: z.string().nullable(),
});
export type DashboardKpi = z.infer<typeof DashboardKpiSchema>;

export const DashboardBucketSchema = z.object({
  key: z.string(),
  label: z.string(),
  count: z.number().int().nonnegative(),
});

export const DashboardFunnelStageSchema = z.object({
  key: z.string(),
  label: z.string(),
  count: z.number().int().nonnegative(),
  hint: z.string().nullable().optional(),
});

export const DashboardBreakdownSchema = z.object({
  key: z.string(),
  label: z.string(),
  items: z.array(DashboardBucketSchema),
});
export type DashboardBreakdown = z.infer<typeof DashboardBreakdownSchema>;

export const DashboardSyncRunSchema = z.object({
  provider: z.string(),
  object_scope: z.string().nullable(),
  status: z.string(),
  started_at: Datetime,
  finished_at: Datetime.nullable(),
  records_total: z.number().int().nonnegative(),
  records_succeeded: z.number().int().nonnegative(),
  records_failed: z.number().int().nonnegative(),
  error: z.string().nullable(),
});

export const DashboardSemanticMetricSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number(),
});
export type DashboardSemanticMetric = z.infer<typeof DashboardSemanticMetricSchema>;

export const DashboardSemanticReadModelSchema = z.object({
  query_id: z.string(),
  read_model_id: z.string(),
  title: z.string(),
  data_classes: z.array(z.string()),
  definition_versions: z.record(z.string()),
  row_count: z.number().int().nonnegative(),
  drilldown_available: z.boolean(),
  export_available: z.boolean(),
  metrics: z.array(DashboardSemanticMetricSchema),
});
export type DashboardSemanticReadModel = z.infer<
  typeof DashboardSemanticReadModelSchema
>;

export const DashboardTreatmentPaymentsSchema = z.object({
  status: z.enum(["available", "contract_ready", "not_started"]),
  message: z.string(),
  treatment_presented_count: z.number().int().nonnegative(),
  treatment_completed_count: z.number().int().nonnegative(),
  invoice_count: z.number().int().nonnegative(),
  payment_total_amount: z.number().nonnegative(),
  collected_total: z.number().nonnegative(),
  payment_event_count: z.number().int().nonnegative(),
  outstanding_total: z.number().nonnegative(),
  outstanding_patient_count: z.number().int().nonnegative(),
  has_partial_payments: z.boolean(),
  first_payment_at: Datetime.nullable(),
  last_payment_at: Datetime.nullable(),
  ar_risk_count: z.number().int().nonnegative().nullable(),
});
export type DashboardTreatmentPayments = z.infer<
  typeof DashboardTreatmentPaymentsSchema
>;

export const DashboardPmSchema = z.object({
  filters: DashboardAppliedFiltersSchema,
  kpis: z.array(DashboardKpiSchema),
  funnel: z.array(DashboardFunnelStageSchema),
  breakdowns: z.array(DashboardBreakdownSchema),
  semantic_analytics: z.array(DashboardSemanticReadModelSchema),
  recent_activity: z.array(OperationalTimelineEntrySchema),
  sync_health: z.array(DashboardSyncRunSchema),
  treatment_payments: DashboardTreatmentPaymentsSchema,
});
export type DashboardPm = z.infer<typeof DashboardPmSchema>;

// Request-side filter (ENG-560/ENG-561). Buckets each person into exactly one
// clinic tab; "all"/omit means the param is absent. This is a pure REQUEST
// filter — it never appears on the row DTO. Keep these values in lockstep with
// the backend `location_tab` query Literal in apps/api/routers/dashboard.py.
export const DashboardPmLeadLocationTabSchema = z.enum([
  "galleria",
  "fusion",
  "el_dorado",
  "cosmo",
]);
export type DashboardPmLeadLocationTab = z.infer<
  typeof DashboardPmLeadLocationTabSchema
>;

// Location-tab ordering (ENG-559). Request-side only — a sort selector, not a
// row field. "lead" = lead/funnel date (default); "appointment" = re-order by
// CareStack appointment-creation time (the CareStack column header). Keep in
// lockstep with the backend `sort` query Literal in dashboard.py.
export const DashboardPmLeadSortSchema = z.enum(["lead", "appointment"]);
export type DashboardPmLeadSort = z.infer<typeof DashboardPmLeadSortSchema>;

export const DashboardPmLeadSchema = z.object({
  id: Uuid,
  person_uid: Uuid,
  display_name: z.string(),
  given_name: z.string().nullable(),
  family_name: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  status: z.string(),
  lead_source: z.string().nullable(),
  source_provider: z.enum(["salesforce", "carestack", "manual", "unknown"]),
  source_external_id: z.string().nullable(),
  created_at: Datetime,
  updated_at: Datetime,
  source_providers: z.array(z.string()),
  consultation_status: z.string().nullable().optional(),
  consultation_scheduled_at: Datetime.nullable().optional(),
  consultation_provider_created_at: Datetime.nullable().optional(),
  consultation_provider: z.string().nullable().optional(),
  location_name: z.string().nullable().optional(),
});
export type DashboardPmLead = z.infer<typeof DashboardPmLeadSchema>;

export const DashboardPmLeadListSchema = z.object({
  items: z.array(DashboardPmLeadSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  has_next: z.boolean(),
  has_previous: z.boolean(),
  filters: DashboardAppliedFiltersSchema,
});
export type DashboardPmLeadList = z.infer<typeof DashboardPmLeadListSchema>;

export const DashboardPmLeadSourceBucketSchema = z.object({
  key: z.string(),
  count: z.number().int().nonnegative(),
});
export type DashboardPmLeadSourceBucket = z.infer<
  typeof DashboardPmLeadSourceBucketSchema
>;

export const DashboardPmLeadSourceProviderSchema = z.object({
  provider: z.enum(["salesforce", "carestack"]),
  total: z.number().int().nonnegative(),
  sources: z.array(DashboardPmLeadSourceBucketSchema),
});
export type DashboardPmLeadSourceProvider = z.infer<
  typeof DashboardPmLeadSourceProviderSchema
>;

export const DashboardPmLeadSourcesSchema = z.object({
  providers: z.array(DashboardPmLeadSourceProviderSchema),
});
export type DashboardPmLeadSources = z.infer<typeof DashboardPmLeadSourcesSchema>;

export const DashboardPmPaymentKindSchema = z.enum([
  "payment_recorded",
  "payment_refunded",
  "payment_reversed",
  // ENG-283: allocation leg of CareStack's double-entry ledger.
  // Returned by the API; hidden by default on the PM Payments page
  // and excluded from Collected totals.
  "payment_applied",
]);
export type DashboardPmPaymentKind = z.infer<typeof DashboardPmPaymentKindSchema>;

export const DashboardPmPaymentSchema = z.object({
  id: Uuid,
  person_uid: Uuid,
  display_name: z.string(),
  lead_status: z.string().nullable().optional(),
  consultation_status: z.string().nullable().optional(),
  // ENG-408: acquisition attribution for the row's person — explorer
  // source label (last-touch, lowercase) and the SF lead owner
  // (Owner.Name mirror, OwnerId fallback). null when the person has no lead.
  lead_source_label: z.string().nullable().optional(),
  lead_owner: z.string().nullable().optional(),
  amount: z.number().nullable().optional(),
  kind: DashboardPmPaymentKindSchema,
  transaction_type: z.string().nullable().optional(),
  occurred_at: Datetime,
  source_provider: DashboardPmFilterProviderSchema,
  source_external_id: z.string().nullable().optional(),
  location_id: Uuid.nullable().optional(),
  location_name: z.string().nullable().optional(),
  raw_event_id: Uuid.nullable().optional(),
  // ENG-303: which CareStack invoice this payment is applied to. number/date
  // are resolved from the invoice feed and may be absent.
  invoice_id: z.string().nullable().optional(),
  invoice_number: z.string().nullable().optional(),
  invoice_date: z.string().nullable().optional(),
  // ENG-306: latest authoritative outstanding balance for the row's
  // patient (patient + insurance from the most recent payment-summary
  // snapshot). `null` when no snapshot exists yet — the UI pill renders
  // "—" rather than misleading "$0".
  balance: z.number().nullable().optional(),
  // ENG-547: what the payment was for + who performed it, resolved from the
  // accounting-transaction's optional procedureCodeId / providerId. operation_code
  // is the CDT code (e.g. "D6010"); doctor_name is the performing provider's
  // display name. `null` for advances / unallocated legs / adjustments — the UI
  // renders "—". Direct transaction fields only (no invoice-provider fallback).
  operation_code: z.string().nullable().optional(),
  operation_description: z.string().nullable().optional(),
  doctor_name: z.string().nullable().optional(),
  doctor_provider_id: z.number().int().nullable().optional(),
});
export type DashboardPmPayment = z.infer<typeof DashboardPmPaymentSchema>;

export const DashboardPmPaymentListSchema = z.object({
  items: z.array(DashboardPmPaymentSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  has_next: z.boolean(),
  has_previous: z.boolean(),
  filters: DashboardAppliedFiltersSchema,
});
export type DashboardPmPaymentList = z.infer<typeof DashboardPmPaymentListSchema>;

// ENG-410: one same-day payment group — CareStack splits a real-world
// payment into per-invoice legs; the group collapses them by
// (person, kind, clinic-local day). `legs` reuse the flat row shape so the
// expanded view is identical to the ungrouped list.
export const DashboardPmPaymentGroupSchema = z.object({
  person_uid: Uuid,
  display_name: z.string(),
  lead_status: z.string().nullable().optional(),
  consultation_status: z.string().nullable().optional(),
  lead_source_label: z.string().nullable().optional(),
  lead_owner: z.string().nullable().optional(),
  balance: z.number().nullable().optional(),
  kind: DashboardPmPaymentKindSchema,
  // Clinic-local calendar day (YYYY-MM-DD).
  day: z.string(),
  amount: z.number(),
  leg_count: z.number().int().positive(),
  occurred_at: Datetime,
  legs: z.array(DashboardPmPaymentSchema),
});
export type DashboardPmPaymentGroup = z.infer<
  typeof DashboardPmPaymentGroupSchema
>;

export const DashboardPmPaymentGroupListSchema = z.object({
  items: z.array(DashboardPmPaymentGroupSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  has_next: z.boolean(),
  has_previous: z.boolean(),
  filters: DashboardAppliedFiltersSchema,
});
export type DashboardPmPaymentGroupList = z.infer<
  typeof DashboardPmPaymentGroupListSchema
>;

// ENG-302: window-wide totals for the Payments summary bar — aggregated over
// the whole selected window/filters, NOT the paginated page.
export const DashboardPmPaymentSummarySchema = z.object({
  collected_total: z.number(),
  payment_count: z.number().int().nonnegative(),
  patient_count: z.number().int().nonnegative(),
  filters: DashboardAppliedFiltersSchema,
});
export type DashboardPmPaymentSummary = z.infer<
  typeof DashboardPmPaymentSummarySchema
>;
