# Analytics Policy Preflight V1

Policy preflight evaluates every analytics query spec before service execution.
It is a backend/service-layer control, not a frontend convention.

## Inputs

- authenticated principal;
- tenant/environment context;
- structured analytics query spec;
- catalog term metadata;
- query registry metadata when available;
- requested output level;
- requested data classes;
- export/drilldown flags;
- source references and audit posture.

## Decisions

Policy preflight returns one of:

- `allow`
- `allow_with_warnings`
- `clarify`
- `deny`

## Decision Shape

```json
{
  "decision": "allow_with_warnings",
  "reason_codes": ["billing_data", "row_level_allowed_internal"],
  "data_classes": ["ops", "identity", "billing"],
  "output_level": "aggregate_drilldown",
  "audit_required": true,
  "phi_service_required": false,
  "warnings": [
    "Billing data is included. Result must show data-class markings."
  ],
  "clarification": null
}
```

## Current Mission Policy

Current production users are treated as authorized internal users. Row-level
analytics output is allowed for them during this mission phase.

This does not remove:

- service-layer checks;
- result field allowlists;
- source references;
- data-class markings;
- audit for billing/PHI-adjacent/PHI-sensitive paths;
- `PhiService` for PHI;
- raw provider payload exclusion.

## Checks

### Authentication

- Principal must be authenticated.
- Anonymous analytics requests are denied.

### Role And User Class

- Current production users are `authorized_internal`.
- Future external or limited roles must be added explicitly.
- Unknown role classes are denied by default.

### Data Class

| Data class | V1 policy |
| --- | --- |
| `ops` | Allowed. |
| `identity` | Allowed through field allowlists. |
| `integration_metadata` | Source references allowed; raw payloads denied. |
| `billing` | Allowed for current production users; audit required. |
| `phi_adjacent` | Allowed through reviewed fields; data-class badge required. |
| `phi` | Deny unless routed through `PhiService` with audit and explicit PHI-capable path. |
| `raw_provider` | Denied for ordinary analytics output. |

### Output Level

- `aggregate`: allowed when terms are cataloged.
- `aggregate_drilldown`: allowed for current production users.
- `row_level`: allowed for current production users when bounded by filters and
  service field allowlists.
- `export_allowed_rows`: denied until export policy is approved.

### Row-Level Safety

Row-level requests must:

- use catalog terms;
- include bounded filters or explicit limits;
- return only approved fields;
- include data-class markings;
- include source references where available;
- avoid raw provider payloads;
- record audit when billing, PHI-adjacent, or PHI paths are involved.

### PHI

V1 analytics terms are designed to avoid clinical-note PHI. If a query requires
PHI:

- route through `PhiService`;
- check principal permission;
- write audit;
- return minimum necessary fields;
- deny if no approved PHI-capable lane exists.

### Billing

Billing data is allowed for current production users, but results must include
audit posture and data-class markings. Payment/balance/accepted amount queries
must not expose raw ledger payloads.

### Export

Exports are out of scope until ENG-281. Any export request returns:

```json
{
  "decision": "deny",
  "reason_codes": ["export_policy_deferred"],
  "message": "Export policy is not approved for this mission phase."
}
```

### Ambiguity

Preflight returns `clarify` when:

- source attribution model is missing and no catalog default exists;
- stale threshold is missing and no catalog default exists;
- payment evidence definition is missing;
- balance source-of-truth is missing;
- requested row fields are not in the field allowlist;
- query references a term with `blocked` review status.

## Audit Events

Audit should record:

- principal id;
- request id;
- original natural language question when present;
- query spec;
- catalog terms and versions;
- decision;
- data classes touched;
- output level;
- row limit;
- row count after execution when available;
- billing/PHI-adjacent/PHI flags;
- export flag;
- timestamp.

## Service Integration

The execution order is:

```text
client/chat/workbench
-> query spec validation
-> policy preflight
-> query registry lookup
-> analytics service
-> result contract
-> audit completion metadata
```

Routes must not hold business logic. Services own policy-aware execution and
repositories remain data-only.

## Test Matrix For Implementation

- unauthenticated request denied;
- unknown term denied;
- raw SQL payload denied;
- raw provider output denied;
- aggregate ops query allowed;
- billing row-level query allowed with audit;
- PHI query denied unless `PhiService` path approved;
- export request denied;
- ambiguous attribution returns clarification;
- blocked catalog term returns deny or clarify;
- allowed row-level result includes field allowlist and data-class markings.
