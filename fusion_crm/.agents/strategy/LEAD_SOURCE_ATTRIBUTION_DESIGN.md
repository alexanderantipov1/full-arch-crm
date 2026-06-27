# Lead Source Attribution — Design (0% unknown)

Epic: ENG-446 (blocks ENG-447…450). Depends on the full-fidelity capture
(ENG-425), which now provides every signal we need.

## Goal & principle

Make every lead's origin knowable. "unknown" is a REPORTING gap, not a data
gap — the trace almost always exists, just not in `utm_source`. We model source
as a **hierarchical distribution chain** and resolve it from captured signals,
with staff able to correct/enrich it in our own system.

Principle: **resolve, don't guess; never silently `unknown`.** A lead with no
recognizable signal lands in an explicit `needs_review` bucket (target ~0%),
not in "unknown".

## The chain (attribution dimension)

Source is not one value — it is an ordered chain we can slice analytics by at
every level:

```
vendor   — who runs the ad ops (agency / in-house): Dima, ROMI, Daniel Creatives, In-house, N/A
  channel — platform / medium: facebook, google, tiktok, phone, direct, manual, referral, organic
    campaign — utm_campaign / last_touch_campaign
      ad_set — utm_adgroup
        ad — utm_content / utm_creative
          form — Hubspot_Lead_Source / Record_Source_Detail / landing_page
agent      — CreatedBy.Name (staff) for manual / phone leads (a parallel axis)
```

Analytics slices the funnel (lead → consult → … → collected) by ANY level and
drills the hierarchy (vendor → its channels → its campaigns → …).

## Real-data grounding (why this works)

Over 64,345 distinct leads (latest capture):

- `utm_source` 30%, `utm_medium` 28%, `utm_campaign` 28%, `last_touch_source`
  18%; `LeadSource` (standard SF) DEAD at 0.1%.
- `Business_Unit__c` 99.5%, `Assigned_Center__c` 52% — near-universal dimensions.
- The campaign-name fields carry real names ("Roseville Lead Gen Fusion",
  "Dima - Facebook Lead Form EDH", "SEM_*"), and `Hubspot_Lead_Source__c` carries
  FORM / integration-point names ("…Lead Capturing Form FB", "CallRail",
  "ApiX-Drive", "Zapier").
- `CreatedBy.Name` (now captured + backfilled for 2026) resolves manual leads to
  a staff person (e.g. the example "unknown" lead → created by **Olga Kolomyza**;
  the no-digital-source 2026 leads cluster on ~8 staff creators).

So: digital leads attribute via utm; phone leads via CallRail / direct-line
campaign names; manual leads via `CreatedBy`; existing patients via the
`source_link` ordering. The VENDOR layer is the one thing NOT in the data — it
comes from mapping rules (below).

## Data model (new `attribution` domain)

A small new domain package `packages/attribution` (own schema), kept separate
from `ops`/`ingest` — it is derived semantic data, re-buildable from raw.

1. **`attribution.source_node`** — controlled-vocab chain nodes:
   `id, level (vendor|channel|campaign|ad_set|ad|form), slug, label, parent_id,
   active`. The chain is the `parent_id` ladder (ad → ad_set → campaign →
   channel → vendor). Seeded with known vendors + channels; campaigns/ads grow
   from observed utm values.

2. **`attribution.lead_attribution`** — resolved, per `person_uid` (+ source
   lead id). Denormalized for fast funnel slicing:
   `vendor_id, channel_id, campaign_id, ad_set_id, ad_id, form_id, agent_name,
   method (auto|rule|manual), confidence (0–1), resolved_at, source_signal`.
   Denormalized columns (not just deepest node) so a funnel GROUP BY any level
   is a single join.

3. **`attribution.mapping_rule`** — editable rules:
   `priority, match_field, match_op (eq|ilike|prefix), match_value, set_level,
   set_node_id, active`. e.g. `utm_campaign ILIKE 'Dima%' → vendor=Dima`. This is
   how the chain learns the vendor and how staff teach the system.

## Resolution = waterfall + rules (ENG-448)

For each lead, in priority order, fill the chain and stop at the first match for
`channel`; deeper/parallel levels fill where data exists:

1. **digital** — `utm_source` / `last_touch_source` → channel; `utm_campaign` →
   campaign; `utm_adgroup` → ad_set; `utm_content` → ad.
2. **phone** — `Hubspot_Lead_Source=CallRail` / `Callrail_Inbound__c` / campaign
   matches a "*direct line*" pattern → channel=phone.
3. **named campaign** — `utm_campaign` / `last_touch_campaign` present though
   source empty → channel inferred from rules, campaign set.
4. **manual** — `CreatedBy` is a staff user and no marketing signal →
   channel=manual, `agent_name = CreatedBy.Name`.
5. **reactivation** — `identity.source_link` shows CareStack BEFORE the SF lead →
   channel=existing_patient.
6. else → `needs_review` (counted + logged; target ~0).

Then **mapping rules** run to set `vendor` (and override channel where a rule is
more specific). `method=rule` where a rule fired, else `auto`. A batch job
(re)resolves all leads idempotently; a per-lead hook resolves on ingest.

## Manual enrichment (ENG-449) — in OUR system, never SF

Read-only SF pull is a hard guard-rail; we never write back. Enrichment lives
in our DB:

- **Mapping rules** (above) — staff define `pattern → chain node` so new leads
  auto-classify by vendor/channel. This scales: one rule fixes thousands of
  leads.
- **Per-lead override** — for the long tail, staff set any chain level on one
  lead; `method=manual` wins and is sticky across re-resolution.
- Every manual change is audited.

## Analytics (ENG-450)

- Funnel aggregate joins `lead_attribution`; `dimension` param selects the chain
  level + optional parent filter (drill-down).
- The dashboard's "unknown" is replaced by the resolved breakdown; the
  `needs_review` count is shown explicitly so the gap is visible, not hidden.

## Open decisions

1. Domain home: standalone `attribution` package vs under `insight`/`ops`.
2. Dirty-name normalization (campaign/form names have `- Copy`, casing, language
   variants) — normalize into `source_node.slug` (trim/lower/strip suffixes) with
   `label` keeping the display form.
3. Pre-2026 backfill of `CreatedBy.Name` to cover the full ~26k unknown bucket
   (only 2026 done so far).
4. Confidence model: simple per-branch constants vs learned.

## Decomposition

- A (ENG-447) — taxonomy + per-lead attribution schema.
- B (ENG-448) — waterfall resolver.
- C (ENG-449) — mapping rules + per-lead override (manual enrichment).
- D (ENG-450) — funnel analytics by chain level + drill-down.

This is a NEW epic, separate from the ENG-425 ingest-framework mission (already
in PR #148). Strategy proposes; Orchestrator creates the execution mission after
the design + domain-home decision are accepted.
