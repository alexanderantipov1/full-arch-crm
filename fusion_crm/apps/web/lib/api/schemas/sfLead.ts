import { z } from "zod";
import { Datetime } from "./common";

export const SfLeadSchema = z.object({
  id: z.string().uuid(),
  person_uid: z.string().uuid(),
  sf_lead_id: z.string(),
  display_name: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  company: z.string().nullable(),
  lead_source: z.string().nullable(),
  lead_status: z.string().nullable(),
  is_reactivation: z.boolean(),
  sf_created_at: z.string().nullable(),
  created_at: Datetime,
});

export type SfLead = z.infer<typeof SfLeadSchema>;

export const SfLeadListSchema = z.object({
  items: z.array(SfLeadSchema),
});

export const SfPullRecentResponseSchema = z.object({
  items: z.array(SfLeadSchema),
  pulled_count: z.number().int().nonnegative(),
});

export type SfPullRecentResponse = z.infer<typeof SfPullRecentResponseSchema>;

export const SfLeadOperationalSummarySchema = z.object({
  sf_lead_id: z.string(),
  salesforce_status: z.string().nullable(),
  salesforce_created_at: Datetime.nullable(),
  status_last_updated_at: Datetime.nullable(),
  source: z.string().nullable(),
  campaign: z.string().nullable(),
  owner: z.string().nullable(),
  owner_id: z.string().nullable(),
  treatment_coordinator: z.string().nullable(),
  assigned_center: z.string().nullable(),
  appointment_type: z.string().nullable(),
  attempt_count: z.number().int().nullable(),
  last_call_by: z.string().nullable(),
  unqualified_reason: z.string().nullable(),
  call_recording_url: z.string().nullable(),
  preferred_call_at: Datetime.nullable(),
  hubspot_contact_id: z.string().nullable(),
  hubspot_created_at: Datetime.nullable(),
  hubspot_lead_source: z.string().nullable(),
  record_source_detail: z.string().nullable(),
  old_lead_owner: z.string().nullable(),
  reactivated: z.boolean().nullable(),
  carestack_id: z.string().nullable(),
  carestack_appointment_id: z.string().nullable(),
  carestack_status: z.string().nullable(),
});

export type SfLeadOperationalSummary = z.infer<
  typeof SfLeadOperationalSummarySchema
>;

export const SfLeadTaskSummarySchema = z.object({
  task_id: z.string(),
  task_kind: z.string(),
  task_label: z.string(),
  call_label: z.string(),
  /** Concise human action ("Outbound call", "SMS sent", "Call-now task",
   * "Task"), its outcome ("Connected", "No answer", "confirmation",
   * "Pending", "Done"), and direction ("inbound"/"outbound"/null). */
  action_label: z.string().default("Task"),
  outcome_label: z.string().nullable().default(null),
  direction: z.string().nullable().default(null),
  status: z.string().nullable(),
  due_date: z.string().nullable(),
  is_overdue: z.boolean(),
  occurred_at: Datetime.nullable(),
  owner_id: z.string().nullable(),
  agent: z.string().nullable(),
  outcome: z.string().nullable(),
  duration_label: z.string().nullable(),
  duration_seconds: z.number().int().nullable(),
  call_recording_url: z.string().nullable(),
  source: z.string().nullable(),
  business_unit: z.string().nullable(),
  language: z.string().nullable(),
  created_label: z.string().nullable(),
});

export const SfLeadTaskSummaryListSchema = z.object({
  items: z.array(SfLeadTaskSummarySchema),
  total: z.number().int().nonnegative(),
});

export type SfLeadTaskSummary = z.infer<typeof SfLeadTaskSummarySchema>;
