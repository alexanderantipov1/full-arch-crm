# Acceptance Criteria

1. Salesforce row's **Reconnect** button calls the canonical OAuth start
   endpoint and lands the operator back on
   `/settings/tenant?tab=integrations&connected=salesforce` (via the #68
   redirect path). No more `title="Reconnect flow ships with ENG-128"`
   placeholder.
2. CareStack row's **Edit** button opens a modal with masked input(s) for
   the API key (and any related metadata: subdomain, location alias). On
   submit, calls `PUT /tenant/credentials/{credential_id}` and re-fetches
   the integration list. The stored secret is never rendered back to the
   DOM after save.
3. **Disconnect** button on either provider row opens a confirm modal
   requiring the operator to type the provider name (e.g. "Salesforce")
   before submission becomes enabled. Submit calls `DELETE
   /tenant/credentials/{credential_id}` and re-fetches the list.
4. Each provider row shows `refreshed_at` and `expires_at` as relative
   time strings (e.g. "2h ago", "in 14d") with the full ISO timestamp in
   the element's `title` attribute. "—" only when the backend returns
   null.
5. Salesforce row carries a one-line **Callback URL hint** block:
   "Paste into Salesforce Connected App → Callback URL:" followed by the
   exact URL synthesised from `OAUTH_REDIRECT_BASE_URL` plus
   `/api/integrations/salesforce/callback`, with a Copy button.
6. New vitest coverage: open / submit happy / submit error path for the
   two modals; happy / error path for the update and delete mutation
   hooks. `pnpm --filter @fusion-crm/web test` (or `npm test` in
   `apps/web`) green.
7. Manual smoke (recorded in `reports/TASK-H-smoke.md`):
   - Reconnect SF → OAuth consent → callback → operator returns to the
     settings tab with the Salesforce row still `Active` and a fresh
     `refreshed_at`.
   - Edit CS API key → modal save → success toast or status update; row
     reflects the new `refreshed_at`.
   - Disconnect SF (then re-add via Reconnect) → row disappears, then
     reappears.
