# Semantic Analytics Catalog V1

This catalog defines the first governed analytics terms for the Semantic
Context And Analytics Foundation mission. It is the source of business meaning
for manager dashboards, manager AI chat, Data Intelligence Agent briefs, and
future analytics services.

The catalog is not a SQL interface. LLM planners and UI clients may reference
catalog terms through structured query specs, but they must not invent metric
definitions or execute raw SQL.

## Catalog Rules

- Every term has a version, owner, reviewer, data class, source evidence,
  allowed output posture, and review status.
- Row-level output is allowed for current production users, who are treated as
  authorized internal users during this mission phase.
- Row-level output still uses service-owned result contracts, field allowlists,
  source references, data-class markings, and audit where required.
- Raw provider payloads are not ordinary analytics output.
- PHI, if ever required, goes through `PhiService` with audit.
- `context_fact` and analytics terms are related but separate: context facts
  record person-linked meaning; analytics terms define cohorts, filters,
  metrics, and result contracts over facts and projections.

## Data Classes

| Data class | Meaning | Output posture |
| --- | --- | --- |
| `ops` | PHI-free operational state such as lead source, owner, stage, task, appointment status, and location. | Aggregate and row-level allowed for current production users. |
| `identity` | `person_uid`, source links, and minimal identifiers needed for row-level worklists. | Row-level allowed through field allowlists. |
| `integration_metadata` | Source ids, sync metadata, raw evidence references, and provider object provenance. | References allowed; raw payloads are not allowed. |
| `billing` | Payments, balances, refunds, accepted amounts, and revenue evidence. | Row-level allowed for current production users; audit posture required. |
| `phi_adjacent` | Appointment/treatment metadata that can imply clinical context. | Allowed only through reviewed fields and data-class badges. |
| `phi` | Clinical notes, diagnoses, or clinical treatment details. | Not included in V1 analytics terms; must use `PhiService` with audit if added later. |

## Review Status Values

- `draft`: proposed definition, safe for planning only.
- `review-ready`: ready for human review.
- `approved-v1`: approved for implementation.
- `blocked`: missing source, policy, or ownership decision.

## Terms

### `lead_source`

- Version: `v1`
- Status: `review-ready`
- Owner: marketing analytics
- Reviewer: marketing director
- Synonyms: source, acquisition source, lead channel
- Definition: the normalized source assigned to a lead or person-linked
  acquisition event.
- Source evidence: Salesforce Lead source fields, UTM fields, campaign fields,
  source links, and reviewed source mapping rules.
- Canonical fields: `person_uid`, `lead_id`, `lead_source`, `utm_source`,
  `utm_medium`, `utm_campaign`, `source_system`, `source_id`
- Data classes: `ops`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `lead_source`, `lead_created_at`,
  `utm_source`, `utm_medium`, `utm_campaign`, `source_reference`
- Aggregate metrics: `lead_count`, `conversion_rate`, `paid_lead_rate`
- Ambiguities: first-touch versus last-touch versus multi-touch attribution.

### `facebook_source`

- Version: `v1`
- Status: `draft`
- Owner: marketing analytics
- Reviewer: marketing director
- Synonyms: Facebook leads, Meta leads, paid social Facebook
- Definition: lead source normalized to Facebook/Meta acquisition using
  reviewed mapping rules over source fields and UTM values.
- Source evidence: Salesforce Lead source, UTM source/medium/campaign, campaign
  metadata, source mapping table or catalog artifact.
- Canonical fields: `lead_source`, `utm_source`, `utm_medium`, `utm_campaign`,
  `campaign_id`
- Data classes: `ops`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `lead_source`, `utm_source`, `utm_campaign`,
  `campaign_id`, `source_reference`
- Aggregate metrics: `lead_count`, `consultation_count`,
  `treatment_accepted_count`, `payment_total`
- Ambiguities: whether Instagram/Meta is included; exact UTM normalization.

### `google_ads_source`

- Version: `v1`
- Status: `draft`
- Owner: marketing analytics
- Reviewer: marketing director
- Synonyms: Google Ads, paid search, Google paid leads
- Definition: lead source normalized to Google paid acquisition using reviewed
  source and UTM mapping rules.
- Source evidence: Salesforce Lead source, UTM source/medium/campaign,
  campaign metadata.
- Canonical fields: `lead_source`, `utm_source`, `utm_medium`, `utm_campaign`,
  `campaign_id`
- Data classes: `ops`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `lead_source`, `utm_campaign`,
  `lead_created_at`, `source_reference`
- Aggregate metrics: `lead_count`, `consultation_completed_count`,
  `revenue_total`
- Ambiguities: campaign normalization across UTM, Salesforce, and ad platform
  identifiers.

### `consultation_scheduled`

- Version: `v1`
- Status: `review-ready`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: consult booked, appointment scheduled
- Definition: person has an appointment or event that represents a scheduled
  consultation.
- Source evidence: CareStack appointment, Salesforce Event, normalized
  `interaction.event` when available.
- Canonical fields: `person_uid`, `consultation_id`, `scheduled_at`,
  `location_id`, `provider_id`, `source_reference`
- Data classes: `ops`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `scheduled_at`, `location_id`, `provider_id`,
  `source_reference`
- Aggregate metrics: `consultation_scheduled_count`,
  `lead_to_consultation_rate`
- Ambiguities: whether rescheduled events create new scheduled events or update
  the same lifecycle.

### `consultation_completed`

- Version: `v1`
- Status: `review-ready`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: completed consult, attended consultation
- Definition: scheduled consultation reached a completed/attended state.
- Source evidence: CareStack appointment status, Salesforce Event outcome,
  normalized timeline event.
- Canonical fields: `person_uid`, `consultation_id`, `completed_at`,
  `location_id`, `provider_id`, `source_reference`
- Data classes: `ops`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `completed_at`, `location_id`,
  `provider_id`, `source_reference`
- Aggregate metrics: `consultation_completed_count`,
  `consultation_completion_rate`
- Ambiguities: completed status mapping across Salesforce and CareStack.

### `consultation_no_show`

- Version: `v1`
- Status: `draft`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: no-show, missed consult
- Definition: scheduled consultation ended with no-show status rather than
  completed, cancelled, or rescheduled.
- Source evidence: CareStack appointment status, Salesforce Event outcome.
- Canonical fields: `person_uid`, `consultation_id`, `scheduled_at`,
  `status`, `location_id`, `source_reference`
- Data classes: `ops`, `identity`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `scheduled_at`, `location_id`,
  `lead_source`, `owner_id`
- Aggregate metrics: `no_show_count`, `no_show_rate`
- Ambiguities: cancelled versus no-show versus rescheduled.

### `no_next_action`

- Version: `v1`
- Status: `draft`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: no follow-up, no next step, no next appointment
- Definition: a completed consultation or active opportunity has no qualifying
  future appointment, treatment plan, or follow-up task inside the configured
  lifecycle window.
- Source evidence: CareStack appointment/treatment evidence, Salesforce Tasks,
  normalized interaction events.
- Canonical fields: `person_uid`, `last_event_at`, `next_action_type`,
  `next_action_at`, `owner_id`
- Data classes: `ops`, `identity`, `integration_metadata`
- Allowed outputs: row-level, aggregate
- Row-level fields: `person_uid`, `last_event_at`, `days_since_last_event`,
  `owner_id`, `location_id`
- Aggregate metrics: `no_next_action_count`, `stale_followup_count`
- Ambiguities: qualifying next-action types and stale threshold.

### `stale_followup`

- Version: `v1`
- Status: `draft`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: stale lead, overdue follow-up, SLA breach
- Definition: an item requiring follow-up has exceeded its configured threshold
  without a qualifying action.
- Source evidence: Salesforce Task, lead created timestamp, consultation
  completed timestamp, CareStack appointment/treatment milestones.
- Canonical fields: `person_uid`, `workflow_type`, `last_activity_at`,
  `threshold_minutes`, `owner_id`
- Data classes: `ops`, `identity`
- Allowed outputs: row-level, aggregate
- Row-level fields: `person_uid`, `workflow_type`, `last_activity_at`,
  `minutes_overdue`, `owner_id`
- Aggregate metrics: `stale_followup_count`, `sla_breach_rate`
- Ambiguities: thresholds differ by workflow and source channel.

### `reactivation_candidate`

- Version: `v1`
- Status: `draft`
- Owner: operations analytics
- Reviewer: doctor / operator
- Synonyms: reactivation lead, dormant consult, stalled consult
- Definition: person completed a consultation but did not schedule treatment or
  another qualifying next step within the configured threshold.
- Source evidence: consultation completion, treatment scheduling, future
  appointment, follow-up task, recent contact.
- Canonical fields: `person_uid`, `consultation_completed_at`,
  `last_contact_at`, `days_since_consult`, `owner_id`
- Data classes: `ops`, `identity`, `integration_metadata`
- Allowed outputs: row-level, aggregate
- Row-level fields: `person_uid`, `consultation_completed_at`,
  `days_since_consult`, `owner_id`, `lead_source`
- Aggregate metrics: `reactivation_candidate_count`
- Ambiguities: threshold and exclusion rules for recently re-engaged patients.

### `treatment_proposed`

- Version: `v1`
- Status: `draft`
- Owner: clinical operations analytics
- Reviewer: doctor / operator
- Synonyms: treatment plan presented, proposed treatment
- Definition: treatment plan or procedure recommendation was proposed to a
  person after or around a consultation.
- Source evidence: CareStack treatment plan/procedure status, reviewed
  treatment milestone event.
- Canonical fields: `person_uid`, `treatment_case_id`, `proposed_at`,
  `provider_id`, `location_id`, `source_reference`
- Data classes: `ops`, `billing`, `phi_adjacent`
- Allowed outputs: aggregate, row-level through reviewed fields
- Row-level fields: `person_uid`, `proposed_at`, `provider_id`,
  `location_id`, `estimated_total`
- Aggregate metrics: `treatment_proposed_count`, `proposed_amount_total`
- Ambiguities: whether clinical procedure detail is required; V1 should avoid
  clinical-note PHI.

### `treatment_accepted`

- Version: `v1`
- Status: `draft`
- Owner: clinical operations analytics
- Reviewer: doctor / operator
- Synonyms: accepted treatment, treatment case accepted
- Definition: person accepted a treatment plan or treatment case according to
  reviewed CareStack or operational status.
- Source evidence: CareStack treatment plan/procedure status, accepted amount,
  reviewed treatment milestone.
- Canonical fields: `person_uid`, `treatment_case_id`, `accepted_at`,
  `accepted_amount`, `provider_id`, `location_id`, `source_reference`
- Data classes: `ops`, `billing`, `phi_adjacent`
- Allowed outputs: aggregate, row-level through reviewed fields
- Row-level fields: `person_uid`, `accepted_at`, `accepted_amount`,
  `provider_id`, `location_id`
- Aggregate metrics: `treatment_accepted_count`,
  `treatment_accepted_amount`
- Ambiguities: partial acceptance and attribution window from consult.

### `payment_received`

- Version: `v1`
- Status: `review-ready`
- Owner: revenue analytics
- Reviewer: doctor / operator
- Synonyms: paid, payment evidence, collected payment
- Definition: payment transaction or payment summary evidence indicates money
  was received for a person-linked account or treatment lifecycle.
- Source evidence: CareStack accounting transaction, payment summary, invoice
  payment event, reviewed revenue event.
- Canonical fields: `person_uid`, `payment_id`, `payment_date`,
  `payment_amount`, `payment_type`, `source_reference`
- Data classes: `billing`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level
- Row-level fields: `person_uid`, `payment_date`, `payment_amount`,
  `payment_type`, `related_invoice_id`
- Aggregate metrics: `payment_count`, `payment_total`, `time_to_payment`
- Ambiguities: deposit versus paid in full; refunds/reversals.

### `paid_lead`

- Version: `v1`
- Status: `draft`
- Owner: marketing analytics
- Reviewer: marketing director
- Synonyms: lead that paid, revenue-producing lead, paid patient
- Definition: a lead linked to a person with payment evidence inside the
  configured attribution window.
- Source evidence: lead source, person/source link, payment evidence, reviewed
  attribution rules.
- Canonical fields: `person_uid`, `lead_id`, `lead_source`, `lead_created_at`,
  `first_payment_date`, `payment_total`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Allowed outputs: aggregate, row-level drilldown
- Row-level fields: `person_uid`, `lead_source`, `lead_created_at`,
  `first_payment_date`, `payment_total`
- Aggregate metrics: `paid_lead_count`, `paid_lead_rate`, `payment_total`
- Ambiguities: any payment versus paid-in-full; attribution model and window.

### `balance_outstanding`

- Version: `v1`
- Status: `draft`
- Owner: revenue analytics
- Reviewer: doctor / operator
- Synonyms: outstanding balance, AR balance, unpaid balance
- Definition: person-linked balance remains greater than zero as of a selected
  date.
- Source evidence: CareStack ledger, invoice, payment summary, balance change
  event.
- Canonical fields: `person_uid`, `balance_amount`, `as_of_date`,
  `last_payment_date`, `source_reference`
- Data classes: `billing`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level
- Row-level fields: `person_uid`, `balance_amount`, `as_of_date`,
  `last_payment_date`, `treatment_status`
- Aggregate metrics: `outstanding_balance_total`, `patient_count`
- Ambiguities: ledger source-of-truth and write-off behavior.

### `carestack_linked`

- Version: `v1`
- Status: `review-ready`
- Owner: data quality analytics
- Reviewer: doctor / operator
- Synonyms: linked to CareStack, CareStack patient linked
- Definition: `identity.person` has a reviewed source link to a CareStack
  patient or qualifying CareStack person object.
- Source evidence: `identity.source_link`, matching results, CareStack patient
  raw-event reference.
- Canonical fields: `person_uid`, `source_system`, `source_kind`,
  `source_id`, `match_status`
- Data classes: `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level
- Row-level fields: `person_uid`, `carestack_patient_id`, `match_status`,
  `source_reference`
- Aggregate metrics: `carestack_linked_count`, `link_rate`
- Ambiguities: patient id only versus patient id plus appointment evidence.

### `revenue_evidence`

- Version: `v1`
- Status: `draft`
- Owner: revenue analytics
- Reviewer: doctor / operator and marketing director
- Synonyms: revenue proof, payment/invoice evidence, financial evidence
- Definition: reviewed source evidence that supports revenue attribution,
  including payment received, accepted amount, invoice issued, or balance state
  depending on the requested metric.
- Source evidence: payment transaction, invoice, treatment accepted amount,
  balance summary.
- Canonical fields: `person_uid`, `evidence_type`, `evidence_date`,
  `amount`, `source_reference`
- Data classes: `billing`, `identity`, `integration_metadata`
- Allowed outputs: aggregate, row-level through reviewed fields
- Row-level fields: `person_uid`, `evidence_type`, `evidence_date`,
  `amount`, `source_reference`
- Aggregate metrics: `revenue_total`, `payment_total`,
  `accepted_amount_total`
- Ambiguities: which evidence type applies to each question.

## First Read Model Needs

| Read model | Required terms | Primary users |
| --- | --- | --- |
| `lead_conversion` | `lead_source`, `consultation_scheduled`, `consultation_completed`, `consultation_no_show` | marketing director |
| `paid_leads` | `lead_source`, `paid_lead`, `payment_received`, `revenue_evidence` | marketing director |
| `consultation_followup` | `consultation_completed`, `no_next_action`, `stale_followup`, `reactivation_candidate` | doctor / operator |
| `treatment_revenue` | `treatment_proposed`, `treatment_accepted`, `payment_received`, `balance_outstanding`, `revenue_evidence` | doctor / operator |

## Open Catalog Decisions

1. Choose source attribution model for marketing terms.
2. Define attribution windows for lead-to-consult, consult-to-treatment, and
   treatment-to-payment.
3. Define stale thresholds per workflow.
4. Approve source normalization for Facebook, Google Ads, and paid social.
5. Confirm balance source-of-truth.
6. Define payment evidence semantics: any payment, deposit, or paid in full.
7. Confirm CareStack link requirements.
8. Define owner semantics: provider, treatment coordinator, or lead owner.
9. Map cancelled, rescheduled, and no-show statuses.
10. Confirm location and business unit source precedence.

## Next Handoff

This catalog is the direct input to:

- ENG-274 Structured Analytics Query Spec.
- ENG-275 Analytics Policy Preflight.
- ENG-276 Analytics Query Registry V1.
- ENG-277 Analytics Services V1.
- ENG-282 Semantic Analytics Workbench V1.
