# Person Journey Field And Event Registry V1

## Summary

Fusion CRM is no longer dealing with one static person snapshot. A person's
business meaning can be assembled from Salesforce Lead, Contact, Account,
Opportunity, OpportunityHistory, Tasks, Cases, CareStack evidence, and
timeline events over time.

This registry defines the first governance layer for those fields and events.
It exists so Agent Runtime, Data Intelligence, Semantic Analytics, manager
answers, charts, and reports do not infer business meaning directly from raw
provider JSON keys.

The rule is simple:

```text
new field or event
-> source and data-class classification
-> semantic registry status
-> human/catalog review where needed
-> approved query/read-model usage only after approval
```

## Why This Exists

Managers will ask questions such as:

- Which sources create real opportunities?
- Which campaigns create stage movement?
- Which converted leads became person-linked opportunities?
- How fast do opportunities move between stages?
- Which no-show or follow-up segments recovered into consultation?

Those questions need more than the current aggregate lead funnel. They need
field and event semantics that are stable across surfaces. Without this
registry, one surface can treat a provider field as attribution, another can
treat it as raw metadata, and an agent can accidentally explain an unreviewed
field as business truth.

## Production State Versus Branch State

### Production / Main After PR 122

PR 122 (`8a1f5b4`) shipped frontend timeline grouping only.

The production-visible frontend can understand a broader timeline enum, but
that does not mean every backend emitter and migration is production-active.

Visible frontend enum additions include:

- `contact_created`
- `opportunity_stage_changed`
- `salesforce_contact`
- `salesforce_account`
- `salesforce_opportunity_history`
- `call_recording_ref`

The important governance point:

```text
frontend enum support is not semantic approval
```

### Current Branch Line

The ENG-371 branch line also contains backend-oriented person journey pieces:

- `packages/ingest/sf_contact_service.py`
- `packages/ingest/sf_account_service.py`
- `packages/ingest/sf_opportunity_history_service.py`
- migration `20260609_2200_f5a6b7c8d9e0_extend_funnel_kind_constraints.py`
- backend enum support for `contact_created`,
  `opportunity_stage_changed`, `salesforce_contact`, `salesforce_account`,
  and `salesforce_opportunity_history`

These are registry candidates, not automatically approved downstream
analytics semantics.

## Registry Statuses

| Status | Meaning |
| --- | --- |
| `approved_candidate` | Safe to model as a candidate business concept; still needs read-model/query binding before execution. |
| `review_only` | Data Intelligence may propose mappings, but downstream answers/charts must not treat it as approved truth. |
| `blocked` | Must not be used in Semantic Analytics, manager answers, charts, or reports. |
| `internal_only` | Operational/debug metadata; useful for engineering, not business semantics. |
| `deferred` | Valid future concept, but blocked by deployment, policy, data quality, or audit gaps. |

## ENG-392 Structured Coverage Dimensions

The structured Data Intelligence registry now carries coverage metadata for
each entry:

- `journey_phase`
- `state_category`
- `source_object`
- `transition_meaning`
- `time_semantics`
- `sale_revenue_posture`

This is intentionally more detailed than a flat field list. The goal is to
show where a field or event lives in the person journey and what it can mean
before any manager answer, chart, report, or export is allowed to use it.

Current coverage phases:

| Phase | Examples | Execution posture |
| --- | --- | --- |
| `lead_attribution` | UTM, referral, click evidence | Review/catalog first. |
| `lead_capture` | Lead status, lead created/updated | Time-window and status taxonomy required. |
| `contact_linkage` | Converted contact, contact created | Linkage confidence required. |
| `account_linkage` | Converted account, account created | Identity-adjacent; not household truth. |
| `opportunity` | Opportunity created | Person linkage required. |
| `opportunity_stage` | Stage name, stage history | Stage taxonomy and transition time required. |
| `sale_conversion` | Won/lost, close date, amount, loss reason | Sale evidence; not collected revenue by itself. |
| `follow_up_activity` | Tasks and call references | Task taxonomy; call refs blocked. |
| `support_case` | Case opened/closed posture | Case taxonomy and sensitivity review required. |
| `consultation` | CareStack appointment lifecycle | Timezone normalization required. |
| `treatment` | Treatment status/completed | Clinical detail remains excluded. |
| `billing_revenue` | Payment bucket/payment recorded | Aggregate-only billing policy. |
| `internal_health` | Unchanged count, watermarks | Engineering-only, not business semantics. |

Sale and revenue are deliberately separated:

```text
Salesforce Opportunity amount / won / lost
-> sale pipeline or sale outcome evidence
-> not collected treatment revenue

CareStack payment recorded / payment amount bucket
-> collected revenue evidence
-> aggregate-only until billing policy, audit, and export rules are approved
```

## Initial Field Registry

| Field | Source | Raw or canonical | Data class | Staff UI | Agent / analytics posture | Registry status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `utm_source` | Salesforce Lead.extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only until attribution model approved | `approved_candidate` | Already referenced by Semantic Analytics docs; needs source precedence and backfill coverage. |
| `utm_medium` | Salesforce Lead.extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only until attribution model approved | `approved_candidate` | Needed for UTM combination analysis. |
| `utm_campaign` | Salesforce Lead.extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only until attribution model approved | `approved_candidate` | Can drive campaign performance only after mapping review. |
| `gclid` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed with masking posture if needed | review-only mapping signal | `review_only` | Strong Google Ads evidence, but not a manager-facing label by itself. |
| `fbclid` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed with masking posture if needed | review-only mapping signal | `review_only` | Strong Meta/Facebook evidence, but not a manager-facing label by itself. |
| `landing_page` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only evidence | `review_only` | Useful for attribution QA; not approved campaign/source meaning alone. |
| `placement` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only evidence | `review_only` | Can help paid/social mapping proposals. |
| `referral_source` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only until referral taxonomy approved | `approved_candidate` | Needs normalization for doctor/friend/internal referral meanings. |
| `ad_network` | Salesforce Lead / Opportunity extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only until ad-network taxonomy approved | `approved_candidate` | Candidate dimension for paid source performance. |
| `hubspot_lead_source` | Salesforce Lead.extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only mapping signal | `review_only` | May conflict with Salesforce lead source and UTM fields. |
| `record_source_detail` | Salesforce Lead.extra | canonical key carrying provider value | ops, integration metadata | allowed | review-only mapping signal | `review_only` | Needs conflict handling with source/campaign fields. |
| `assigned_center` | Salesforce Lead.extra | canonical key carrying provider value | ops | allowed | query filter candidate after location mapping | `approved_candidate` | Needs center/location normalization. |
| `business_unit` | Salesforce Lead.extra | canonical key carrying provider value | ops | allowed | query filter candidate after business-unit taxonomy | `approved_candidate` | Needed for cross-unit analytics. |
| `owner_id` | Salesforce Lead.extra | raw provider actor reference | ops, identity-adjacent | allowed as id/ref only | review-only until actor mapping is approved | `review_only` | Must resolve through actor/owner semantics before manager reporting. |
| `consultation_scheduled_at` | Salesforce Lead.extra | canonical key carrying provider value | ops | allowed | time evidence candidate | `approved_candidate` | Must not conflict with CareStack appointment evidence. |
| `converted_contact_id` | Salesforce Lead.extra | canonical key carrying provider id | ops, identity-adjacent | allowed as source ref | linkage candidate | `approved_candidate` | Supports Lead -> Contact person journey. |
| `converted_account_id` | Salesforce Lead.extra | canonical key carrying provider id | ops, identity-adjacent | allowed as source ref | linkage candidate | `approved_candidate` | Supports Account path only after account source links are active. |
| `converted_opportunity_id` | Salesforce Lead.extra | canonical key carrying provider id | ops, integration metadata | allowed as source ref | linkage candidate | `approved_candidate` | Supports Lead -> Opportunity journey and source quality. |
| `unchanged_count` | ingest summaries | internal computed | internal/debug | engineering only | not allowed | `internal_only` | Sync performance counter, not business meaning. |
| `watermark` | ingest jobs | internal computed | internal/debug | engineering only | not allowed | `internal_only` | Do not expose as Semantic Catalog term. |
| raw provider payload fields | ingest.raw_event | raw provider payload | varies, often sensitive | inspector only by policy | not allowed | `blocked` | Agent Runtime must not infer semantics from raw payloads. |
| `call_recording_ref` | interaction event data class | reference to call artifact | pending review | limited / pending review | not allowed | `blocked` | Requires review before analytics, answers, or charts. |

## Initial Event Registry

| Event kind | Source kind | Business meaning | Data class | Staff UI | Agent / analytics posture | Registry status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lead_created` | `salesforce_lead` | Lead entered CRM evidence. | ops | allowed | approved aggregate candidate | `approved_candidate` | Already used by lead/source analytics. |
| `lead_updated` | `salesforce_lead` | Lead changed in CRM. | ops | allowed | review-only for stage/change analytics | `review_only` | Needs field-level change semantics before manager answers. |
| `contact_created` | `salesforce_contact` | Post-conversion contact evidence. | ops, identity-adjacent | allowed when backend deployed | person journey candidate | `deferred` | Frontend enum can display it; backend/migration deployment must be confirmed before production claims. |
| `opportunity_created` | `salesforce_opportunity` | Opportunity object evidence. | ops | allowed | approved candidate for opportunity analytics | `approved_candidate` | Needs person linkage confidence. |
| `opportunity_stage_changed` | `salesforce_opportunity_history` | Opportunity moved between stages. | ops | allowed when backend deployed | stage velocity candidate | `deferred` | Requires stage taxonomy, timestamp semantics, and deployment confirmation. |
| `opportunity_won` | `salesforce_opportunity` | Opportunity reached won/closed-won posture. | ops | allowed | conversion quality candidate | `approved_candidate` | Needs win definition review. |
| `opportunity_lost` | `salesforce_opportunity` | Opportunity reached lost/closed-lost posture. | ops | allowed | conversion quality candidate | `approved_candidate` | Needs loss reason taxonomy if used. |
| `task_created` | `salesforce_task` | Operational task created. | ops | allowed | follow-up workload candidate | `review_only` | Needs task-type taxonomy. |
| `task_completed` | `salesforce_task` | Operational task completed. | ops | allowed | follow-up workload candidate | `review_only` | Needs task-type taxonomy. |
| `call_logged` | `salesforce_task` | Call activity evidence. | ops | allowed without recording refs | activity analytics candidate | `review_only` | Must exclude call recordings and PHI-bearing notes. |
| `call_reference_found` | `salesforce_task` | Call recording/reference evidence detected. | call_recording_ref | pending review | not allowed | `blocked` | Do not use in manager analytics until reviewed. |
| `case_opened` | `salesforce_case` | Case/support workflow opened. | ops | allowed | review-only | `review_only` | Needs case taxonomy. |
| `case_closed` | `salesforce_case` | Case/support workflow closed. | ops | allowed | review-only | `review_only` | Needs case taxonomy. |
| CareStack consultation events | `carestack_appointment` | Consultation lifecycle evidence. | ops | allowed | approved aggregate candidate | `approved_candidate` | Existing consultation analytics consume these concepts. |
| CareStack treatment/payment events | CareStack treatment, invoice, accounting transaction | Treatment and billing evidence. | billing / ops | allowed by role/posture | review-only to approved depending on term | `review_only` | Billing analytics require stricter definitions and policy. |

## Downstream Usage Rules

### Data Intelligence Agent

DIA may inspect approved datasets and produce review-only proposals for:

- unknown attribution values;
- conflicting source fields;
- unmapped campaign/source labels;
- new event kinds;
- linkage gaps between Lead, Contact, Account, Opportunity, and Person;
- missing opportunity history coverage.

DIA must not auto-approve catalog meaning.

ENG-388 adds the first deterministic projection path:

```text
packages.data_intelligence structured person journey registry
-> data_intelligence_person_journey_proposals tool
-> review-only Semantic Catalog proposal drafts
-> human proposal review
```

That tool can submit `approved_candidate` and `review_only` entries for human
review. It still marks every result as non-executable and not auto-approved.
`blocked`, `internal_only`, and `deferred` entries are returned only as
fail-closed review context.

ENG-390 adds the service-owned persistence path:

```text
review-only person journey proposal drafts
-> AnalyticsCatalogReviewService.ingest_person_journey_registry_proposals
-> Semantic Catalog proposal review storage
-> human approval/rejection/unresolved workflow
```

This persistence path creates only proposed review rows. It does not approve
catalog versions and it does not make manager answers, charts, reports, or
exports executable from person journey fields/events.

### Semantic Catalog

The catalog may approve terms only after human review. Initial candidate terms:

- `attribution_source`
- `utm_combination`
- `paid_source`
- `referral_source`
- `lead_to_opportunity_linkage`
- `opportunity_stage`
- `opportunity_stage_velocity`
- `person_journey_event`
- `source_quality`

### Query Registry And Read Models

No query registry entry should use these new candidates until it declares:

- approved catalog version refs;
- exact source fields/events;
- time-window semantics;
- data classes;
- row-level posture;
- warnings for backfill or linkage coverage.

Candidate future read models:

- `source_quality_by_opportunity`
- `opportunity_stage_velocity`
- `lead_to_opportunity_journey`
- `campaign_opportunity_conversion`
- `person_journey_coverage`

### Agent Runtime And Manager Answers

Agent Runtime can display these registry entries as metadata, but manager
answers and charts must use only approved aggregate execution output.

If a manager asks about an unapproved field/event, the correct behavior is:

```text
clarification or blocked posture
-> explain that the field/event is review-only
-> do not produce a metric as business truth
```

## Known Risks

- Attribution backfills require re-import/backfill; current coverage may be
  incomplete.
- Duplicate source links and FK-pinned records can distort linkage coverage.
- Visit/appointment date timezone shifts are unresolved and must not be hidden
  inside manager answers.
- Frontend enum support can precede backend deployment. Treat that as display
  readiness, not backend execution readiness.
- `call_recording_ref` needs a dedicated policy and review decision.

## V1 Acceptance

V1 is considered useful when:

- every initial field/event above has a status;
- blocked/internal fields are explicitly excluded from catalog approval;
- Data Intelligence proposal posture is clear;
- Query Registry/read-model usage remains gated by approved catalog versions;
- production-active versus branch-only state is visible;
- future work can add a registry entry instead of inventing semantics ad hoc.
