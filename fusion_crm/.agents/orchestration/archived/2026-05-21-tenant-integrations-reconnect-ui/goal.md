# Mission Goal — Tenant Integrations Reconnect / Edit / Disconnect UI

Restore actionable credential management for Salesforce and CareStack in
`/settings/tenant?tab=integrations`. The page currently lists rows as
`Active` but every action button is a disabled placeholder; if a token
expires or an API key rotates, the operator has nowhere in the UI to fix
it.

## Source

- Linear: ENG-214
- Strategy candidate: `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Tenant Integrations: SF + CareStack Reconnect / Edit / Disconnect UI"

## Outcome

1. Salesforce **Reconnect** wired to OAuth-start flow.
2. CareStack **Edit API key** via masked modal.
3. **Disconnect** with typed-provider-name confirm modal.
4. `refreshed_at` / `expires_at` rendered (relative primary, ISO on hover).
5. Salesforce **callback URL hint** with copy-to-clipboard.
6. Vitest coverage for new hooks + modals.
7. End-to-end manual smoke in local dev.

## Constraints

- No new backend endpoints.
- Repository files in English.
- No PHI, no secrets in logs, never echo stored secrets back to DOM.
- No commits/pushes from Worker — Orchestrator/Integrator owns merge.
