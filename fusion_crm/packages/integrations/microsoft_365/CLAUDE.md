# CLAUDE.md — `packages/integrations/microsoft_365`

Microsoft Identity Platform OAuth + Graph API plumbing. Read
`packages/integrations/CLAUDE.md` first for the cross-cutting rules.
This file documents the M365-specific surface only.

## Phase 1 scope (ENG-131)

Mirror of the `google_workspace` package — OAuth + send-only Graph
client.

- `MicrosoftOAuthClient` — authorize URL + code exchange + refresh
  + ID-token verification.
- `MicrosoftClient` — Graph v1.0 client; `send_message` (POST
  `/me/sendMail`) and `get_profile` (GET `/me`). Built via
  `from_credential(credential_id)` only.
- `MicrosoftOAuthError`, `MicrosoftAPIError`, `PersonalAccountBlocked`
  — typed exceptions.

ENG-132 calls `send_message` with a pre-built Graph message body.
The RFC 822 fallback exists for symmetry with the Gmail client; new
code paths should pass `graph_message=` directly.

## HIPAA compliance gate

Per ADR-0004 §"HIPAA compliance gate" and ENG-131. Personal MSA
accounts are NOT BAA-eligible. Two checks at every callback:

1. **`tid` claim is not the consumer-tenant id**
   (`9188040d-6c67-4c5b-b112-36a304b66dad`). Microsoft reuses this
   tid for every personal MSA grant — rejecting it is the canonical
   block. M365 Business / Enterprise tenants have their own tids
   and pass this check.
2. **`preferred_username` host not in `PERSONAL_EMAIL_DOMAINS`**
   (`outlook.com`, `hotmail.com`, `live.com`, `msn.com`). Defence
   in depth — even if a B2C-style fork were to slip the tid check,
   the email host would catch it.

The gate is mandatory. There is no operator-toggled opt-out.

## OAuth scopes

```
https://graph.microsoft.com/Mail.Send
https://graph.microsoft.com/User.Read
offline_access
openid
email
profile
```

`offline_access` is required for the refresh token. `email` +
`profile` are required for `preferred_username` to land in the ID
token (which the gate reads).

## OAuth endpoints

- Authorize: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
- Token: `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- JWKS: `https://login.microsoftonline.com/common/discovery/v2.0/keys`

Why `/common/`: we cannot enumerate operator AD tenants ahead of
time. The `tid` claim in the returned ID token tells us which one
they came from, which the compliance gate then evaluates.

## Token storage

One row per `(tenant_id, "microsoft_365", "oauth_token",
mailbox_email)` in `tenant.integration_credential`. Multi-mailbox
by design.

Payload shape (after ENG-131 callback persists it):

```json
{
  "access_token": "ey...",
  "refresh_token": "M.R3_BAY...",
  "id_token": "ey...",
  "expires_at": 1715180000.0,
  "scope": "https://graph.microsoft.com/Mail.Send offline_access ...",
  "token_type": "Bearer",
  "mailbox_email": "info@galleriaoms.com",
  "tid": "11111111-2222-3333-4444-555555555555",
  "oid": "..."
}
```

Microsoft uses **rolling refresh tokens** — every refresh response
returns a new `refresh_token`, and the old one stops working. The
`from_credential` refresh callback always overwrites the stored
refresh_token, never preserves the old one.

## Required env (Azure AD app registration)

- `MICROSOFT_OAUTH_CLIENT_ID` — application (client) ID from Azure
  AD → App registrations → your app → Overview.
- `MICROSOFT_OAUTH_CLIENT_SECRET` — value from Certificates &
  secrets (NOT the secret id; the actual value).
- `OAUTH_REDIRECT_BASE_URL` — base URL for the callback. The redirect
  URI registered in Azure AD must EXACTLY match
  `<OAUTH_REDIRECT_BASE_URL>/integrations/microsoft_365/callback`.

App registration steps:

1. Azure AD → App registrations → New registration.
2. Supported account types: "Accounts in any organizational directory
   (Any Microsoft Entra ID tenant — Multitenant)". Personal MSAs
   are blocked downstream by our compliance gate, but registering
   for multi-tenant is what lets `/common/` work for every clinic.
3. Redirect URI: Web → `<OAUTH_REDIRECT_BASE_URL>/integrations/microsoft_365/callback`.
4. API permissions → Microsoft Graph → Delegated:
   `Mail.Send`, `User.Read`, `offline_access`, `openid`, `email`,
   `profile`. Grant admin consent for the home tenant; per-tenant
   consent happens on each operator's first connect.
5. Certificates & secrets → New client secret → copy the **value**.

## Graph `sendMail` quirks

- The endpoint returns 202 with empty body. We do not get a
  `messageId` / `threadId` back — `MicrosoftClient.send_message`
  surfaces `{"message_id": null, "thread_id": null}` deterministically.
  Stage 2 may add a "lookup last sent" step using `/me/mailFolders/sentitems/messages`.
- `saveToSentItems: true` is set so the operator sees every
  outbound message in their Outlook Sent folder (ADR-0004 §"Trust").

## Tests

`tests/integrations/microsoft_365/test_oauth.py` mirrors the Google
test file:

- state CSRF roundtrip
- `test_personal_msa_blocked_by_tid` — id_token with consumer-tenant
  id raises `PersonalAccountBlocked`.
- `test_personal_msa_blocked_by_email_host` — id_token with a
  business-looking tid but `@outlook.com` username still blocks.
- `test_business_account_passes` — non-consumer tid + business
  email host flows through cleanly.
- `test_callback_persists_credential` — full flow.

External calls are stubbed with `respx`; no real Microsoft traffic.

## Out of scope

- Inbound (`Mail.Read`) — Stage 2; requires re-consent.
- App-only (client credentials) flows — ADR-0004 picks per-operator
  delegated grants.
- Webhook subscriptions — Stage 2.
