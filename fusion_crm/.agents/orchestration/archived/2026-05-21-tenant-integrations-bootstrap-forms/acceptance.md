# Acceptance Criteria

1. `NotConnectedCard` for Salesforce: "Set up" button opens
   `BootstrapCredentialModal` with 4 fields (`client_id`, `client_secret`
   masked, `callback_url`, `domain`). Submit calls
   `POST /tenant/credentials` via `useUpsertBootstrapCredential`.
2. `NotConnectedCard` for CareStack: "Set up" button opens the same
   modal with 6 fields (`vendor_key`, `account_key`, `account_id` masked,
   `idp_base_url`, `api_base_url`, `api_version`).
3. `ConnectedCard` for SF and CS: secondary "Edit config" button opens
   the same modal with `display_name` pre-filled; secrets are NEVER
   pre-filled.
4. Stale `Coming next — credential UI lands when backend ENG-128 is ready`
   tooltip removed from `NotConnectedCard`.
5. Vitest covers: SF variant renders 4 fields; CS variant renders 6;
   submit with empty required field blocks; password fields use
   `type="password"` + `autoComplete="off"`.
6. `cd apps/web && npx tsc --noEmit` clean.
7. `cd apps/web && npx eslint . --max-warnings 0` clean.
8. `cd apps/web && npx vitest run` green (existing + new tests).
