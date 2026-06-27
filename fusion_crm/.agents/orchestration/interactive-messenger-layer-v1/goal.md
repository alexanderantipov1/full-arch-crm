# Mission Goal — Interactive Corporate Messenger Layer (Mattermost) V1

**Linear project:** [Interactive Corporate Messenger Layer (Mattermost) V1](https://linear.app/fusion-dental-implants/project/interactive-corporate-messenger-layer-mattermost-v1-5cc0552b86e0)
**Epic:** ENG-433
**Accepted from Strategy:** 2026-06-15
**Doctrine:** `.agents/strategy/INTERACTIVE_MESSENGER_LAYER_DOCTRINE.md`

## Goal

Build an interactive corporate messenger layer on self-hosted Mattermost: an
internal team channel plus a bidirectional automation/agent interface
(human-in-the-loop). Mattermost is an external provider behind a thin
`ChatProvider` adapter — not forked. Outbound is rule-driven and de-identified
by default; inbound is signed and captured verbatim before curated mapping.

## Blocks → Linear

| Block | Issue | Title |
| --- | --- | --- |
| A | ENG-434 | Local Mattermost infrastructure (compose profile "chat") |
| B | ENG-435 | ChatProvider abstraction + MattermostAdapter + outbound send |
| C | ENG-436 | Outbox + notification rules schema + dispatch worker |
| D | ENG-437 | Rules engine (field conditions) + first-wave event wiring |
| E | ENG-438 | Signed inbound (buttons + thread replies) + domain mapping |
| F | ENG-439 | Manual enrichment store (record_annotation) |
| G | ENG-440 | Agent human-in-the-loop (approve/reject via chat) |
| H | ENG-441 | Governance: ADR-0006 + audit actions + docs |
| I | ENG-442 | Production infrastructure (deferred, DEPLOYMENT_RULES-gated) |

## Merge order

A → C → B → D → E → F → G → H, with I last and isolated.

## Task class

`contract_change` overall (durable schema, new provider kind, public route,
new raw_event source, audit taxonomy, deployment). Cross-runtime review required
for all blocks except A (infra-only, `normal`) and H docs portion.

## Open human decisions (block-scoped, not blocking Block A)

1. `record_annotation` domain placement — recommend new `enrichment` domain (F)
2. Mattermost version pin + upgrade cadence (A)
3. Prod host shape + `chat.*` hostname/TLS (I)
4. Prod Mattermost DB placement (I)
5. Canonical `event_type` taxonomy (D)
6. Message/file retention + backup policy (I)

## Execution gate

Start with Block A (ENG-434) — reversible, local-only. Defer Block I (ENG-442)
until ADR-0006 is Accepted and DEPLOYMENT_RULES preflight passes. No worker is
launched until the user approves execution.
