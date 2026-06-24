# Worker Report — ENG-427 (Block B: SF dynamic projection + FLS-gap)

- **Task**: B — Salesforce dynamic describe-driven projection + Tooling-API FLS-gap detector
- **Linear**: ENG-427
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch**: eng-425-full-fidelity-ingestion-v1
- **Status**: COMPLETE — all 8 SF services on the dynamic full-fidelity
  projection; real-SF verified 8/8.

## Rollout (all 8 SF services)

Reusable `packages/ingest/sf_schema_sync.py::SfSchemaSync` holds the
projection + registry-sync logic once; each service declares its object name +
static fallback. Converted: Lead, Contact, Account, Opportunity, Event, Task,
Case, OpportunityHistory. Static `_SF_*` projections kept only as fallback.

Relationship-field preservation: `Owner.Name` (and any dotted field) from the
static projection is appended to the dynamic one — a describe-driven field set
cannot express relationship traversals, and dropping `Owner.Name` would regress
ENG-408 owner-name enrichment.

### Real-SF verify — ALL 8 PASS (infra/scripts/verify_sf_full_fidelity.py)

| Object | readable fields | live keys | CreatedById |
| --- | --- | --- | --- |
| Lead | 240 | 240 | Y |
| Contact | 107 | 106 | Y |
| Account | 164 | 161 | Y |
| Opportunity | 255 | 256 | Y |
| Event | 69 | 70 | Y |
| Task | 61 | 62 | Y |
| Case | 39 | 40 | Y |
| OpportunityHistory | 14 | 14 | Y |

Suite: 466 ingest+integrations passed; `mypy packages apps` clean (243 files);
all changed files ruff-clean. (Pre-existing repo lint debt in unrelated files —
funnel.py, actor/service.py, the other in-tree features — left untouched; not in
scope.)

## What changed (touched files)

- `packages/integrations/salesforce/client.py` — `describe(resource)`
  (FLS-aware sObject describe), `describe_tooling_fields(resource)` (Tooling
  `FieldDefinition`, NOT FLS-filtered, paginates), shared `_get_json` helper
  (refresh-once-on-401).
- `packages/ingest/sf_schema.py` — NEW pure module: `selectable_fields`,
  `build_projection` (skips base64/address/location compound parents),
  `build_observed_fields` (describe→readable, Tooling-only→`readable=False`
  with `fls_blocked`), `fls_gap`. Type labels truncated to the registry's
  64-char column.
- `packages/ingest/sf_lead_service.py` — `SfClientProtocol` extended with
  `describe` + `describe_tooling_fields`; `sync_schema(tenant_id)` (describe +
  Tooling → registry via `IngestService.sync_object_schema`, logs FLS gap,
  returns `(SchemaDiffOut, gap)`); `_projection(tenant_id)` builds the SELECT
  from the registry, falling back to live describe then the static
  `_SF_LEAD_PROJECTION`; 3 SOQL templates rewired to `{projection}`.
- Tests: `tests/ingest/test_sf_schema.py` (12), `test_sf_lead_schema_wiring.py`
  (4), `tests/integrations/test_sf_client.py` (+3), harness fix in
  `test_sf_lead_service.py` (registry mock).

## Design notes

- Projection comes from the registry (refreshed out-of-band by Block C), so we
  do NOT `describe` on every pull — honors the doctrine's cadence rule.
- Static `_SF_LEAD_PROJECTION` kept ONLY as a last-resort fallback so a pull
  never breaks if describe + registry are both unavailable.
- FLS gap = Tooling minus describe (principle 4): the exact admin remediation
  list, never silently lost.

## Tests run / results

- `pytest tests/ingest tests/integrations` → **460 passed**.
- `ruff` + `mypy` on changed files → clean.
- No real Salesforce traffic yet (respx-stubbed). Real describe/Tooling smoke
  against the org is the gating verification before merge.

## Real-SF verification — PASS (2026-06-14)

`infra/scripts/verify_sf_full_fidelity.py` against the live connected org:

- describe readable fields: **240** vs static projection **45** (we were
  capturing ~19% of the Lead object).
- dynamic projection: **239** fields; live SOQL (LIMIT 1) returned **240**
  keys per record; **`CreatedById` present: True**.
- registry sync: **+247** fields (240 readable + 7 FLS-blocked), 0 removed.
- **FLS-gap (7)**: `CampaignId`, `CampaignMemberStatus`,
  `ConnectionReceivedDate`, `ConnectionSentDate`, `InternalSource`,
  `RecordVisibilityId`, `UserRecordAccessId`. Note: `CampaignId` IS a Lead
  field — blocked only by FLS — directly answering the earlier "which campaign"
  question (grant the integration user FLS read to capture it).

**Bug found by real data + fixed:** Tooling `QualifiedApiName` casing
(`CreatedByID`) differs from describe `name` (`CreatedById`) for the same
field. Case-sensitive matching falsely flagged it FLS-blocked and wrote a
duplicate registry row. `sf_schema` now compares case-insensitively; +2
regression tests. Full suite: **462 passed**.

## Remaining for ENG-427

1. Replicate the `sync_schema` + dynamic `_projection` pattern to the other 7
   SF services: Contact, Account, Opportunity, Event, Task, Case,
   OpportunityHistory (each has its own static `_SF_*_PROJECTION` + SOQL
   templates). Mechanical once Lead is proven.
2. **Real-SF verification**: run a live Lead pull on the local stack, confirm
   the raw payload widened to all queryable fields (incl. previously-missing
   like `CreatedById`), and the FLS-gap report is sane. Per
   `feedback_verify_with_real_data_before_merge`.

## Risks

- Per-object SOQL quirks (e.g. OpportunityHistory) may need small tweaks when
  rolling out to the remaining 7 — verify each against real SF.
- Until real-SF verification, the dynamic widening is unproven on live data;
  the static fallback bounds the blast radius.

## Do-not-merge conditions

- Do not merge before real-SF verification of the Lead path.
- Roll out to all 8 services (no static field lists remaining) before closing
  ENG-427 per its acceptance.
