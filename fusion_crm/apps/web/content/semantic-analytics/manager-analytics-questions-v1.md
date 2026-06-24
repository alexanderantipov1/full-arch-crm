# Manager Analytics Questions V1 — Seed Spec

This file is the V1 seed spec for manager analytics questions in the
`Semantic Context And Analytics Foundation` mission (ENG-272). It is not yet
final product truth. It captures 30 questions that the manager dashboard,
manager AI chat, and Data Intelligence Agent should be able to answer
through approved, typed, policy-aware analytics queries.

Audience groups:

- **doctor / operator** — clinical operations and revenue health for current
  patients and accepted treatments.
- **marketing director** — lead source, campaign, and funnel performance for
  paid and organic acquisition.

Both groups are current production users and are treated as authorized
internal users for this mission phase. Row-level analytics is allowed for
them. Service-layer checks, source references, data-class markings,
`PhiService`, and audit requirements remain mandatory. Raw provider payloads
are not ordinary analytics output.

## Legend

### Priority

- **P0** — foundational; the first dashboards, chat answers, and read
  models must answer this by Slice 1.
- **P1** — high priority; primary cohort/funnel questions that follow
  immediately after P0 stabilizes.
- **P2** — medium priority; secondary breakdowns and performance views.
- **P3** — data-quality and gap-finding; required for trust but lower
  business urgency.

### Default output level

- **aggregate** — counts, sums, rates, group-bys; no row-level person data
  by default.
- **aggregate + drilldown** — primary view is aggregate; row-level expansion
  is allowed for authorized internal users when the cohort is bounded.
- **row-level** — the primary view is a person/cohort list (doctor/operator
  worklists). Service-layer field allowlists and audit still apply.

### Data classes

- `ops` — non-PHI operational state (sources, statuses, owners, links,
  scheduling metadata).
- `identity` — person identity and minimal identifiers.
- `integration_metadata` — source system ids, sync timestamps, raw evidence
  pointers (never raw payload).
- `billing` — payments, balances, refunds, charges. PHI-adjacent; treat
  strictly.
- `phi_adjacent` — appointment or treatment metadata that can imply
  diagnosis or clinical context.
- `phi` — clinical notes, diagnoses, treatment plan content. Always through
  `PhiService` with audit.

## Doctor / Operator Questions

### Q1. Which consultations were completed in the selected period, and what happened next for each person?

- Priority: P0 | Workflow: Consultation and follow-up | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate count grouped by `next_action_type`; drilldown rows of
  `person_uid, consult_date, location, provider, next_action_type, next_action_date`
- Filters: `date_range`, `location_id`, `provider_id`
- Terms: `consultation_completed`, `next_action_present`, `next_appointment`,
  `next_treatment_plan`, `next_task`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: scope of "next" (any appointment vs treatment-related);
  source of next action (Salesforce task vs CareStack appointment); time
  horizon for "what happened next" (within N days vs open-ended)

### Q2. Which completed consultations have no next appointment, treatment plan, or follow-up task?

- Priority: P0 | Workflow: Consultation and follow-up | Reviewer: doctor / operator
- Default level: row-level (worklist)
- Output: rows of `person_uid, consult_date, location, provider, owner, days_since_consult`
- Filters: `date_range`, `location_id`, `provider_id`, `owner_id`, `min_days_since_consult`
- Terms: `consultation_completed`, `no_next_action`, `stale_followup`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: stale threshold (config-driven; default candidate 7 days);
  whether SF task counts as "next" even if no appointment booked

### Q3. Which patients accepted treatment after consultation, grouped by location and provider?

- Priority: P1 | Workflow: Treatment and revenue | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate count and `treatment_accepted_amount` grouped by
  `location, provider`; drilldown rows of
  `person_uid, accepted_date, location, provider, treatment_total`
- Filters: `date_range`, `location_id`, `provider_id`, `min_accepted_amount`
- Terms: `consultation_completed`, `treatment_accepted`, `treatment_accepted_amount`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: source of "accepted" (CareStack treatment plan status vs
  SF opportunity stage); whether partial acceptance (single phase) counts;
  attribution window from consult to acceptance

### Q4. Which treatment plans were proposed but not accepted, grouped by reason or current stage when available?

- Priority: P1 | Workflow: Treatment and revenue | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate count grouped by `decline_reason` or `current_stage`;
  drilldown rows of `person_uid, proposed_date, provider, treatment_total, decline_reason, current_stage`
- Filters: `date_range`, `location_id`, `provider_id`
- Terms: `treatment_proposed`, `treatment_not_accepted`, `decline_reason`
- Data classes: `ops`, `identity`, `billing`, `phi_adjacent`
- Ambiguities: reason field availability (often free text in CareStack;
  may need normalization); difference between "declined" and "no decision
  yet"; stage taxonomy normalization across systems

### Q5. Which accepted treatment cases have no recorded payment evidence yet?

- Priority: P0 | Workflow: Treatment and revenue | Reviewer: doctor / operator
- Default level: row-level (worklist)
- Output: rows of `person_uid, accepted_date, treatment_total, days_since_acceptance, owner`
- Filters: `date_range`, `location_id`, `min_treatment_total`, `min_days_since_acceptance`
- Terms: `treatment_accepted`, `no_payment_evidence`, `revenue_evidence`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: what counts as "payment evidence" (recorded payment,
  invoice issued, deposit only?); attribution window from acceptance to
  expected first payment; treatment plans with insurance pending

### Q6. Which patients have outstanding balances after treatment was accepted or completed?

- Priority: P0 | Workflow: Payment and balance | Reviewer: doctor / operator
- Default level: row-level (worklist)
- Output: rows of `person_uid, outstanding_balance, last_payment_date, treatment_status, owner`
- Filters: `as_of_date`, `location_id`, `min_balance`, `treatment_status`
- Terms: `treatment_accepted`, `treatment_completed`, `balance_outstanding`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: balance source-of-truth (CareStack ledger vs derived from
  invoices/payments); cutoff (today vs end-of-period); whether write-offs
  reduce balance

### Q7. Which consultations resulted in no-shows, grouped by source, location, and owner?

- Priority: P1 | Workflow: Consultation and follow-up | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate count and no-show rate grouped by `lead_source, location, owner`;
  drilldown rows of `person_uid, scheduled_date, lead_source, location, owner`
- Filters: `date_range`, `lead_source`, `location_id`, `owner_id`
- Terms: `consultation_no_show`, `lead_source`, `consultation_scheduled`
- Data classes: `ops`, `identity`
- Ambiguities: how no-show is marked (CareStack status vs SF event);
  cancelled vs no-show vs rescheduled disambiguation; attribution of lead
  source for patients with multiple touches

### Q8. Which people are reactivation candidates because they completed a consult but did not schedule treatment within the configured threshold?

- Priority: P1 | Workflow: Consultation and follow-up | Reviewer: doctor / operator
- Default level: row-level (worklist)
- Output: rows of `person_uid, consult_date, days_since_consult, last_owner, last_contact_date`
- Filters: `date_range`, `min_days_since_consult`, `location_id`, `owner_id`
- Terms: `consultation_completed`, `no_treatment_scheduled`, `reactivation_candidate`,
  `stale_threshold`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: threshold (config-driven; candidate 30–60 days); whether
  unresponsive vs explicit decline both count; exclusion of recently
  re-engaged patients

### Q9. Which patients paid after consultation, and how long did it take from consult to first payment?

- Priority: P1 | Workflow: Payment and balance | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate `time_to_first_payment` (p50, p90) grouped by
  `location, lead_source`; drilldown rows of
  `person_uid, consult_date, first_payment_date, first_payment_amount, days_consult_to_payment`
- Filters: `date_range`, `location_id`, `lead_source`
- Terms: `consultation_completed`, `payment_received`, `time_to_payment`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: which payment counts as "first" (deposit vs first scheduled
  invoice payment); attribution if treatment was accepted before consult
  was logged

### Q10. Which locations have the highest conversion from consultation to accepted treatment?

- Priority: P2 | Workflow: Location, owner, provider operations | Reviewer: doctor / operator
- Default level: aggregate
- Output: aggregate `consultation_completed`, `treatment_accepted`,
  `consultation_to_acceptance_rate` grouped by `location`
- Filters: `date_range`, `location_id`
- Terms: `consultation_completed`, `treatment_accepted`, `conversion_rate`
- Data classes: `ops`
- Ambiguities: attribution window for consult-to-acceptance; whether
  cancelled consults count in denominator

### Q11. Which providers or treatment coordinators have the most stale consult follow-ups?

- Priority: P2 | Workflow: Location, owner, provider operations | Reviewer: doctor / operator
- Default level: aggregate + drilldown
- Output: aggregate `stale_followup_count` grouped by `owner`; drilldown rows of
  `person_uid, last_activity_date, days_since_activity, owner`
- Filters: `date_range`, `min_days_since_activity`, `location_id`, `owner_id`
- Terms: `stale_followup`, `owner`, `consultation_completed`
- Data classes: `ops`, `identity`
- Ambiguities: definition of "owner" (provider vs treatment coordinator vs
  SF lead owner); stale threshold

### Q12. Which high-value treatment opportunities are stalled with no next action?

- Priority: P2 | Workflow: Treatment and revenue | Reviewer: doctor / operator
- Default level: row-level (worklist)
- Output: rows of `person_uid, proposed_date, treatment_total, days_since_proposed, owner`
- Filters: `min_treatment_total`, `min_days_since_proposed`, `location_id`, `owner_id`
- Terms: `treatment_proposed`, `no_next_action`, `high_value_threshold`,
  `stale_followup`
- Data classes: `ops`, `identity`, `billing`, `phi_adjacent`
- Ambiguities: high-value threshold (config-driven; candidate $5k+);
  "no next action" definition same as Q2

### Q13. Which CareStack-linked people have incomplete operational timeline evidence for consultation, treatment, invoice, or payment milestones?

- Priority: P3 | Workflow: Identity and provenance quality | Reviewer: doctor / operator
- Default level: row-level (data-quality worklist)
- Output: rows of `person_uid, carestack_id, missing_milestones[]` where
  `missing_milestones` is a subset of `consultation, treatment_plan, invoice, payment`
- Filters: `date_range`, `location_id`, `missing_milestone`
- Terms: `carestack_linked`, `milestone_evidence_missing`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: required-vs-optional milestones for new patients;
  attribution of missing data to ingest gap vs business absence

### Q14. Which patients have payment received, refund issued, failed payment, or balance changed events during the selected period?

- Priority: P2 | Workflow: Payment and balance | Reviewer: doctor / operator
- Default level: row-level (event ledger)
- Output: rows of `person_uid, event_type, event_date, amount, related_invoice_id`
  where `event_type ∈ {payment_received, refund_issued, payment_failed, balance_changed}`
- Filters: `date_range`, `event_type`, `location_id`, `person_uid`
- Terms: `payment_received`, `refund_issued`, `payment_failed`, `balance_changed`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: payment_failed source (gateway log vs CareStack); whether
  internal write-offs count as `balance_changed`

### Q15. Which accepted treatment cases are missing source references back to Salesforce or CareStack evidence?

- Priority: P3 | Workflow: Identity and provenance quality | Reviewer: doctor / operator
- Default level: row-level (data-quality worklist)
- Output: rows of `person_uid, accepted_date, treatment_total, missing_sources[]`
  where `missing_sources` is a subset of `salesforce, carestack`
- Filters: `date_range`, `location_id`, `missing_source`
- Terms: `treatment_accepted`, `source_reference_missing`,
  `salesforce_linked`, `carestack_linked`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: expected source coverage per patient cohort (new vs
  recurring); whether manual entries without source still count as
  accepted

## Marketing Director Questions

### Q16. Which lead sources produced paid patients in the selected period?

- Priority: P0 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `paid_lead_count`, `revenue_total` grouped by `lead_source`;
  drilldown rows of `person_uid, lead_source, first_payment_date, payment_total`
- Filters: `date_range`, `lead_source`, `location_id`
- Terms: `lead_source`, `paid_lead`, `revenue_evidence`, `payment_received`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Ambiguities: attribution window (lead created → first payment); when a
  lead has multiple sources (first-touch vs last-touch); "paid" definition
  (any payment vs paid in full)

### Q17. Which Facebook leads reached consultation, accepted treatment, and produced payment evidence?

- Priority: P0 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: funnel counts `lead → consult_scheduled → consult_completed → treatment_accepted → payment_received`
  for `facebook_source`; drilldown rows per stage
- Filters: `date_range`, `campaign_id`, `location_id`
- Terms: `facebook_source`, `paid_social_source`, `conversion_funnel`,
  `consultation_completed`, `treatment_accepted`, `payment_received`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Ambiguities: how `facebook_source` is identified (raw source string vs
  UTM medium=`paid_social`+source=`facebook` vs SF lead_source field);
  attribution model

### Q18. Which Google Ads campaigns produced consultations and revenue evidence?

- Priority: P1 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `lead_count`, `consultation_completed`, `revenue_total`
  grouped by `campaign`; drilldown rows of `person_uid, campaign, lead_date, revenue_total`
- Filters: `date_range`, `campaign_id`, `location_id`
- Terms: `google_ads_source`, `campaign`, `consultation_completed`,
  `revenue_evidence`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Ambiguities: how `google_ads_source` is identified; how campaign id is
  normalized across UTM, SF, and ad platform; expected attribution window

### Q19. What is the conversion funnel by source: lead created, consult scheduled, consult completed, treatment accepted, payment received?

- Priority: P0 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate
- Output: 5-stage funnel grouped by `lead_source`; values per stage and
  per stage-to-stage rate
- Filters: `date_range`, `lead_source`, `location_id`
- Terms: `lead_source`, `conversion_funnel`, `consultation_scheduled`,
  `consultation_completed`, `treatment_accepted`, `payment_received`
- Data classes: `ops`, `identity`, `billing`
- Ambiguities: cohort definition (leads created in period vs leads that
  reached each stage in period); attribution windows per stage

### Q20. Which campaigns have the highest no-show rate after consultation was scheduled?

- Priority: P1 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `consultation_scheduled`, `consultation_no_show`,
  `no_show_rate` grouped by `campaign`; drilldown to person-level no-shows
- Filters: `date_range`, `campaign_id`, `location_id`, `min_volume`
- Terms: `campaign`, `consultation_scheduled`, `consultation_no_show`,
  `no_show_rate`
- Data classes: `ops`, `identity`
- Ambiguities: cancelled vs no-show; minimum volume threshold for
  statistical comparison

### Q21. Which lead sources generate the highest treatment accepted amount or payment total?

- Priority: P1 | Workflow: Treatment and revenue | Reviewer: marketing director
- Default level: aggregate
- Output: aggregate `treatment_accepted_amount`, `payment_total` grouped
  by `lead_source`; sortable by either metric
- Filters: `date_range`, `lead_source`, `location_id`
- Terms: `lead_source`, `treatment_accepted_amount`, `payment_total`,
  `revenue_evidence`
- Data classes: `ops`, `billing`, `integration_metadata`
- Ambiguities: same attribution model decision as Q16; whether to include
  accepted-but-not-paid revenue vs only realized payment

### Q22. Which owners or centers convert paid social leads fastest from lead to consultation?

- Priority: P2 | Workflow: Location, owner, provider operations | Reviewer: marketing director
- Default level: aggregate
- Output: aggregate `time_to_consultation` (p50, p90) grouped by
  `owner, location` for `paid_social_source`
- Filters: `date_range`, `paid_social_source`, `location_id`, `owner_id`
- Terms: `paid_social_source`, `time_to_consultation`, `owner`, `location`
- Data classes: `ops`, `identity`
- Ambiguities: definition of `paid_social_source` (Facebook + Instagram +
  TikTok?); whether to include consultation_scheduled or only
  consultation_completed

### Q23. Which campaigns produce many leads but few CareStack-linked people?

- Priority: P2 | Workflow: Identity and provenance quality | Reviewer: marketing director
- Default level: aggregate
- Output: aggregate `lead_count`, `carestack_linked_count`, `link_rate`
  grouped by `campaign`
- Filters: `date_range`, `campaign_id`, `min_lead_count`
- Terms: `campaign`, `carestack_linked`, `link_rate`
- Data classes: `ops`, `integration_metadata`
- Ambiguities: what counts as "linked" (any CareStack patient_id vs
  patient_id with at least one appointment); expected link rate baseline

### Q24. Which sources produce hot leads with no follow-up within the configured SLA?

- Priority: P2 | Workflow: Consultation and follow-up | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `hot_lead_count`, `sla_breach_count` grouped by
  `lead_source`; drilldown rows of `person_uid, lead_source, lead_created_at, sla_breach_minutes`
- Filters: `date_range`, `lead_source`, `sla_minutes`
- Terms: `lead_source`, `hot_lead`, `sla_breach`, `stale_followup`
- Data classes: `ops`, `identity`
- Ambiguities: how "hot" is defined (SF lead rating vs source + form
  type); SLA value (config-driven; candidate 5 or 15 minutes for paid
  social)

### Q25. Which UTM source, medium, campaign, and business unit combinations produce the strongest paid-lead conversion?

- Priority: P2 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate
- Output: aggregate `lead_count`, `paid_lead_count`, `paid_lead_rate`
  grouped by `utm_source, utm_medium, utm_campaign, business_unit`
- Filters: `date_range`, `utm_source`, `utm_medium`, `utm_campaign`,
  `business_unit`, `min_lead_count`
- Terms: `utm_combination`, `paid_lead`, `business_unit`
- Data classes: `ops`, `billing`, `integration_metadata`
- Ambiguities: UTM normalization (lowercasing, trimming, null handling);
  business_unit field source (SF account vs CareStack location)

### Q26. Which source channels have the highest outstanding balance after treatment?

- Priority: P2 | Workflow: Payment and balance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `outstanding_balance_total`, `patient_count` grouped
  by `lead_source`; drilldown rows of `person_uid, lead_source, outstanding_balance, treatment_status`
- Filters: `as_of_date`, `lead_source`, `min_balance`
- Terms: `lead_source`, `balance_outstanding`, `treatment_status`
- Data classes: `ops`, `identity`, `billing`, `integration_metadata`
- Ambiguities: balance source-of-truth (same as Q6); attribution of
  source for long-running patients

### Q27. Which leads are linked to CareStack but missing a next appointment?

- Priority: P1 | Workflow: Consultation and follow-up | Reviewer: marketing director
- Default level: row-level (worklist)
- Output: rows of `person_uid, lead_source, carestack_id, last_appointment_date, days_since_last_appointment`
- Filters: `date_range`, `lead_source`, `location_id`, `min_days_since_last_appointment`
- Terms: `carestack_linked`, `no_next_appointment`, `stale_followup`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: difference between "no next appointment" and "no future
  scheduled appointment" (past-due appointment not rescheduled); stale
  threshold

### Q28. Which Salesforce leads could not be linked to a person or CareStack patient?

- Priority: P3 | Workflow: Identity and provenance quality | Reviewer: marketing director
- Default level: row-level (data-quality worklist)
- Output: rows of `sf_lead_id, lead_source, lead_created_at, link_status`
  where `link_status ∈ {no_person_link, no_carestack_link, both_missing}`
- Filters: `date_range`, `lead_source`, `link_status`
- Terms: `unlinked_salesforce_lead`, `salesforce_linked`,
  `carestack_linked`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: expected link rate per source; whether spam/invalid leads
  should be excluded from this view

### Q29. Which locations are underperforming on consultation completion after lead creation?

- Priority: P1 | Workflow: Location, owner, provider operations | Reviewer: marketing director
- Default level: aggregate
- Output: aggregate `lead_count`, `consultation_completed`,
  `consultation_completion_rate` grouped by `location`
- Filters: `date_range`, `location_id`, `min_lead_count`
- Terms: `location`, `consultation_completion_rate`, `lead_source`
- Data classes: `ops`
- Ambiguities: attribution window for completion (within N days vs
  open-ended); whether walk-ins count

### Q30. Which sources create the most reactivation candidates after completed consults?

- Priority: P2 | Workflow: Lead source and campaign performance | Reviewer: marketing director
- Default level: aggregate + drilldown
- Output: aggregate `reactivation_candidate_count` grouped by `lead_source`;
  drilldown rows of `person_uid, lead_source, consult_date, days_since_consult`
- Filters: `date_range`, `lead_source`, `min_days_since_consult`
- Terms: `lead_source`, `reactivation_candidate`, `consultation_completed`,
  `stale_threshold`
- Data classes: `ops`, `identity`, `integration_metadata`
- Ambiguities: shared with Q8 (threshold, exclusion of re-engaged)

## Workflow Group Index

| Workflow | Questions |
| --- | --- |
| Lead source and campaign performance | 16, 17, 18, 19, 20, 21, 25, 30 |
| Consultation and follow-up | 1, 2, 7, 8, 24, 27 |
| Treatment and revenue | 3, 4, 5, 12, 21 |
| Payment and balance | 6, 9, 14, 26 |
| Location, owner, provider operations | 10, 11, 22, 29 |
| Identity and provenance quality | 13, 15, 23, 28 |

## Priority Roll-Up

| Priority | Questions |
| --- | --- |
| P0 | 1, 2, 5, 6, 16, 17, 19 |
| P1 | 3, 4, 7, 8, 9, 18, 20, 21, 27, 29 |
| P2 | 10, 11, 12, 14, 22, 23, 24, 25, 26, 30 |
| P3 | 13, 15, 28 |

## Output Expectations And Guardrails

- Default outputs may include aggregate summaries and row-level
  drilldowns for current production users, who are treated as authorized
  internal users during this mission phase.
- Row-level outputs must still use service-owned result contracts, source
  references, data-class markings, and audit where required.
- Raw provider payloads are not ordinary analytics output and must not be
  returned by the dashboard, manager AI chat, or Data Intelligence Agent
  surfaces.
- PHI access, when required, still goes through `PhiService` with audit.
  No question in this V1 list is expected to require clinical-note PHI.
  Several questions touch `phi_adjacent` (appointment context, treatment
  metadata) and `billing` (payments, balances). These data classes must
  be explicitly classified by the catalog and routed through approved
  services before exposure.
- Result contracts must declare applied semantic definitions and versions,
  applied filters, data classes touched, aggregation level, row count,
  and any gaps or warnings.
- Service-layer field allowlists govern row-level output. The mere fact
  that a question is listed here does not authorize exposing arbitrary
  person fields.

## Cross-Cutting Ambiguities And Clarification Notes

The following ambiguities recur across multiple questions and should be
resolved in the semantic catalog (ENG-273) before service implementation
(ENG-277):

1. **Source attribution model.** First-touch, last-touch, or multi-touch
   when a person has multiple lead sources. Affects Q16, Q17, Q18, Q19,
   Q21, Q25, Q26.
2. **Attribution windows.** Lead-to-consult, consult-to-acceptance,
   acceptance-to-first-payment. Affects Q3, Q5, Q9, Q10, Q19, Q22.
3. **Stale thresholds.** Config-driven defaults for stale follow-up,
   reactivation, no-next-action, missing-next-appointment. Affects Q2,
   Q8, Q11, Q12, Q27, Q30.
4. **Source normalization.** How `facebook_source`, `google_ads_source`,
   and `paid_social_source` map to raw SF `lead_source`, UTM tuples, and
   ad platform identifiers. Affects Q17, Q18, Q22, Q25.
5. **Balance source-of-truth.** Whether outstanding balance is the
   CareStack ledger value or computed from invoices and payments.
   Affects Q6, Q26.
6. **Payment evidence definition.** Whether "paid" means any recorded
   payment, deposit only, or paid in full. Affects Q5, Q9, Q16, Q21.
7. **CareStack link definition.** Patient_id present vs patient_id with
   at least one appointment. Affects Q13, Q23, Q27, Q28.
8. **Owner definition.** Provider, treatment coordinator, or SF lead
   owner. Affects Q7, Q11, Q22.
9. **Cancelled vs no-show vs rescheduled.** Disambiguation across SF and
   CareStack signals. Affects Q7, Q20.
10. **Business unit and location.** Source field for `business_unit` and
    `location` (SF account vs CareStack center). Affects Q25, Q29.

These items are inputs to ENG-273 (Semantic Analytics Catalog V1). They
are not blockers for ENG-272 (this seed spec) becoming reviewed.

## Candidate First Catalog Terms

The following terms are referenced by the questions above and should be
defined in ENG-273. Inclusion here is a candidate signal, not an
approved catalog entry.

Core cohort and outcome terms:

- `paid_lead`
- `converted_to_consultation`
- `consultation_scheduled`
- `consultation_completed`
- `consultation_no_show`
- `treatment_proposed`
- `treatment_accepted`
- `treatment_completed`
- `treatment_not_accepted`
- `payment_received`
- `payment_failed`
- `refund_issued`
- `balance_outstanding`
- `balance_changed`
- `revenue_evidence`
- `no_payment_evidence`
- `no_next_action`
- `no_next_appointment`
- `no_treatment_scheduled`
- `reactivation_candidate`
- `hot_lead`
- `stale_followup`

Source and attribution terms:

- `lead_source`
- `facebook_source`
- `google_ads_source`
- `paid_social_source`
- `campaign`
- `utm_combination`
- `business_unit`

Operational and provenance terms:

- `location`
- `provider`
- `owner`
- `carestack_linked`
- `salesforce_linked`
- `unlinked_salesforce_lead`
- `source_reference_missing`
- `milestone_evidence_missing`
- `link_rate`

Derived metrics and thresholds:

- `conversion_funnel`
- `conversion_rate`
- `consultation_completion_rate`
- `no_show_rate`
- `time_to_consultation`
- `time_to_payment`
- `treatment_accepted_amount`
- `payment_total`
- `outstanding_balance_total`
- `paid_lead_rate`
- `sla_breach`
- `stale_threshold`
- `high_value_threshold`

## Next Steps

1. Human review of priority assignment, especially the P0 set, before
   ENG-273 begins.
2. ENG-273 (Semantic Analytics Catalog V1) defines each candidate term
   with synonyms, source fields, data class, permission, row-level rule,
   allowed fields, version, owner, and review status.
3. ENG-273 resolves the cross-cutting ambiguities listed above.
4. ENG-274 (Structured Analytics Query Spec) defines the JSON shape that
   maps these questions to typed query specs.
5. ENG-282 (Semantic Analytics Workbench V1) renders this spec for
   in-app reading once stable.
