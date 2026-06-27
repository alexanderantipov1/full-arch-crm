# Mission Goal — Tenant Integrations Bootstrap Forms

Provide UI for operators to enter the full set of Salesforce Connected App
config (client_id, client_secret, callback_url, domain) and CareStack
partner config (vendor_key, account_key, account_id, idp_base_url,
api_base_url, api_version) — fields that today have no entry surface
anywhere in the staff app.

## Source

- Linear: ENG-215
- Predecessor: ENG-214 (PR #81) — wired reconnect/edit-single-key/disconnect
  on EXISTING credential rows. Bootstrap (first-time, full-rotation) is
  the remaining gap.

## Outcome

1. `NotConnectedCard` for SF and CS opens a `BootstrapCredentialModal`.
2. `ConnectedCard` for SF and CS gets a secondary "Edit config" button
   that opens the same modal (full re-key, not just `api_key`).
3. Stale `ENG-128` placeholder gone from `NotConnectedCard`.
4. Secrets never echoed back; encrypted at rest in
   `tenant.integration_credential.payload`.

## Constraints

- No backend changes; reuse `POST /tenant/credentials` via
  `useUpsertBootstrapCredential`.
- No PHI, no secrets in logs.
- Repository files in English.
