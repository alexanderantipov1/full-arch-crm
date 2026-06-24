# CLAUDE.md — `packages/integrations/google_workspace`

Google OAuth + Gmail API plumbing. Read
`packages/integrations/CLAUDE.md` first for the cross-cutting rules
(no PHI imports, audit on every state change, packages-level boundaries).
This file documents the Workspace-specific surface only.

## Phase 1 scope (ENG-131)

The OAuth + send foundation. Today this package exposes:

- `GoogleOAuthClient` — authorize URL + code exchange + refresh +
  ID-token verification. Token endpoint POSTs are HMAC-clean (no
  query-string secrets).
- `GoogleWorkspaceClient` — Gmail API client; `send_message` and
  `get_profile`. Built via `from_credential(credential_id)` only —
  there is no `from_env` factory.
- `GoogleOAuthError`, `GoogleAPIError`, `PersonalAccountBlocked` —
  typed exceptions; the FastAPI middleware translates them to the
  envelope.

ENG-132 (the outreach send service) is the first caller of
`send_message`. ENG-135 (the settings UI) drives the `auth_url` flow.

## HIPAA compliance gate

Per ADR-0004 §"HIPAA compliance gate" and ENG-131. Personal Gmail
mailboxes are NOT BAA-eligible. The gate runs in
`oauth.exchange_code` BEFORE any token is handed to the credential
store. Two checks, both required:

1. **`hd` claim non-empty** — Workspace grants ship a hosted-domain
   claim. A grant from a personal `@gmail.com` account omits `hd`
   entirely; that is the canonical signal.
2. **email host not in `PERSONAL_EMAIL_DOMAINS`** — defence in depth.
   `gmail.com` / `googlemail.com` are blocked even if `hd` is somehow
   present.

`email_verified=true` is also required — we will not route mail
through a Google account whose own email is unverified.

The gate is mandatory. There is no operator-toggled opt-out at the
package level. A non-BAA dev tenant that legitimately needs to test
with `@gmail.com` would have to disable HIPAA mode entirely (out of
scope for ENG-131).

## OAuth scopes

```
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/userinfo.email
openid
```

`access_type=offline` + `prompt=consent` are both set so Google
issues a long-lived `refresh_token` on every grant. Without
`prompt=consent`, a re-auth from an already-consented user omits the
refresh_token, leaving us with a one-hour access window and no
recovery path.

Inbound scopes (`gmail.readonly`) are deferred to Stage 2 per
ADR-0004 §"What this enables". Adding them later requires operator
re-consent — we do not pre-request them now.

## Token storage

Tokens live in `tenant.integration_credential` (encrypted via the
Fernet envelope). One row per `(tenant_id, "google_workspace",
"oauth_token", mailbox_email)` — multi-mailbox by design.

Payload shape (after ENG-131 callback persists it):

```json
{
  "access_token": "ya29...",
  "refresh_token": "1//...",
  "id_token": "eyJ...",
  "expires_at": 1715180000.0,
  "scope": "https://www.googleapis.com/auth/gmail.send openid",
  "token_type": "Bearer",
  "mailbox_email": "info@galleriaoms.com",
  "hd": "galleriaoms.com",
  "sub": "1138..."
}
```

`mailbox_email` and `hd` are denormalised onto the payload so the
audit + diagnostics paths can read them without re-decoding the
ID-token. None of these values appear in audit `extra` (the
audit row carries only `tenant_id`, `credential_id`, `provider_kind`,
`credential_kind`, `is_default`, `has_mailbox`, `has_location`).

## Refresh flow

`GoogleWorkspaceClient` runs the refresh path on:

1. Proactive: when `expires_at` is within `_REFRESH_SKEW_SECONDS` (60s).
2. Reactive: when an API call returns 401.

The refresh callback (`from_credential` builds it) writes the new
`access_token` + `expires_at` back to the credential row via
`IntegrationCredentialService.upsert` — the row stays the source of
truth. If the refresh itself fails (revoked grant, bad client_id),
the call raises `GoogleOAuthError` and the operator UI surfaces
"reconnect this mailbox".

## Required env (Workspace OAuth app)

- `GOOGLE_OAUTH_CLIENT_ID` — Web-app client id from Google Cloud
  Console → APIs & Services → Credentials. The OAuth consent screen
  must be configured for **External** user type.
- `GOOGLE_OAUTH_CLIENT_SECRET` — the matching secret.
- `OAUTH_REDIRECT_BASE_URL` — base URL for the callback (the API
  appends `/integrations/google_workspace/callback`). Must EXACTLY
  match an authorised redirect URI registered with the OAuth client.

## Tests

`tests/integrations/google_workspace/test_oauth.py` covers:

- `test_state_csrf_roundtrip` — mint + verify a state token via the
  shared `_oauth_state` helper (positive + tampered cases).
- `test_personal_gmail_blocked` — a decoded id_token without `hd`
  raises `PersonalAccountBlocked`.
- `test_workspace_account_passes` — `hd=galleriaoms.com` flows
  through the gate cleanly.
- `test_callback_persists_credential` — full `exchange_code` happy
  path with `respx`-mocked token endpoint and a stub JWK client; we
  assert `IntegrationCredentialService.upsert` is called with the
  right tenant + provider + mailbox arguments via the route layer.

External calls are stubbed with `respx`. Real Google traffic is
generated only by the manual smoke test.

## Out of scope

- Inbound scopes / `gmail.readonly` — Stage 2.
- Domain-wide delegation / service accounts — ADR-0004 picks
  per-operator OAuth, not impersonation.
- Watch / push notifications — Stage 2.
