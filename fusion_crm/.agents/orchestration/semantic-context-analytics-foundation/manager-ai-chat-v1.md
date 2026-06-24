# Manager AI Chat V1

Manager AI Chat V1 is the aggregate-only chat planning and execution contract
for manager analytics questions.

V1 is deterministic and tool-backed. It does not call a general LLM planner,
does not accept SQL, does not inspect raw provider payloads, and does not
return row-level results. A later version can replace the deterministic planner
with an LLM planner only if it still produces the same structured query spec
and policy preflight result before execution.

## Tool Surface

- Tool: `ask_manager_analytics`
- Package: `packages.tools.manager_chat_tools`
- Registry: `packages.tools.registry.ALL_TOOLS`
- Execution target: `run_analytics_query`
- Output posture: aggregate only
- Export: not produced by chat; aggregate CSV export is available through the
  separate `export_analytics_csv` tool.

## Flow

```text
manager question
-> deterministic intent selection
-> approved query id
-> structured query spec
-> aggregate-only policy preflight
-> run_analytics_query
-> aggregate read-model result
-> short explanation
-> audit rows
```

## Supported V1 Intents

| User intent | Query id | Read model id |
| --- | --- | --- |
| Lead source profile | `lead_source_profile.v1` | `lead_source_profile` |
| Lead conversion funnel | `lead_conversion_funnel.v1` | `lead_conversion` |
| Paid leads by source | `paid_leads_by_source.v1` | `paid_leads` |
| Consultation follow-up | `consultation_followup_worklist.v1` | `consultation_followup` |
| Treatment revenue evidence | `treatment_revenue_evidence.v1` | `treatment_revenue` |

## Clarification Behavior

If the question does not match an approved V1 intent, the tool returns:

- `planner.status = clarification_needed`
- `query_spec = null`
- `policy_preflight.decision = clarify`
- `execution = null`
- a clarification prompt listing supported topics

It must not guess a metric, invent a query id, or run a fallback search.

## Structured Query Spec

The planner emits:

```json
{
  "intent": "manager_analytics",
  "query_id": "paid_leads_by_source.v1",
  "params": {},
  "output_level": "aggregate"
}
```

The query spec is intentionally small in V1. Params are passed through the same
structured validation used by `run_analytics_query`.

## Policy Preflight

V1 allows only:

- approved query ids;
- aggregate output;
- structured filters;
- no direct chat export;
- no raw SQL;
- no raw provider payloads.

Row-level and drilldown requests are denied by the execution tool. CSV export is
available only through the separate `export_analytics_csv` tool and remains
aggregate-only.

## Audit

`ask_manager_analytics` writes a `tool.ask_manager_analytics` audit row with:

- selected query id;
- whether execution was requested;
- param keys only, never raw values;
- tenant and principal from `ToolContext`.

When execution runs, `run_analytics_query` writes its own
`tool.run_analytics_query` audit row.

## Explanation Contract

V1 explanations are templated and conservative:

- identify the executed query id;
- identify the read model id;
- report aggregate bucket count;
- state that no row-level drilldown or export was produced.

The explanation must not fabricate business insight beyond the returned
aggregate payload.

## Deferred

- natural-language LLM planner;
- streaming chat UI;
- saved conversations;
- row-level follow-up worklists;
- direct chat export, row-level export, and scheduled reports;
- PHI-aware clinical answers.
