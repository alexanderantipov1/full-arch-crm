# Authentication — OAuth2 password grant

CareStack issues bearer JWTs via an IdentityProvider (IdP) host
separate from the resource API. The grant type is the
`password` flow (RFC 6749 §4.3), using four credentials.

## Credentials provisioned by CareStack

| Name | Purpose | Scope |
|---|---|---|
| `Base URL` | IdP host (e.g. `https://id.carestack.com`) | global |
| `client_id` | Identifies the vendor (us) | per vendor |
| `client_secret` | Vendor secret | per vendor |
| `username` | "Vendor key" — same for all accounts a vendor serves | per vendor |
| `password` | "Account key" — unique per clinic/account | **per account** |

→ In Fusion CRM, **one CareStack `password` per clinic account**.
Model: `client_id`, `client_secret`, `username` live in global
settings; `password` is a per-account secret.

## Token request

```
POST <base_url>/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=password
client_id=<client_id>
client_secret=<client_secret>
username=<vendor_key>
password=<account_key>
```

### Success response (200)

```json
{
  "access_token": "<JWT>",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

- **TTL: 1 hour** (verify via the JWT `iat` / `exp` claims).
- On 401 from an API call → assume the token expired, re-request a
  fresh one, retry once.

## Using the token

```
Authorization: Bearer <access_token>
```

On every request to `<account>.carestack.com/v1.0/...`.

## Fusion CRM integration plan

1. **Settings** — add `CARESTACK_IDP_URL`, `CARESTACK_CLIENT_ID`,
   `CARESTACK_CLIENT_SECRET`, `CARESTACK_VENDOR_KEY` to
   `packages.core.config.Settings`. Per-account `password` lives
   elsewhere (DB table or mounted secret; never in `.env` committed).
2. **Token cache** — Redis key
   `carestack:token:<account_id>` with TTL 55 min (5 min margin).
3. **Client** — `packages/integrations/carestack/client.py`
   (async httpx) fetches a token on cold start / 401 and injects the
   Bearer header. On 401 it invalidates the cache and retries once.
4. **Credentials rotation** — store the account key in a dedicated
   secret store or an encrypted DB column; never log, never return
   via API.

## Security

- Never log the raw token, `client_secret`, or `password`.
- Redact on structlog bindings (processor that strips `authorization`,
  `client_secret`, `password`).
- Prefer process-level env injection over `.env` files for the
  secrets; mount per-account keys read-only.
